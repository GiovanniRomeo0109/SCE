"""
services/worker_progetti.py — Elaborazione in background dei documenti dei progetti PSC

Un solo thread, avviato all'avvio dell'app. Ciclo:
  1. classifica i documenti nuovi (una chiamata Haiku per gruppo di file dello stesso progetto;
     foto ed elenchi prezzi XML/fogli di calcolo riconosciuti senza AI)
  2. elabora i documenti in coda in ORDINE DI PRIORITÀ (elenchi prezzi → contratto → relazione →
     computo → ... → tavole → foto), un blocco da max 100 pagine alla volta
  3. prima di ogni blocco controlla budget demo e limite giornaliero: se non bastano, il documento
     passa "in attesa" e si prova il successivo (magari più piccolo)
  4. ogni minuto riprova i documenti in attesa; ogni ora elimina i file dei progetti chiusi
     o inattivi da 30 giorni
Lo stato è tutto nel DB: se il container riparte, il lavoro riprende dal blocco interrotto.
"""
import json
import logging
import os
import shutil
import threading
import time

import anthropic

from database import get_conn, get_user_by_username, cartella_progetto
from services import documenti_progetto as dp
from services import gestione_elenchi
from services.ai_costi import (TrackedClient, verifica_disponibilita, stima_costo_eur,
                               calcola_costo_usd, EUR_PER_USD, chiamate_oggi)
from services.elenchi_prezzi import sembra_elenco_prezzi

log = logging.getLogger("worker_progetti")

GIORNI_INATTIVITA = 30
_evento = threading.Event()
_avviato = False


def sveglia():
    """Chiamata dopo un caricamento: il worker riparte subito invece di attendere."""
    _evento.set()


def avvia_worker():
    global _avviato
    if _avviato:
        return
    _avviato = True
    conn = get_conn()
    try:
        # Lavori interrotti da un riavvio: tornano in coda e ripartono dal blocco successivo
        conn.execute("UPDATE progetto_documenti SET stato='in_coda' WHERE stato='in_elaborazione'")
        conn.commit()
    finally:
        conn.close()
    # Tappe PSC interrotte da un riavvio: tornano in coda
    from services.tappe_psc import ripristina_dopo_riavvio
    ripristina_dopo_riavvio()
    threading.Thread(target=_ciclo, name="worker-progetti", daemon=True).start()
    log.info("Worker progetti avviato")


def _ciclo():
    ultimo_riprova, ultima_pulizia = 0.0, 0.0
    while True:
        lavorato = False
        try:
            lavorato = _passo()
            ora = time.time()
            if ora - ultimo_riprova > 60:
                _riprova_in_attesa()
                ultimo_riprova = ora
            if ora - ultima_pulizia > 3600:
                elimina_file_scaduti()
                ultima_pulizia = ora
        except Exception:
            log.exception("Errore nel ciclo del worker")
            time.sleep(5)
        if not lavorato:
            _evento.wait(5)
            _evento.clear()


# ══════════════════════════════════════════════════════════════════════════════
# Utilità DB
# ══════════════════════════════════════════════════════════════════════════════

def _aggiorna_doc(doc_id: int, **campi):
    campi["updated_at"] = None  # segnaposto, sostituito da CURRENT_TIMESTAMP
    assegnazioni = ", ".join(
        f"{k} = CURRENT_TIMESTAMP" if k == "updated_at" else f"{k} = ?" for k in campi)
    valori = [v for k, v in campi.items() if k != "updated_at"]
    conn = get_conn()
    try:
        conn.execute(f"UPDATE progetto_documenti SET {assegnazioni} WHERE id = ?", (*valori, doc_id))
        conn.commit()
    finally:
        conn.close()


def _proprietario(progetto_id: int) -> dict:
    conn = get_conn()
    try:
        row = conn.execute("SELECT username FROM progetti WHERE id = ?", (progetto_id,)).fetchone()
    finally:
        conn.close()
    return get_user_by_username(row["username"]) if row else None


def _leggi_file(doc) -> bytes:
    if not doc["file_path"] or not os.path.exists(doc["file_path"]):
        return None
    with open(doc["file_path"], "rb") as f:
        return f.read()


def tipo_effettivo(doc) -> str:
    return doc["tipo_csp"] or doc["tipo_ai"] or "altro"


# ══════════════════════════════════════════════════════════════════════════════
# Passo del ciclo
# ══════════════════════════════════════════════════════════════════════════════

def _passo() -> bool:
    conn = get_conn()
    try:
        primo = conn.execute(
            "SELECT progetto_id FROM progetto_documenti WHERE stato='da_classificare' ORDER BY id LIMIT 1"
        ).fetchone()
        if primo:
            gruppo = conn.execute(
                """SELECT * FROM progetto_documenti WHERE stato='da_classificare' AND progetto_id=?
                   ORDER BY id LIMIT 15""", (primo["progetto_id"],)).fetchall()
        else:
            gruppo = None
            prossimo = conn.execute(
                "SELECT * FROM progetto_documenti WHERE stato='in_coda' ORDER BY priorita, id LIMIT 1"
            ).fetchone()
    finally:
        conn.close()

    if gruppo:
        _classifica_gruppo(primo["progetto_id"], [dict(d) for d in gruppo])
        return True
    if prossimo:
        _elabora_documento(dict(prossimo))
        return True
    # Documenti finiti: si passa alle tappe del PSC (una alla volta, in ordine)
    from services import tappe_psc
    tappa = tappe_psc.prossima_tappa_in_coda()
    if tappa:
        tappe_psc.esegui_tappa(tappa)
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# 1. Classificazione
# ══════════════════════════════════════════════════════════════════════════════

def _classifica_gruppo(progetto_id: int, docs: list):
    user = _proprietario(progetto_id)
    if not user:
        return
    da_ai, contenuti = [], {}

    for d in docs:
        contenuto = _leggi_file(d)
        if contenuto is None:
            _aggiorna_doc(d["id"], stato="errore", errore="File non più disponibile")
            continue
        contenuti[d["id"]] = contenuto
        est = d["estensione"]
        if d["tipo_csp"]:                                   # già indicato dal CSP
            _metti_in_coda(d, d["tipo_csp"], contenuto, user)
        elif est in ("jpg", "jpeg", "png"):
            _metti_in_coda(d, "foto", contenuto, user)
        elif est in ("xml", "ods", "xls", "xlsx") and sembra_elenco_prezzi(contenuto, d["nome_file"]):
            _metti_in_coda(d, "elenco_prezzi", contenuto, user)
        else:
            info = dp.analizza_file(contenuto, d["nome_file"])
            miniatura = None
            if est == "pdf" and not info.get("ha_testo"):
                try:
                    miniatura = dp.miniatura_prima_pagina(contenuto)
                except Exception:
                    pass
            da_ai.append({"id": d["id"], "nome_file": d["nome_file"],
                          "anteprima": info.get("anteprima", ""), "miniatura": miniatura, "_doc": d})

    if not da_ai:
        return

    stima = stima_costo_eur(dp.MODELLO, 400 + sum(500 + (900 if x["miniatura"] else 0) for x in da_ai), 300)
    motivo = verifica_disponibilita(user, stima)
    if motivo:
        for x in da_ai:
            _aggiorna_doc(x["id"], stato="in_attesa", motivo_attesa=motivo)
        return

    tipi = {}
    try:
        client = TrackedClient(user, "classificazione_documenti")
        risposta = client.messages.create(
            model=dp.MODELLO, max_tokens=1000,
            system="Classifichi documenti di progetti edilizi italiani. Rispondi SOLO con JSON valido.",
            messages=[{"role": "user", "content": dp.costruisci_richiesta_classificazione(da_ai)}],
        )
        tipi = dp.interpreta_classificazione(risposta.content[0].text)
    except Exception as e:
        log.error(f"Classificazione fallita: {e}")

    for x in da_ai:
        _metti_in_coda(x["_doc"], tipi.get(x["id"], "altro"), contenuti[x["id"]], user)


def _metti_in_coda(doc: dict, tipo: str, contenuto: bytes, user: dict):
    campi = {"priorita": dp.priorita(tipo)}
    if not doc["tipo_csp"]:
        campi["tipo_ai"] = tipo
    info = dp.analizza_file(contenuto, doc["nome_file"])
    campi["pagine"] = info.get("pagine")
    campi["ha_testo"] = None if info.get("ha_testo") is None else int(bool(info["ha_testo"]))
    if tipo == "elenco_prezzi":
        _aggiorna_doc(doc["id"], **campi)
        _elabora_elenco(doc, contenuto, user)
    else:
        _aggiorna_doc(doc["id"], stato="in_coda", **campi)


# ══════════════════════════════════════════════════════════════════════════════
# 2a. Elenchi prezzi (nessuna AI)
# ══════════════════════════════════════════════════════════════════════════════

def _elabora_elenco(doc: dict, contenuto: bytes, user: dict):
    conn = get_conn()
    try:
        vecchio = conn.execute("SELECT elenco_id FROM progetto_documenti WHERE id=?", (doc["id"],)).fetchone()
    finally:
        conn.close()
    if vecchio and vecchio["elenco_id"]:
        gestione_elenchi.elimina_elenco(vecchio["elenco_id"])

    scheda = gestione_elenchi.crea_elenco(
        user["username"], "progetto", doc["nome_file"], doc["nome_file"], contenuto,
        progetto_id=doc["progetto_id"])
    if scheda["stato"] == "pronto":
        _aggiorna_doc(doc["id"], stato="completato", elenco_id=scheda["id"], errore=None,
                      n_blocchi=1, blocchi_completati=1)
        _elimina_file_documento(doc)        # le voci sono nel DB: il file non serve più
    elif scheda["stato"] == "mappatura_richiesta":
        _aggiorna_doc(doc["id"], stato="mappatura_richiesta", elenco_id=scheda["id"])
    else:
        _aggiorna_doc(doc["id"], stato="errore", elenco_id=scheda["id"], errore=scheda["errore"])


# ══════════════════════════════════════════════════════════════════════════════
# 2b. Estrazione AI, blocco per blocco
# ══════════════════════════════════════════════════════════════════════════════

def _elabora_documento(doc: dict):
    tipo = tipo_effettivo(doc)
    user = _proprietario(doc["progetto_id"])
    contenuto = _leggi_file(doc)
    if not user or contenuto is None:
        _aggiorna_doc(doc["id"], stato="errore", errore="File non più disponibile")
        return
    if tipo == "elenco_prezzi":
        _elabora_elenco(doc, contenuto, user)
        return

    _aggiorna_doc(doc["id"], stato="in_elaborazione", errore=None)
    try:
        blocchi = dp.prepara_blocchi(contenuto, doc["nome_file"], tipo)
    except Exception as e:
        _aggiorna_doc(doc["id"], stato="non_supportato", errore=f"Impossibile leggere il file: {e}")
        return
    _aggiorna_doc(doc["id"], n_blocchi=len(blocchi))

    client = TrackedClient(user, "estrazione_progetto")
    costo = doc["costo_eur"] or 0.0
    for i in range(doc["blocchi_completati"] or 0, len(blocchi)):
        b = blocchi[i]
        stima = stima_costo_eur(dp.MODELLO, b["stima_input"] + 1500, dp.OUTPUT_TOKEN_STIMA)
        motivo = verifica_disponibilita(user, stima)
        if motivo:
            _aggiorna_doc(doc["id"], stato="in_attesa", motivo_attesa=motivo)
            return
        try:
            risposta = client.messages.create(
                model=dp.MODELLO, max_tokens=dp.OUTPUT_TOKEN_ESTRAZIONE,
                system=dp.SYSTEM_ESTRAZIONE,
                messages=[{"role": "user",
                           "content": dp.costruisci_richiesta_estrazione(b, doc["nome_file"], tipo)}],
            )
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError) as e:
            # Sovraccarico temporaneo: riprovo più tardi dallo stesso blocco
            log.warning(f"API temporaneamente non disponibile: {e}")
            _aggiorna_doc(doc["id"], stato="in_coda")
            time.sleep(30)
            return
        except anthropic.APIStatusError as e:
            _aggiorna_doc(doc["id"], stato="errore", errore=f"Errore API: {e.message}")
            return

        costo += calcola_costo_usd(dp.MODELLO, risposta.usage) * EUR_PER_USD
        testo = risposta.content[0].text if risposta.content else ""
        dati = dp.pulisci_json(testo) or {"testo_non_strutturato": testo}
        conn = get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO progetto_estrazioni
                   (documento_id, blocco, pagine_da, pagine_a, dati_json) VALUES (?, ?, ?, ?, ?)""",
                (doc["id"], i, b.get("pagine_da"), b.get("pagine_a"),
                 json.dumps(dati, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()
        _aggiorna_doc(doc["id"], blocchi_completati=i + 1, costo_eur=costo)

    _aggiorna_doc(doc["id"], stato="completato", motivo_attesa=None)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Ripresa dei documenti in attesa
# ══════════════════════════════════════════════════════════════════════════════

def _riprova_in_attesa():
    conn = get_conn()
    try:
        righe = conn.execute(
            """SELECT d.id, d.motivo_attesa, d.tipo_ai, d.tipo_csp, p.username
               FROM progetto_documenti d JOIN progetti p ON p.id = d.progetto_id
               WHERE d.stato = 'in_attesa'""").fetchall()
    finally:
        conn.close()
    utenti = {}
    for r in righe:
        user = utenti.get(r["username"]) or get_user_by_username(r["username"])
        utenti[r["username"]] = user
        if not user:
            continue
        # Si riprova solo se c'è di nuovo margine (nuovo giorno, budget aumentato, utente admin)
        if verifica_disponibilita(user, 0.005) is None:
            nuovo_stato = "in_coda" if (r["tipo_ai"] or r["tipo_csp"]) else "da_classificare"
            _aggiorna_doc(r["id"], stato=nuovo_stato, motivo_attesa=None)
            sveglia()


# ══════════════════════════════════════════════════════════════════════════════
# 4. Eliminazione dei file (chiusura progetto o 30 giorni di inattività)
# ══════════════════════════════════════════════════════════════════════════════

def _elimina_file_documento(doc: dict):
    if doc.get("file_path") and os.path.exists(doc["file_path"]):
        os.remove(doc["file_path"])
    _aggiorna_doc(doc["id"], file_path=None)


def elimina_file_progetto(progetto_id: int):
    """Cancella i file originali; i dati estratti restano nel DB."""
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE progetto_documenti SET stato='errore',
                      errore='File eliminato prima dell''elaborazione (progetto chiuso o inattivo)'
               WHERE progetto_id=? AND stato IN ('da_classificare','in_coda','in_attesa')""",
            (progetto_id,))
        conn.execute("UPDATE progetto_documenti SET file_path=NULL WHERE progetto_id=?", (progetto_id,))
        conn.execute("UPDATE progetti SET file_eliminati_at=CURRENT_TIMESTAMP WHERE id=?", (progetto_id,))
        conn.commit()
    finally:
        conn.close()
    shutil.rmtree(cartella_progetto(progetto_id), ignore_errors=True)


def elimina_file_scaduti():
    conn = get_conn()
    try:
        progetti = conn.execute(
            f"""SELECT id FROM progetti WHERE file_eliminati_at IS NULL AND is_esempio = 0
                AND (stato = 'chiuso' OR ultima_attivita < datetime('now', '-{GIORNI_INATTIVITA} days'))"""
        ).fetchall()
    finally:
        conn.close()
    for p in progetti:
        log.info(f"Eliminazione file del progetto {p['id']} (chiuso o inattivo)")
        elimina_file_progetto(p["id"])

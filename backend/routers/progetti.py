"""
routers/progetti.py — Progetti PSC: creazione, caricamento documenti, stato di elaborazione

Ogni progetto è visibile solo all'utente che lo ha creato.
Ogni richiesta sul progetto aggiorna 'ultima_attivita' (conta per i 30 giorni).
"""
import json
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from auth import get_current_user
from database import get_conn, cartella_progetto
from services import documenti_progetto as dp
from services import gestione_elenchi, worker_progetti
from services.ai_costi import stato_budget

router = APIRouter()

MAX_MB_FILE = 50
MAX_MB_PROGETTO = 150
GIORNI_INATTIVITA = worker_progetti.GIORNI_INATTIVITA
GIORNI_PREAVVISO = 3

ETICHETTE_STATO = {
    "da_classificare":     "In attesa di riconoscimento",
    "in_coda":             "In coda",
    "in_elaborazione":     "In elaborazione",
    "completato":          "Completato",
    "in_attesa":           "In attesa",
    "mappatura_richiesta": "Indica le colonne",
    "errore":              "Errore",
    "non_supportato":      "Non supportato",
}


class NuovoProgetto(BaseModel):
    nome: str


class Rinomina(BaseModel):
    nome: str


class CorrezioneTipo(BaseModel):
    tipo: str


class Mappatura(BaseModel):
    riga_intestazione: int
    codice: int
    descrizione: int
    um: int
    prezzo: int
    perc_manodopera: Optional[int] = None


# ══════════════════════════════════════════════════════════════════════════════
# Utilità
# ══════════════════════════════════════════════════════════════════════════════

def _progetto(conn, progetto_id: int, user: dict, tocca: bool = True):
    row = conn.execute("SELECT * FROM progetti WHERE id = ?", (progetto_id,)).fetchone()
    if not row or row["username"] != user["username"]:
        raise HTTPException(404, "Progetto non trovato")
    if tocca:
        conn.execute("UPDATE progetti SET ultima_attivita = CURRENT_TIMESTAMP WHERE id = ?", (progetto_id,))
        conn.commit()
    return row


def _documento(conn, progetto_id: int, doc_id: int):
    row = conn.execute("SELECT * FROM progetto_documenti WHERE id = ? AND progetto_id = ?",
                       (doc_id, progetto_id)).fetchone()
    if not row:
        raise HTTPException(404, "Documento non trovato")
    return row


def _scheda_documento(d) -> dict:
    tipo = d["tipo_csp"] or d["tipo_ai"]
    avanzamento = 0
    if d["stato"] == "completato":
        avanzamento = 100
    elif d["n_blocchi"]:
        avanzamento = int(100 * (d["blocchi_completati"] or 0) / d["n_blocchi"])
    return {
        "id": d["id"],
        "nome_file": d["nome_file"],
        "estensione": d["estensione"],
        "dimensione": d["dimensione"],
        "pagine": d["pagine"],
        "ha_testo": None if d["ha_testo"] is None else bool(d["ha_testo"]),
        "tipo": tipo,
        "tipo_etichetta": dp.etichetta(tipo) if tipo else None,
        "tipo_corretto_da_csp": bool(d["tipo_csp"]),
        "stato": d["stato"],
        "stato_etichetta": ETICHETTE_STATO.get(d["stato"], d["stato"]),
        "motivo_attesa": d["motivo_attesa"],
        "errore": d["errore"],
        "n_blocchi": d["n_blocchi"],
        "blocchi_completati": d["blocchi_completati"],
        "avanzamento": avanzamento,
        "elenco_id": d["elenco_id"],
        "file_disponibile": bool(d["file_path"]),
        "costo_eur": round(d["costo_eur"] or 0, 4),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Progetti
# ══════════════════════════════════════════════════════════════════════════════

@router.get("")
def elenco_progetti(user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT p.*,
                      (SELECT COUNT(*) FROM progetto_documenti d WHERE d.progetto_id = p.id) AS n_documenti,
                      (SELECT COUNT(*) FROM progetto_documenti d WHERE d.progetto_id = p.id
                              AND d.stato = 'completato') AS n_completati,
                      julianday('now') - julianday(p.ultima_attivita) AS giorni_inattivita
               FROM progetti p WHERE p.username = ? ORDER BY p.ultima_attivita DESC""",
            (user["username"],)).fetchall()
    finally:
        conn.close()
    return [{
        "id": r["id"], "nome": r["nome"], "stato": r["stato"], "is_esempio": bool(r["is_esempio"]),
        "created_at": r["created_at"], "ultima_attivita": r["ultima_attivita"],
        "n_documenti": r["n_documenti"], "n_completati": r["n_completati"],
        "file_eliminati": bool(r["file_eliminati_at"]),
        # Preavviso: l'apertura del progetto azzera il conteggio
        "giorni_alla_eliminazione": (
            None if r["file_eliminati_at"] or r["is_esempio"] or r["stato"] == "chiuso"
            else max(0, int(GIORNI_INATTIVITA - (r["giorni_inattivita"] or 0)))),
        "preavviso_eliminazione": (
            not r["file_eliminati_at"] and not r["is_esempio"] and r["stato"] == "aperto"
            and (r["giorni_inattivita"] or 0) >= GIORNI_INATTIVITA - GIORNI_PREAVVISO),
    } for r in rows]


@router.post("")
def crea_progetto(body: NuovoProgetto, user: dict = Depends(get_current_user)):
    nome = body.nome.strip()
    if not nome:
        raise HTTPException(400, "Indica un nome per il progetto")
    conn = get_conn()
    try:
        cur = conn.execute("INSERT INTO progetti (username, nome) VALUES (?, ?)", (user["username"], nome))
        conn.commit()
        return {"id": cur.lastrowid, "nome": nome}
    finally:
        conn.close()


@router.get("/{progetto_id}")
def dettaglio_progetto(progetto_id: int, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        p = _progetto(conn, progetto_id, user)
        docs = conn.execute(
            "SELECT * FROM progetto_documenti WHERE progetto_id = ? ORDER BY priorita, id",
            (progetto_id,)).fetchall()
    finally:
        conn.close()

    documenti = [_scheda_documento(d) for d in docs]
    budget = stato_budget(user)
    avvisi = []
    in_attesa_budget = [d for d in documenti if d["stato"] == "in_attesa" and d["motivo_attesa"] == "budget"]
    in_attesa_giorno = [d for d in documenti if d["stato"] == "in_attesa"
                        and d["motivo_attesa"] == "limite_giornaliero"]
    if in_attesa_budget:
        n = len(in_attesa_budget)
        quanti = "1 documento, che resta" if n == 1 else f"{n} documenti, che restano"
        avvisi.append({"tipo": "demo", "testo":
            f"Versione demo limitata: il budget disponibile non basta per elaborare "
            f"{quanti} in attesa ma comunque visibili. I documenti più importanti "
            f"(contratto, relazione tecnica, computo) vengono elaborati per primi."})
    if in_attesa_giorno:
        n = len(in_attesa_giorno)
        quanti = "1 documento riprenderà" if n == 1 else f"{n} documenti riprenderanno"
        avvisi.append({"tipo": "limite", "testo":
            f"Raggiunto il limite giornaliero di chiamate: {quanti} automaticamente domani."})
    if p["file_eliminati_at"]:
        avvisi.append({"tipo": "info", "testo":
            "I file originali di questo progetto sono stati eliminati; i dati estratti restano disponibili."})
    elif p["stato"] == "aperto" and not p["is_esempio"] and documenti:
        avvisi.append({"tipo": "info", "testo":
            f"I file originali vengono eliminati alla chiusura del progetto o dopo "
            f"{GIORNI_INATTIVITA} giorni senza attività. I dati estratti restano."})

    return {
        "id": p["id"], "nome": p["nome"], "stato": p["stato"], "is_esempio": bool(p["is_esempio"]),
        "created_at": p["created_at"], "file_eliminati": bool(p["file_eliminati_at"]),
        "documenti": documenti,
        "in_lavorazione": any(d["stato"] in ("da_classificare", "in_coda", "in_elaborazione")
                              for d in documenti),
        "avvisi": avvisi,
        "budget": budget,
        "limiti": {"mb_file": MAX_MB_FILE, "mb_progetto": MAX_MB_PROGETTO},
        "tipi": [{"codice": k, "etichetta": v[0]} for k, v in dp.TIPI.items()],
    }


@router.patch("/{progetto_id}")
def rinomina_progetto(progetto_id: int, body: Rinomina, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        _progetto(conn, progetto_id, user)
        conn.execute("UPDATE progetti SET nome = ? WHERE id = ?", (body.nome.strip(), progetto_id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/{progetto_id}")
def elimina_progetto(progetto_id: int, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        _progetto(conn, progetto_id, user, tocca=False)
        elenchi = conn.execute("SELECT id FROM elenchi_prezzi WHERE progetto_id = ?", (progetto_id,)).fetchall()
        conn.execute("""DELETE FROM progetto_estrazioni WHERE documento_id IN
                        (SELECT id FROM progetto_documenti WHERE progetto_id = ?)""", (progetto_id,))
        conn.execute("DELETE FROM progetto_documenti WHERE progetto_id = ?", (progetto_id,))
        # dati dei blocchi 3-5 collegati al progetto
        for tabella in ("progetto_tappe", "progetto_domande", "progetto_costi", "progetto_presidi", "progetto_schemi"):
            conn.execute(f"DELETE FROM {tabella} WHERE progetto_id = ?", (progetto_id,))
        conn.execute("DELETE FROM progetti WHERE id = ?", (progetto_id,))
        conn.commit()
    finally:
        conn.close()
    for e in elenchi:
        gestione_elenchi.elimina_elenco(e["id"])
    worker_progetti.elimina_file_progetto(progetto_id)
    import shutil
    from database import cartella_schemi
    shutil.rmtree(cartella_schemi(progetto_id), ignore_errors=True)
    return {"ok": True}


@router.post("/{progetto_id}/chiudi")
def chiudi_progetto(progetto_id: int, user: dict = Depends(get_current_user)):
    """Chiusura (usata dall'export finale del blocco 6): elimina subito i file originali."""
    conn = get_conn()
    try:
        _progetto(conn, progetto_id, user)
        conn.execute("UPDATE progetti SET stato = 'chiuso' WHERE id = ?", (progetto_id,))
        conn.commit()
    finally:
        conn.close()
    worker_progetti.elimina_file_progetto(progetto_id)
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
# Documenti
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{progetto_id}/documenti")
async def carica_documenti(progetto_id: int, files: List[UploadFile] = File(...),
                           user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        p = _progetto(conn, progetto_id, user)
        if p["stato"] == "chiuso":
            raise HTTPException(400, "Il progetto è chiuso: non è possibile caricare altri documenti")
        occupato = conn.execute(
            """SELECT COALESCE(SUM(dimensione), 0) AS tot FROM progetto_documenti
               WHERE progetto_id = ? AND file_path IS NOT NULL""", (progetto_id,)).fetchone()["tot"]
        nomi_esistenti = {r["nome_file"] for r in conn.execute(
            "SELECT nome_file FROM progetto_documenti WHERE progetto_id = ?", (progetto_id,)).fetchall()}
    finally:
        conn.close()

    cartella = cartella_progetto(progetto_id)
    accettati, rifiutati = [], []
    for f in files:
        nome = os.path.basename(f.filename or "file")
        est = nome.lower().rsplit(".", 1)[-1] if "." in nome else ""
        if est == "dwg":
            rifiutati.append({"file": nome, "motivo": "File DWG non supportati: esportali in PDF da AutoCAD"})
            continue
        if est not in dp.ESTENSIONI_AMMESSE:
            rifiutati.append({"file": nome, "motivo": f"Formato .{est} non supportato"})
            continue
        if nome in nomi_esistenti:
            rifiutati.append({"file": nome, "motivo": "Un documento con lo stesso nome è già nel progetto"})
            continue
        contenuto = await f.read()
        mb = len(contenuto) / 1024 / 1024
        if mb > MAX_MB_FILE:
            rifiutati.append({"file": nome, "motivo": f"File di {mb:.0f} MB: il limite è {MAX_MB_FILE} MB"})
            continue
        if (occupato + len(contenuto)) / 1024 / 1024 > MAX_MB_PROGETTO:
            rifiutati.append({"file": nome, "motivo":
                f"Superato il limite complessivo di {MAX_MB_PROGETTO} MB per progetto"})
            continue
        path = os.path.join(cartella, f"{uuid.uuid4().hex[:10]}_{nome}")
        with open(path, "wb") as out:
            out.write(contenuto)
        occupato += len(contenuto)
        nomi_esistenti.add(nome)
        accettati.append((nome, est, len(contenuto), path))

    if accettati:
        conn = get_conn()
        try:
            conn.executemany(
                """INSERT INTO progetto_documenti (progetto_id, nome_file, estensione, dimensione, file_path)
                   VALUES (?, ?, ?, ?, ?)""",
                [(progetto_id, n, e, d, pth) for n, e, d, pth in accettati])
            conn.commit()
        finally:
            conn.close()
        worker_progetti.sveglia()

    return {"caricati": [a[0] for a in accettati], "rifiutati": rifiutati}


@router.patch("/{progetto_id}/documenti/{doc_id}")
def correggi_tipo(progetto_id: int, doc_id: int, body: CorrezioneTipo, user: dict = Depends(get_current_user)):
    if body.tipo not in dp.TIPI:
        raise HTTPException(400, "Tipo di documento non valido")
    conn = get_conn()
    try:
        _progetto(conn, progetto_id, user)
        d = _documento(conn, progetto_id, doc_id)
        tipo_prima = d["tipo_csp"] or d["tipo_ai"]
        conn.execute("UPDATE progetto_documenti SET tipo_csp = ?, priorita = ? WHERE id = ?",
                     (body.tipo, dp.priorita(body.tipo), doc_id))
        conn.commit()
    finally:
        conn.close()

    # Se il documento era già stato elaborato con un tipo diverso, conviene rielaborarlo
    # (costa una nuova estrazione: lo decide il CSP con il pulsante "Rielabora")
    rielaborare = (d["stato"] in ("completato", "errore", "mappatura_richiesta")
                   and tipo_prima != body.tipo and bool(d["file_path"]))
    if d["stato"] in ("in_coda", "in_attesa"):
        worker_progetti.sveglia()
    return {"ok": True, "rielaborazione_consigliata": rielaborare}


@router.post("/{progetto_id}/documenti/{doc_id}/rielabora")
def rielabora(progetto_id: int, doc_id: int, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        _progetto(conn, progetto_id, user)
        d = _documento(conn, progetto_id, doc_id)
        if not d["file_path"]:
            raise HTTPException(400, "Il file originale non è più disponibile")
        conn.execute("DELETE FROM progetto_estrazioni WHERE documento_id = ?", (doc_id,))
        conn.execute(
            """UPDATE progetto_documenti SET stato = 'in_coda', blocchi_completati = 0, n_blocchi = 0,
                      errore = NULL, motivo_attesa = NULL WHERE id = ?""", (doc_id,))
        conn.commit()
    finally:
        conn.close()
    worker_progetti.sveglia()
    return {"ok": True}


@router.delete("/{progetto_id}/documenti/{doc_id}")
def elimina_documento(progetto_id: int, doc_id: int, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        _progetto(conn, progetto_id, user)
        d = _documento(conn, progetto_id, doc_id)
        conn.execute("DELETE FROM progetto_estrazioni WHERE documento_id = ?", (doc_id,))
        conn.execute("DELETE FROM progetto_documenti WHERE id = ?", (doc_id,))
        conn.commit()
    finally:
        conn.close()
    if d["file_path"] and os.path.exists(d["file_path"]):
        os.remove(d["file_path"])
    if d["elenco_id"]:
        gestione_elenchi.elimina_elenco(d["elenco_id"])
    return {"ok": True}


@router.get("/{progetto_id}/documenti/{doc_id}/dati")
def dati_estratti(progetto_id: int, doc_id: int, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        _progetto(conn, progetto_id, user)
        d = _documento(conn, progetto_id, doc_id)
        blocchi = conn.execute(
            "SELECT blocco, pagine_da, pagine_a, dati_json FROM progetto_estrazioni WHERE documento_id = ? ORDER BY blocco",
            (doc_id,)).fetchall()
        elenco = None
        if d["elenco_id"]:
            elenco = gestione_elenchi.leggi_scheda_elenco(conn, d["elenco_id"])
    finally:
        conn.close()
    return {
        "documento": _scheda_documento(d),
        "blocchi": [{"blocco": b["blocco"], "pagine_da": b["pagine_da"], "pagine_a": b["pagine_a"],
                     "dati": json.loads(b["dati_json"]) if b["dati_json"] else None} for b in blocchi],
        "elenco": elenco,
    }


@router.post("/{progetto_id}/documenti/{doc_id}/mappatura")
def mappatura_elenco(progetto_id: int, doc_id: int, body: Mappatura, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        _progetto(conn, progetto_id, user)
        d = _documento(conn, progetto_id, doc_id)
    finally:
        conn.close()
    if not d["elenco_id"]:
        raise HTTPException(400, "Questo documento non è un elenco prezzi")
    try:
        scheda = gestione_elenchi.applica_mappatura(d["elenco_id"], body.dict())
    except Exception as e:
        raise HTTPException(400, str(e))
    worker_progetti._aggiorna_doc(doc_id, stato="completato", errore=None, n_blocchi=1, blocchi_completati=1)
    worker_progetti._elimina_file_documento(dict(d))
    return scheda

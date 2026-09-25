"""
routers/tappe.py — Tappe del PSC e questionario del sopralluogo (blocco 3)

Montato con prefisso /api/progetti (stesso proprietario e stessi controlli dei progetti).
Le generazioni avvengono nel worker in background: gli endpoint accodano e restituiscono subito.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from database import get_conn
from routers.progetti import _progetto
from services import tappe_definizioni as td
from services import tappe_psc, worker_progetti
from services.ai_costi import assicura_budget, stato_budget

router = APIRouter()


class RichiestaGenera(BaseModel):
    nota: Optional[str] = None


class Sezione(BaseModel):
    id: str
    tipo: str
    testo: Optional[str] = None
    righe: Optional[List[List[str]]] = None


class ModificaTappa(BaseModel):
    sezioni: List[Sezione]


class DatiCSP(BaseModel):
    data_inizio_lavori: Optional[str] = None


class Risposta(BaseModel):
    risposta: str


def _verifica_progetto(progetto_id: int, user: dict):
    conn = get_conn()
    try:
        p = _progetto(conn, progetto_id, user)
    finally:
        conn.close()
    return dict(p)


def _stato_documenti(progetto_id: int) -> dict:
    conn = get_conn()
    try:
        r = conn.execute(
            """SELECT SUM(stato IN ('da_classificare','in_coda','in_elaborazione')) AS in_lavorazione,
                      SUM(stato = 'completato' AND COALESCE(tipo_csp, tipo_ai) != 'elenco_prezzi') AS completati
               FROM progetto_documenti WHERE progetto_id = ?""", (progetto_id,)).fetchone()
    finally:
        conn.close()
    return {"in_lavorazione": r["in_lavorazione"] or 0, "completati": r["completati"] or 0}


def _scheda(t: dict) -> dict:
    d = td.definizione(t["numero"])
    c = tappe_psc.contenuto(t)
    return {
        "numero": t["numero"], "codice": d["codice"], "titolo": d["titolo"], "obiettivo": d["obiettivo"],
        "stato": t["stato"], "contenuto": c,
        "modificata_a_mano": bool(t["modificata_a_mano"]),
        "da_ricontrollare": bool(t["da_ricontrollare"]),
        "da_aggiornare": bool(t["da_aggiornare"]),
        "nota_csp": t["nota_csp"], "errore": t["errore"],
        "costo_eur": round(t["costo_eur"] or 0, 4), "generata_at": t["generata_at"],
        "n_da_verificare": td.conta_da_verificare(c) if c else 0,
    }


def _controlla_prerequisiti(progetto_id: int):
    doc = _stato_documenti(progetto_id)
    if doc["in_lavorazione"]:
        raise HTTPException(409, "Attendi la fine dell'elaborazione dei documenti prima di generare le tappe")
    if not doc["completati"]:
        raise HTTPException(400, "Carica ed elabora almeno un documento del progetto prima di generare le tappe")


# ══════════════════════════════════════════════════════════════════════════════
# Tappe
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{progetto_id}/tappe")
def elenco_tappe(progetto_id: int, user: dict = Depends(get_current_user)):
    p = _verifica_progetto(progetto_id, user)
    tappe = [_scheda(t) for t in tappe_psc.leggi_tappe(progetto_id)]
    doc = _stato_documenti(progetto_id)
    return {
        "tappe": tappe,
        "bozza": {"stato": p.get("bozza_stato"), "messaggio": p.get("bozza_messaggio")},
        "in_corso": any(t["stato"] in tappe_psc.STATI_ATTIVI for t in tappe),
        "da_aggiornare": tappe_psc.tappe_da_aggiornare(progetto_id),
        "data_inizio_lavori": p.get("data_inizio_lavori"),
        "documenti": doc,
        "budget": stato_budget(user),
    }


@router.get("/{progetto_id}/tappe/stima")
def stima(progetto_id: int, numeri: str = "", user: dict = Depends(get_current_user)):
    """Stima in euro della generazione delle tappe indicate (es. numeri=1,2,3)."""
    _verifica_progetto(progetto_id, user)
    try:
        elenco = [int(x) for x in numeri.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "Parametro numeri non valido")
    elenco = [n for n in elenco if 1 <= n <= td.NUMERO_TAPPE]
    return {"numeri": elenco, "stima_eur": tappe_psc.stima_generazione(progetto_id, elenco),
            "budget": stato_budget(user)}


@router.post("/{progetto_id}/tappe/bozza")
def genera_bozza(progetto_id: int, user: dict = Depends(get_current_user)):
    _verifica_progetto(progetto_id, user)
    _controlla_prerequisiti(progetto_id)
    # Serve almeno il budget per la prima tappa: il resto si verifica tappa per tappa
    assicura_budget(user, tappe_psc.stima_generazione(progetto_id, [1]))
    esito = tappe_psc.avvia_bozza(progetto_id)
    worker_progetti.sveglia()
    return esito


@router.post("/{progetto_id}/tappe/aggiorna")
def aggiorna_tappe(progetto_id: int, user: dict = Depends(get_current_user)):
    """Cascata raccolta: rigenera in ordine tutte le tappe "da aggiornare" (tappa 12 esclusa)."""
    _verifica_progetto(progetto_id, user)
    _controlla_prerequisiti(progetto_id)
    numeri = tappe_psc.tappe_da_aggiornare(progetto_id)
    if not numeri:
        raise HTTPException(400, "Nessuna tappa da aggiornare")
    assicura_budget(user, tappe_psc.stima_generazione(progetto_id, numeri[:1]))
    accodate = tappe_psc.aggiorna_successive(progetto_id)
    worker_progetti.sveglia()
    return {"accodate": accodate}


@router.post("/{progetto_id}/tappe/interrompi")
def interrompi(progetto_id: int, user: dict = Depends(get_current_user)):
    _verifica_progetto(progetto_id, user)
    tappe_psc._interrompi_catena(progetto_id, 1, "Generazione interrotta dal CSP.")
    return {"ok": True}


@router.post("/{progetto_id}/tappe/{numero}/genera")
def genera_tappa(progetto_id: int, numero: int, body: RichiestaGenera = None,
                 user: dict = Depends(get_current_user)):
    if not 1 <= numero <= td.NUMERO_TAPPE:
        raise HTTPException(404, "Tappa inesistente")
    _verifica_progetto(progetto_id, user)
    _controlla_prerequisiti(progetto_id)
    tappe = {t["numero"]: t for t in tappe_psc.leggi_tappe(progetto_id)}
    if tappe[numero]["stato"] in tappe_psc.STATI_ATTIVI:
        raise HTTPException(409, "La tappa è già in generazione")
    mancanti = [n for n in range(1, numero)
                if not tappe[n]["contenuto_json"] and tappe[n]["stato"] not in tappe_psc.STATI_ATTIVI]
    if mancanti:
        raise HTTPException(400, f"Genera prima la tappa {mancanti[0]}: ogni tappa si basa sulle precedenti")
    assicura_budget(user, tappe_psc.stima_generazione(progetto_id, [numero]))
    tappe_psc.accoda_tappa(progetto_id, numero, (body.nota if body else None) or "")
    worker_progetti.sveglia()
    return {"ok": True}


@router.put("/{progetto_id}/tappe/{numero}")
def salva_tappa(progetto_id: int, numero: int, body: ModificaTappa, user: dict = Depends(get_current_user)):
    if not 1 <= numero <= td.NUMERO_TAPPE:
        raise HTTPException(404, "Tappa inesistente")
    _verifica_progetto(progetto_id, user)
    tappe = {t["numero"]: t for t in tappe_psc.leggi_tappe(progetto_id)}
    if tappe[numero]["stato"] in tappe_psc.STATI_ATTIVI:
        raise HTTPException(409, "La tappa è in generazione: attendi la fine prima di modificarla")
    precedente = tappe_psc.contenuto(tappe[numero]) or {}
    dati = {
        "sezioni": [s.dict() for s in body.sezioni],
        # gli elenchi da_verificare / domande restano quelli dell'ultima generazione
        "da_verificare": precedente.get("da_verificare", []),
        "domande_sopralluogo": precedente.get("domande_sopralluogo", []),
    }
    esito = tappe_psc.salva_modifica_csp(progetto_id, numero, dati)
    if esito["rigenerate"]:
        worker_progetti.sveglia()
    return esito


@router.post("/{progetto_id}/tappe/{numero}/verificata")
def verificata(progetto_id: int, numero: int, user: dict = Depends(get_current_user)):
    _verifica_progetto(progetto_id, user)
    tappe_psc.segna_verificata(progetto_id, numero)
    return {"ok": True}


@router.patch("/{progetto_id}/dati-csp")
def dati_csp(progetto_id: int, body: DatiCSP, user: dict = Depends(get_current_user)):
    _verifica_progetto(progetto_id, user)
    tappe_psc._aggiorna_progetto(progetto_id, data_inizio_lavori=(body.data_inizio_lavori or None))
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
# Questionario del sopralluogo
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{progetto_id}/questionario")
def questionario(progetto_id: int, user: dict = Depends(get_current_user)):
    p = _verifica_progetto(progetto_id, user)
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM progetto_domande WHERE progetto_id = ? ORDER BY tappa, origine, id",
            (progetto_id,)).fetchall()
    finally:
        conn.close()
    gruppi = {}
    for r in rows:
        gruppi.setdefault(r["tappa"], []).append({
            "id": r["id"], "origine": r["origine"], "testo": r["testo"],
            "risposta": r["risposta"] or "", "stato": r["stato"],
        })
    return {
        "progetto": p["nome"],
        "gruppi": [{"tappa": n, "titolo": td.definizione(n)["titolo"], "domande": gruppi[n]}
                   for n in sorted(gruppi)],
        "da_applicare": sum(1 for r in rows if r["stato"] == "risposta"),
        "aperte": sum(1 for r in rows if r["stato"] == "aperta"),
    }


@router.patch("/{progetto_id}/questionario/{domanda_id}")
def rispondi(progetto_id: int, domanda_id: int, body: Risposta, user: dict = Depends(get_current_user)):
    _verifica_progetto(progetto_id, user)
    testo = body.risposta.strip()
    conn = get_conn()
    try:
        r = conn.execute("SELECT id FROM progetto_domande WHERE id = ? AND progetto_id = ?",
                         (domanda_id, progetto_id)).fetchone()
        if not r:
            raise HTTPException(404, "Domanda non trovata")
        conn.execute(
            """UPDATE progetto_domande SET risposta = ?, stato = ?, risposta_at = CURRENT_TIMESTAMP
               WHERE id = ?""", (testo or None, "risposta" if testo else "aperta", domanda_id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.post("/{progetto_id}/questionario/applica")
def applica(progetto_id: int, user: dict = Depends(get_current_user)):
    _verifica_progetto(progetto_id, user)
    esito = tappe_psc.applica_risposte(progetto_id)
    if esito["rigenerate"]:
        worker_progetti.sveglia()
    return esito

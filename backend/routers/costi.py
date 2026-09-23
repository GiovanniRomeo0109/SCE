"""
routers/costi.py — Costi della sicurezza, uomini-giorno ed esportazioni Excel (blocco 4)
Montato con prefisso /api/progetti.
"""
import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from auth import get_current_user
from database import get_conn
from routers.documents import _utente_da_richiesta
from routers.progetti import _progetto
from services import costi_sicurezza as cs
from services import uomini_giorno as ugm
from services import export_excel, worker_progetti

router = APIRouter()
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ModificaRiga(BaseModel):
    quantita: Optional[float] = None
    prezzo: Optional[float] = None
    voce_id: Optional[int] = None          # voce scelta dal CSP tra quelle degli elenchi
    azzera_quantita: bool = False          # torna alla quantità proposta dalla tappa 11


class DatiUG(BaseModel):
    importo_lavori: Optional[float] = None
    incidenza_manodopera: Optional[float] = None
    costo_giornaliero: Optional[float] = None
    ug_scelta: Optional[str] = None
    campi: list = []                        # quali campi aggiornare (permette di azzerarli)


def _verifica(progetto_id, user):
    conn = get_conn()
    try:
        return dict(_progetto(conn, progetto_id, user))
    finally:
        conn.close()


def _riga(progetto_id, riga_id):
    conn = get_conn()
    try:
        r = conn.execute("SELECT * FROM progetto_costi WHERE id=? AND progetto_id=?", (riga_id, progetto_id)).fetchone()
    finally:
        conn.close()
    if not r:
        raise HTTPException(404, "Riga non trovata")
    return dict(r)


def _nome_file(nome, suffisso):
    base = re.sub(r"[^A-Za-z0-9]+", "_", nome).strip("_")[:40] or "progetto"
    return f"{suffisso}_{base}.xlsx"


# ── Costi ─────────────────────────────────────────────────────────────────────

@router.get("/{progetto_id}/costi")
def costi(progetto_id: int, user: dict = Depends(get_current_user)):
    p = _verifica(progetto_id, user)
    elenco = cs.righe(progetto_id)
    return {
        "righe": elenco, "totali": cs.totali(elenco),
        "in_abbinamento": bool(p.get("costi_da_abbinare")), "messaggio": p.get("costi_messaggio"),
        "elenchi": cs.elenchi_disponibili(progetto_id, user["username"]),
    }


@router.post("/{progetto_id}/costi/aggiorna")
def aggiorna(progetto_id: int, user: dict = Depends(get_current_user)):
    """Riallinea alla tappa 11 e riprova l'abbinamento delle misure senza voce."""
    _verifica(progetto_id, user)
    cs.sincronizza(progetto_id)
    conn = get_conn()
    try:
        conn.execute("""UPDATE progetto_costi SET stato='da_abbinare' WHERE progetto_id=? AND attiva=1
                        AND stato='da_definire'""", (progetto_id,))
        n = conn.execute("SELECT COUNT(*) n FROM progetto_costi WHERE progetto_id=? AND attiva=1 AND stato='da_abbinare'",
                         (progetto_id,)).fetchone()["n"]
        conn.execute("UPDATE progetti SET costi_da_abbinare=?, costi_messaggio=NULL WHERE id=?", (1 if n else 0, progetto_id))
        conn.commit()
    finally:
        conn.close()
    worker_progetti.sveglia()
    return {"da_abbinare": n}


@router.get("/{progetto_id}/costi/cerca-voci")
def cerca(progetto_id: int, q: str = "", um: str = "", user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    return cs.cerca_voci(cs.elenchi_disponibili(progetto_id, user["username"]), q, um, per_livello=15)


@router.patch("/{progetto_id}/costi/{riga_id}")
def modifica(progetto_id: int, riga_id: int, body: ModificaRiga, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    r = _riga(progetto_id, riga_id)
    campi = {}
    if body.voce_id is not None:
        elenchi = {e["id"]: e for e in cs.elenchi_disponibili(progetto_id, user["username"])}
        conn = get_conn()
        try:
            v = conn.execute("SELECT * FROM elenchi_prezzi_voci WHERE id=?", (body.voce_id,)).fetchone()
        finally:
            conn.close()
        if not v or v["elenco_id"] not in elenchi:
            raise HTTPException(404, "Voce non trovata negli elenchi disponibili")
        e = elenchi[v["elenco_id"]]
        campi.update(stato="manuale", livello=e["livello"], elenco_id=e["id"], elenco_nome=e["nome"],
                     codice=v["codice"], descrizione_voce=v["descrizione"], um_voce=v["um"], prezzo=v["prezzo"],
                     nota="Voce scelta dal CSP")
    if body.prezzo is not None:
        campi["prezzo"] = body.prezzo
        if body.voce_id is None:
            campi.update(stato="manuale", nota="Prezzo inserito dal CSP")
            if not r["codice"]:
                campi.update(livello="manuale", descrizione_voce="Prezzo inserito dal CSP")
    if body.quantita is not None:
        campi.update(quantita=body.quantita, quantita_csp=1)
    if body.azzera_quantita:
        campi.update(quantita=r["quantita_tappa"], quantita_csp=0)
    if campi:
        conn = get_conn()
        try:
            conn.execute(f"UPDATE progetto_costi SET {', '.join(k + '=?' for k in campi)}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                         (*campi.values(), riga_id))
            conn.commit()
        finally:
            conn.close()
    return {"ok": True}


# ── Uomini-giorno ─────────────────────────────────────────────────────────────

@router.get("/{progetto_id}/uomini-giorno")
def uomini_giorno(progetto_id: int, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    return ugm.calcola(progetto_id, user["username"])


@router.patch("/{progetto_id}/uomini-giorno")
def salva_ug(progetto_id: int, body: DatiUG, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    ammessi = {"importo_lavori", "incidenza_manodopera", "costo_giornaliero", "ug_scelta"}
    campi = {k: getattr(body, k) for k in body.campi if k in ammessi}
    if "ug_scelta" in campi and campi["ug_scelta"] not in (None, "cronoprogramma", "incidenza"):
        raise HTTPException(400, "Scelta non valida")
    if "incidenza_manodopera" in campi and campi["incidenza_manodopera"] is not None \
            and not 0 < campi["incidenza_manodopera"] <= 100:
        raise HTTPException(400, "L'incidenza deve essere una percentuale tra 0 e 100")
    if campi:
        conn = get_conn()
        try:
            conn.execute(f"UPDATE progetti SET {', '.join(k + '=?' for k in campi)} WHERE id=?",
                         (*campi.values(), progetto_id))
            conn.commit()
        finally:
            conn.close()
    return ugm.calcola(progetto_id, user["username"])


# ── Excel ─────────────────────────────────────────────────────────────────────

@router.get("/{progetto_id}/export/cronoprogramma.xlsx")
def excel_cronoprogramma(progetto_id: int, request: Request, token: Optional[str] = None):
    user = _utente_da_richiesta(request, token)
    p = _verifica(progetto_id, user)
    dati = export_excel.cronoprogramma_xlsx(p["nome"], ugm.calcola(progetto_id, user["username"]))
    return Response(dati, media_type=MIME_XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{_nome_file(p["nome"], "Cronoprogramma")}"'})


@router.get("/{progetto_id}/export/costi.xlsx")
def excel_costi(progetto_id: int, request: Request, token: Optional[str] = None):
    user = _utente_da_richiesta(request, token)
    p = _verifica(progetto_id, user)
    elenco = cs.righe(progetto_id)
    conn = get_conn()
    try:
        t = conn.execute("SELECT contenuto_json FROM progetto_tappe WHERE progetto_id=? AND numero=11", (progetto_id,)).fetchone()
    finally:
        conn.close()
    escluse = []
    if t and t["contenuto_json"]:
        sez = next((s for s in json.loads(t["contenuto_json"])["sezioni"] if s["id"] == "costi_ordinari"), None)
        escluse = [(r[0], r[1] if len(r) > 1 else "") for r in (sez or {}).get("righe", [])]
    dati = export_excel.costi_xlsx(p["nome"], elenco, cs.totali(elenco), escluse)
    return Response(dati, media_type=MIME_XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{_nome_file(p["nome"], "Costi_sicurezza")}"'})

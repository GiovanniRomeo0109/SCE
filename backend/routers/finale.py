"""
routers/finale.py — Documento finale del PSC (blocco 6)

/api/studio ...                       dati e logo dello studio (uno per account)
/api/progetti/{id}/checklist ...      checklist A–M compilata dal CSP
/api/progetti/{id}/export-info        revisione proposta, coordinatori, stato della checklist
/api/progetti/{id}/export-psc         genera il DOCX (bloccato se la checklist non è completa)
/api/progetti/{id}/pubblica-esempio   solo amministratore
/api/progetti/{id}/tappe/manuale      "Compila senza documenti": 12 tappe vuote da compilare a mano
"""
import os
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from auth import get_current_user
from database import get_conn, cartella_studio
from routers.anagrafica import salva_immagine
from routers.documents import _utente_da_richiesta
from routers.progetti import _progetto
from services import checklist as ck
from services import esempio, psc_docx
from services import tappe_definizioni as td
from services import tappe_psc

router_studio = APIRouter()
router = APIRouter()

CAMPI_STUDIO = ("nome", "indirizzo", "piva", "telefono", "email", "pec")


# ══════════════════════════════════════════════════════════════════════════════
# Studio (uno per account)
# ══════════════════════════════════════════════════════════════════════════════

class Studio(BaseModel):
    nome: Optional[str] = None
    indirizzo: Optional[str] = None
    piva: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    pec: Optional[str] = None


def leggi_studio(username: str) -> dict:
    conn = get_conn()
    try:
        r = conn.execute("SELECT * FROM studio_profilo WHERE username = ?", (username,)).fetchone()
    finally:
        conn.close()
    d = dict(r) if r else {"username": username}
    d["ha_logo"] = bool(d.get("logo_path") and os.path.exists(d["logo_path"]))
    return d


def _pubblico(d):
    return {k: d.get(k) for k in CAMPI_STUDIO + ("ha_logo",)}


@router_studio.get("")
def get_studio(user: dict = Depends(get_current_user)):
    return _pubblico(leggi_studio(user["username"]))


@router_studio.put("")
def put_studio(body: Studio, user: dict = Depends(get_current_user)):
    dati = {k: (getattr(body, k) or "").strip() or None for k in CAMPI_STUDIO}
    conn = get_conn()
    try:
        conn.execute(
            f"""INSERT INTO studio_profilo (username, {', '.join(CAMPI_STUDIO)}) VALUES (?, {', '.join('?' * len(CAMPI_STUDIO))})
                ON CONFLICT(username) DO UPDATE SET {', '.join(f'{k}=excluded.{k}' for k in CAMPI_STUDIO)},
                updated_at=CURRENT_TIMESTAMP""", (user["username"], *dati.values()))
        conn.commit()
    finally:
        conn.close()
    return _pubblico(leggi_studio(user["username"]))


@router_studio.post("/logo")
async def carica_logo(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    attuale = leggi_studio(user["username"])
    path = salva_immagine(await file.read(), cartella_studio(user["username"]), "logo", attuale.get("logo_path"))
    conn = get_conn()
    try:
        conn.execute("""INSERT INTO studio_profilo (username, logo_path) VALUES (?, ?)
                        ON CONFLICT(username) DO UPDATE SET logo_path=excluded.logo_path""", (user["username"], path))
        conn.commit()
    finally:
        conn.close()
    return _pubblico(leggi_studio(user["username"]))


@router_studio.delete("/logo")
def elimina_logo(user: dict = Depends(get_current_user)):
    attuale = leggi_studio(user["username"])
    if attuale.get("logo_path") and os.path.exists(attuale["logo_path"]):
        os.remove(attuale["logo_path"])
    conn = get_conn()
    try:
        conn.execute("UPDATE studio_profilo SET logo_path=NULL WHERE username=?", (user["username"],))
        conn.commit()
    finally:
        conn.close()
    return _pubblico(leggi_studio(user["username"]))


@router_studio.get("/logo.png")
def immagine_logo(request: Request, token: Optional[str] = None):
    user = _utente_da_richiesta(request, token)
    s = leggi_studio(user["username"])
    if not s["ha_logo"]:
        raise HTTPException(404, "Nessun logo")
    return FileResponse(s["logo_path"], media_type="image/png")


# ══════════════════════════════════════════════════════════════════════════════
# Checklist A–M
# ══════════════════════════════════════════════════════════════════════════════

class VoceChecklist(BaseModel):
    esito: Optional[str] = None
    motivazione: Optional[str] = None


def _verifica(progetto_id, user):
    conn = get_conn()
    try:
        return dict(_progetto(conn, progetto_id, user))
    finally:
        conn.close()


@router.get("/{progetto_id}/checklist")
def get_checklist(progetto_id: int, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    return ck.stato(progetto_id)


@router.patch("/{progetto_id}/checklist/{voce}")
def patch_checklist(progetto_id: int, voce: str, body: VoceChecklist, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    try:
        ck.salva(progetto_id, voce, body.esito, body.motivazione)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ck.stato(progetto_id)


# ══════════════════════════════════════════════════════════════════════════════
# Export del PSC
# ══════════════════════════════════════════════════════════════════════════════

class RichiestaExport(BaseModel):
    revisione: int
    data: str                    # gg/mm/aaaa
    coordinatore_id: Optional[int] = None


def _coordinatori(username):
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM coordinatori WHERE username=? ORDER BY predefinito DESC, cognome, nome",
                            (username,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _revisioni(progetto_id, username):
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id, revisione, created_at FROM documenti WHERE progetto_id=? AND tipo='psc' AND username=?
               ORDER BY revisione""", (progetto_id, username)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/{progetto_id}/export-info")
def export_info(progetto_id: int, user: dict = Depends(get_current_user)):
    p = _verifica(progetto_id, user)
    coords = _coordinatori(user["username"])
    revisioni = _revisioni(progetto_id, user["username"])
    tappe = tappe_psc.leggi_tappe(progetto_id)
    predefinito = p.get("coordinatore_id") if any(c["id"] == p.get("coordinatore_id") for c in coords) else (coords[0]["id"] if coords else None)
    studio = leggi_studio(user["username"])
    return {
        "revisione_proposta": revisioni[-1]["revisione"] if revisioni else 0,
        "data_proposta": date.today().strftime("%d/%m/%Y"),
        "revisioni": revisioni,
        "coordinatori": [{"id": c["id"], "nome": f"{c['nome']} {c['cognome']}", "predefinito": bool(c.get("predefinito")),
                          "ha_firma": bool(c.get("firma_path") and os.path.exists(c["firma_path"]))} for c in coords],
        "coordinatore_id": predefinito,
        "checklist": {k: v for k, v in ck.stato(progetto_id).items() if k != "sezioni"},
        "tappe_mancanti": [t["numero"] for t in tappe if not t["contenuto_json"] and t["numero"] != 12],
        "studio": {"completo": bool(studio.get("nome")), "ha_logo": studio["ha_logo"]},
        "stato": p["stato"],
        "is_admin": bool(user.get("is_admin")),
        "esempio_pubblicato": (esempio.pubblicato() or {}).get("progetto_id") == progetto_id,
        "is_esempio": bool(p.get("is_esempio")),
    }


@router.post("/{progetto_id}/export-psc")
def export_psc(progetto_id: int, body: RichiestaExport, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    stato = ck.stato(progetto_id)
    if not stato["completa"]:
        raise HTTPException(409, f"Completa la checklist A–M prima dell'export: {len(stato['mancanti'])} voci da sistemare "
                                 f"(prima: {stato['mancanti'][0]['voce']} {stato['mancanti'][0]['testo']})")
    if not 0 <= body.revisione <= 999:
        raise HTTPException(400, "Numero di revisione non valido")
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", body.data.strip()):
        raise HTTPException(400, "Data di revisione non valida: usa il formato gg/mm/aaaa")
    coordinatore = None
    if body.coordinatore_id:
        coordinatore = next((c for c in _coordinatori(user["username"]) if c["id"] == body.coordinatore_id), None)
        if not coordinatore:
            raise HTTPException(404, "Coordinatore non trovato nella tua anagrafica")
        tappe_psc._aggiorna_progetto(progetto_id, coordinatore_id=body.coordinatore_id)
    esito = psc_docx.esporta(progetto_id, user, body.revisione, body.data.strip(), coordinatore,
                             leggi_studio(user["username"]))
    return esito


@router.post("/{progetto_id}/pubblica-esempio")
def pubblica_esempio(progetto_id: int, user: dict = Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(403, "Solo l'amministratore può pubblicare il progetto di esempio")
    _verifica(progetto_id, user)
    esempio.pubblica(progetto_id, user)
    return {"ok": True}


@router.post("/{progetto_id}/tappe/manuale")
def tappe_manuali(progetto_id: int, user: dict = Depends(get_current_user)):
    """Compila senza documenti: crea le tappe non ancora presenti come strutture vuote, senza AI."""
    import json
    _verifica(progetto_id, user)
    create = []
    for t in tappe_psc.leggi_tappe(progetto_id):
        if t["contenuto_json"] or t["stato"] in tappe_psc.STATI_ATTIVI:
            continue
        vuoto = td.normalizza(t["numero"], {})
        tappe_psc._aggiorna(progetto_id, t["numero"], contenuto_json=json.dumps(vuoto, ensure_ascii=False),
                            stato="generata", modificata_a_mano=1, errore=None)
        create.append(t["numero"])
    return {"create": create}

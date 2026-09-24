"""
routers/anagrafica.py — Committenti, imprese e coordinatori

Dal blocco 6 l'anagrafica è PERSONALE per account (1 account = 1 studio): ogni account vede e
modifica solo le schede che ha creato. Le schede create prima (senza proprietario) sono state
assegnate all'account amministratore. Indirizzi e formato delle risposte sono invariati.
Coordinatori: firma (immagine) e "predefinito" (chi firma il PSC se non si sceglie altro).
"""
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, model_validator

from auth import get_current_user
from database import get_conn, cartella_studio

router = APIRouter()

MAX_MB_IMMAGINE = 5


# ═══════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════

class ModelloAnagrafica(BaseModel):
    """I moduli inviano i campi facoltativi vuoti come "": diventano None (prima un "" in un campo
    numerico, es. anni_esperienza, faceva fallire il salvataggio con errore 422)."""
    @model_validator(mode="before")
    @classmethod
    def vuoti_a_none(cls, dati):
        if isinstance(dati, dict):
            return {k: (None if v == "" and k in cls.model_fields and not cls.model_fields[k].is_required() else v)
                    for k, v in dati.items()}
        return dati


class CommittenteIn(ModelloAnagrafica):
    tipo: str = "persona_fisica"
    nome: Optional[str] = None
    cognome: Optional[str] = None
    ragione_sociale: Optional[str] = None
    codice_fiscale: Optional[str] = None
    piva: Optional[str] = None
    indirizzo: Optional[str] = None
    citta: Optional[str] = None
    cap: Optional[str] = None
    provincia: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    pec: Optional[str] = None


class ImpresaIn(ModelloAnagrafica):
    ragione_sociale: str
    codice_fiscale: Optional[str] = None
    piva: str
    indirizzo: Optional[str] = None
    citta: Optional[str] = None
    cap: Optional[str] = None
    provincia: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    pec: Optional[str] = None
    cciaa: Optional[str] = None
    numero_cciaa: Optional[str] = None
    inail_pat: Optional[str] = None
    inps: Optional[str] = None
    cassa_edile: Optional[str] = None
    ccnl: Optional[str] = "CCNL Edilizia Industria"
    nome_dl: Optional[str] = None
    cognome_dl: Optional[str] = None
    nome_rspp: Optional[str] = None
    cognome_rspp: Optional[str] = None
    nome_mc: Optional[str] = None
    cognome_mc: Optional[str] = None
    nome_rls: Optional[str] = None
    cognome_rls: Optional[str] = None


class CoordinatoreIn(ModelloAnagrafica):
    nome: str
    cognome: str
    codice_fiscale: Optional[str] = None
    ordine_professionale: Optional[str] = None
    numero_ordine: Optional[str] = None
    provincia_ordine: Optional[str] = None
    titolo_studio: Optional[str] = None
    anni_esperienza: Optional[int] = None
    attestato_corso: Optional[str] = None
    data_corso: Optional[str] = None
    data_aggiornamento: Optional[str] = None
    indirizzo: Optional[str] = None
    citta: Optional[str] = None
    cap: Optional[str] = None
    provincia: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    pec: Optional[str] = None



TABELLE = {
    "committenti":  (CommittenteIn, "cognome, nome, ragione_sociale", "Committente"),
    "imprese":      (ImpresaIn, "ragione_sociale", "Impresa"),
    "coordinatori": (CoordinatoreIn, "predefinito DESC, cognome, nome", "Coordinatore"),
}


def _colonne(conn, tabella):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({tabella})").fetchall()}


def _elenco(tabella, user):
    conn = get_conn()
    try:
        rows = conn.execute(f"SELECT * FROM {tabella} WHERE username = ? ORDER BY {TABELLE[tabella][1]}",
                            (user["username"],)).fetchall()
    finally:
        conn.close()
    return [_pubblica(dict(r)) for r in rows]


def _pubblica(d):
    """Non espone il percorso del file della firma, solo se esiste."""
    if "firma_path" in d:
        d["ha_firma"] = bool(d["firma_path"] and os.path.exists(d["firma_path"]))
        d.pop("firma_path")
    return d


def _scheda(tabella, id, user):
    conn = get_conn()
    try:
        row = conn.execute(f"SELECT * FROM {tabella} WHERE id = ? AND username = ?", (id, user["username"])).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, f"{TABELLE[tabella][2]} non trovato")
    return dict(row)


def _crea(tabella, data, user):
    campi = data.dict()
    conn = get_conn()
    try:
        cur = conn.execute(
            f"INSERT INTO {tabella} ({', '.join(campi)}, username) VALUES ({', '.join('?' * len(campi))}, ?)",
            (*campi.values(), user["username"]))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _aggiorna(tabella, id, data, user):
    _scheda(tabella, id, user)
    campi = data.dict()
    conn = get_conn()
    try:
        extra = ", updated_at=datetime('now')" if "updated_at" in _colonne(conn, tabella) else ""
        conn.execute(f"UPDATE {tabella} SET {', '.join(k + '=?' for k in campi)}{extra} WHERE id=? AND username=?",
                     (*campi.values(), id, user["username"]))
        conn.commit()
    finally:
        conn.close()


def _elimina(tabella, id, user):
    r = _scheda(tabella, id, user)
    if r.get("firma_path") and os.path.exists(r["firma_path"]):
        os.remove(r["firma_path"])
    conn = get_conn()
    try:
        conn.execute(f"DELETE FROM {tabella} WHERE id=? AND username=?", (id, user["username"]))
        conn.commit()
    finally:
        conn.close()


# ═══════════════════════════════════════════════
# COMMITTENTI
# ═══════════════════════════════════════════════

@router.get("/committenti")
def list_committenti(user: dict = Depends(get_current_user)):
    return _elenco("committenti", user)


@router.get("/committenti/{id}")
def get_committente(id: int, user: dict = Depends(get_current_user)):
    return _pubblica(_scheda("committenti", id, user))


@router.post("/committenti", status_code=201)
def create_committente(data: CommittenteIn, user: dict = Depends(get_current_user)):
    return {"id": _crea("committenti", data, user), "message": "Committente creato"}


@router.put("/committenti/{id}")
def update_committente(id: int, data: CommittenteIn, user: dict = Depends(get_current_user)):
    _aggiorna("committenti", id, data, user)
    return {"message": "Committente aggiornato"}


@router.delete("/committenti/{id}")
def delete_committente(id: int, user: dict = Depends(get_current_user)):
    _elimina("committenti", id, user)
    return {"message": "Committente eliminato"}


# ═══════════════════════════════════════════════
# IMPRESE
# ═══════════════════════════════════════════════

@router.get("/imprese")
def list_imprese(user: dict = Depends(get_current_user)):
    return _elenco("imprese", user)


@router.get("/imprese/{id}")
def get_impresa(id: int, user: dict = Depends(get_current_user)):
    return _pubblica(_scheda("imprese", id, user))


@router.post("/imprese", status_code=201)
def create_impresa(data: ImpresaIn, user: dict = Depends(get_current_user)):
    return {"id": _crea("imprese", data, user), "message": "Impresa creata"}


@router.put("/imprese/{id}")
def update_impresa(id: int, data: ImpresaIn, user: dict = Depends(get_current_user)):
    _aggiorna("imprese", id, data, user)
    return {"message": "Impresa aggiornata"}


@router.delete("/imprese/{id}")
def delete_impresa(id: int, user: dict = Depends(get_current_user)):
    _elimina("imprese", id, user)
    return {"message": "Impresa eliminata"}


# ═══════════════════════════════════════════════
# COORDINATORI
# ═══════════════════════════════════════════════

@router.get("/coordinatori")
def list_coordinatori(user: dict = Depends(get_current_user)):
    return _elenco("coordinatori", user)


@router.get("/coordinatori/{id}")
def get_coordinatore(id: int, user: dict = Depends(get_current_user)):
    return _pubblica(_scheda("coordinatori", id, user))


@router.post("/coordinatori", status_code=201)
def create_coordinatore(data: CoordinatoreIn, user: dict = Depends(get_current_user)):
    nuovo = _crea("coordinatori", data, user)
    # Il primo coordinatore dell'account diventa il predefinito
    conn = get_conn()
    try:
        n = conn.execute("SELECT COUNT(*) FROM coordinatori WHERE username=?", (user["username"],)).fetchone()[0]
        if n == 1:
            conn.execute("UPDATE coordinatori SET predefinito=1 WHERE id=?", (nuovo,))
            conn.commit()
    finally:
        conn.close()
    return {"id": nuovo, "message": "Coordinatore creato"}


@router.put("/coordinatori/{id}")
def update_coordinatore(id: int, data: CoordinatoreIn, user: dict = Depends(get_current_user)):
    _aggiorna("coordinatori", id, data, user)
    return {"message": "Coordinatore aggiornato"}


@router.delete("/coordinatori/{id}")
def delete_coordinatore(id: int, user: dict = Depends(get_current_user)):
    _elimina("coordinatori", id, user)
    return {"message": "Coordinatore eliminato"}


@router.post("/coordinatori/{id}/predefinito")
def imposta_predefinito(id: int, user: dict = Depends(get_current_user)):
    _scheda("coordinatori", id, user)
    conn = get_conn()
    try:
        conn.execute("UPDATE coordinatori SET predefinito = (id = ?) WHERE username = ?", (id, user["username"]))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


def salva_immagine(contenuto: bytes, cartella: str, prefisso: str, vecchio: Optional[str]) -> str:
    """PNG con trasparenza conservata (firme scansionate su fondo bianco restano leggibili)."""
    import io
    from PIL import Image
    if len(contenuto) > MAX_MB_IMMAGINE * 1024 * 1024:
        raise HTTPException(400, f"Immagine troppo grande: il limite è {MAX_MB_IMMAGINE} MB")
    try:
        img = Image.open(io.BytesIO(contenuto))
        img.load()
    except Exception:
        raise HTTPException(400, "File non riconosciuto: carica un'immagine PNG o JPG")
    img = img.convert("RGBA")
    img.thumbnail((1200, 1200))
    path = os.path.join(cartella, f"{prefisso}_{uuid.uuid4().hex[:10]}.png")
    img.save(path, format="PNG")
    if vecchio and os.path.exists(vecchio):
        os.remove(vecchio)
    return path


@router.post("/coordinatori/{id}/firma")
async def carica_firma(id: int, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    r = _scheda("coordinatori", id, user)
    path = salva_immagine(await file.read(), cartella_studio(user["username"]), f"firma_{id}", r.get("firma_path"))
    conn = get_conn()
    try:
        conn.execute("UPDATE coordinatori SET firma_path=? WHERE id=?", (path, id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/coordinatori/{id}/firma")
def elimina_firma(id: int, user: dict = Depends(get_current_user)):
    r = _scheda("coordinatori", id, user)
    if r.get("firma_path") and os.path.exists(r["firma_path"]):
        os.remove(r["firma_path"])
    conn = get_conn()
    try:
        conn.execute("UPDATE coordinatori SET firma_path=NULL WHERE id=?", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.get("/coordinatori/{id}/firma.png")
def immagine_firma(id: int, request: Request, token: Optional[str] = None):
    from routers.documents import _utente_da_richiesta
    user = _utente_da_richiesta(request, token)
    r = _scheda("coordinatori", id, user)
    if not r.get("firma_path") or not os.path.exists(r["firma_path"]):
        raise HTTPException(404, "Nessuna firma")
    return FileResponse(r["firma_path"], media_type="image/png")

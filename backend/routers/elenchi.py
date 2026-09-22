"""
routers/elenchi.py — Pagina "Elenchi prezzi"

- livello 'account': elenchi del singolo utente (carica, rinomina, elimina)
- livello 'sistema': caricati dall'amministratore, visibili a tutti in sola lettura
Gli elenchi caricati dentro un progetto (livello 'progetto') si gestiscono dal progetto.
Nessuna chiamata AI: la lettura è locale e non consuma budget.
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from auth import get_current_user
from database import get_conn
from services import gestione_elenchi

router = APIRouter()

MAX_MB_ELENCO = 50
FORMATI = ("xml", "ods", "xls", "xlsx", "pdf")


class Rinomina(BaseModel):
    nome: str


class Mappatura(BaseModel):
    riga_intestazione: int
    codice: int
    descrizione: int
    um: int
    prezzo: int
    perc_manodopera: Optional[int] = None


def _elenco_modificabile(conn, elenco_id: int, user: dict):
    row = conn.execute("SELECT * FROM elenchi_prezzi WHERE id = ?", (elenco_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Elenco non trovato")
    if row["livello"] == "sistema":
        if not user.get("is_admin"):
            raise HTTPException(403, "Gli elenchi di sistema possono essere modificati solo dall'amministratore")
    elif row["username"] != user["username"] or row["livello"] != "account":
        raise HTTPException(404, "Elenco non trovato")
    return row


def _elenco_leggibile(conn, elenco_id: int, user: dict):
    row = conn.execute("SELECT * FROM elenchi_prezzi WHERE id = ?", (elenco_id,)).fetchone()
    if not row or (row["livello"] != "sistema" and row["username"] != user["username"]):
        raise HTTPException(404, "Elenco non trovato")
    return row


@router.get("")
def elenco(user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id FROM elenchi_prezzi
               WHERE (livello = 'account' AND username = ?) OR livello = 'sistema'
               ORDER BY livello DESC, created_at DESC""", (user["username"],)).fetchall()
        return {
            "elenchi": [gestione_elenchi.leggi_scheda_elenco(conn, r["id"]) for r in rows],
            "puo_caricare_sistema": bool(user.get("is_admin")),
        }
    finally:
        conn.close()


@router.post("")
async def carica(file: UploadFile = File(...), nome: str = Form(default=""),
                 sistema: bool = Form(default=False), user: dict = Depends(get_current_user)):
    if sistema and not user.get("is_admin"):
        raise HTTPException(403, "Solo l'amministratore può caricare elenchi di sistema")
    nome_file = file.filename or "elenco"
    est = nome_file.lower().rsplit(".", 1)[-1]
    if est not in FORMATI:
        raise HTTPException(400, f"Formato .{est} non supportato. Formati ammessi: XML, ODS, XLS, XLSX, PDF")
    contenuto = await file.read()
    if len(contenuto) > MAX_MB_ELENCO * 1024 * 1024:
        raise HTTPException(400, f"File troppo grande: il limite è {MAX_MB_ELENCO} MB")
    return gestione_elenchi.crea_elenco(
        None if sistema else user["username"], "sistema" if sistema else "account",
        (nome or nome_file).strip(), nome_file, contenuto)


@router.patch("/{elenco_id}")
def rinomina(elenco_id: int, body: Rinomina, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        _elenco_modificabile(conn, elenco_id, user)
        conn.execute("UPDATE elenchi_prezzi SET nome = ? WHERE id = ?", (body.nome.strip(), elenco_id))
        conn.commit()
        return gestione_elenchi.leggi_scheda_elenco(conn, elenco_id)
    finally:
        conn.close()


@router.delete("/{elenco_id}")
def elimina(elenco_id: int, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        _elenco_modificabile(conn, elenco_id, user)
    finally:
        conn.close()
    gestione_elenchi.elimina_elenco(elenco_id)
    return {"ok": True}


@router.post("/{elenco_id}/mappatura")
def mappatura(elenco_id: int, body: Mappatura, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        _elenco_modificabile(conn, elenco_id, user)
    finally:
        conn.close()
    try:
        return gestione_elenchi.applica_mappatura(elenco_id, body.dict())
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/{elenco_id}/voci")
def voci(elenco_id: int, q: str = "", limite: int = 50, user: dict = Depends(get_current_user)):
    """Consultazione delle voci (ricerca per codice o parole della descrizione)."""
    conn = get_conn()
    try:
        _elenco_leggibile(conn, elenco_id, user)
        sql = "SELECT codice, descrizione, um, prezzo, perc_manodopera, capitolo FROM elenchi_prezzi_voci WHERE elenco_id = ?"
        params = [elenco_id]
        for parola in [p for p in q.split() if p][:6]:
            sql += " AND (descrizione LIKE ? OR codice LIKE ?)"
            params += [f"%{parola}%", f"%{parola}%"]
        sql += " ORDER BY id LIMIT ?"
        params.append(max(1, min(limite, 200)))
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()

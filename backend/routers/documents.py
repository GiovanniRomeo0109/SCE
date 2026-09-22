"""
routers/documents.py — Storico, download ed eliminazione dei documenti

Usa la tabella reale `documenti` (non più la vecchia `documenti_generati`).
Ogni utente vede solo i propri documenti; l'amministratore vede anche quelli
senza proprietario creati prima di questo aggiornamento.

Il download accetta il token sia nell'header Authorization sia come
parametro ?token=..., così funziona anche con un semplice link <a href>.
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import FileResponse

from auth import decode_token, get_current_user
from database import get_conn, get_user_by_username

router = APIRouter()

MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _utente_da_richiesta(request: Request, token: Optional[str]) -> dict:
    """Legge il token dall'header o dal parametro ?token= e restituisce l'utente."""
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    username = decode_token(token or "").get("sub")
    user = get_user_by_username(username) if username else None
    if not user or not user.get("is_active", 1):
        raise HTTPException(401, "Sessione scaduta — effettua di nuovo il login")
    return user


def _puo_accedere(user: dict, row) -> bool:
    proprietario = row["username"]
    if proprietario == user["username"]:
        return True
    return bool(user.get("is_admin")) and proprietario is None


@router.get("/storico")
def storico_documenti(user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        if user.get("is_admin"):
            rows = conn.execute(
                """SELECT id, tipo, nome_cantiere, impresa_nome, file_path, created_at
                   FROM documenti WHERE username = ? OR username IS NULL
                   ORDER BY created_at DESC LIMIT 200""",
                (user["username"],),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, tipo, nome_cantiere, impresa_nome, file_path, created_at
                   FROM documenti WHERE username = ?
                   ORDER BY created_at DESC LIMIT 200""",
                (user["username"],),
            ).fetchall()
    finally:
        conn.close()

    risultato = []
    for r in rows:
        d = dict(r)
        d["tipo_documento"] = d["tipo"]          # compatibilità con Dashboard.jsx
        d["scaricabile"] = bool(d.pop("file_path"))
        risultato.append(d)
    return risultato


@router.get("/download/{doc_id}")
def download_documento(doc_id: int, request: Request, token: Optional[str] = None):
    user = _utente_da_richiesta(request, token)
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, username, file_path FROM documenti WHERE id = ?", (doc_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row or not _puo_accedere(user, row):
        raise HTTPException(404, "Documento non trovato")
    path = row["file_path"]
    if not path or not os.path.exists(path):
        raise HTTPException(404, "Per questo documento non è disponibile un file da scaricare")

    return FileResponse(path, media_type=MIME_DOCX, filename=os.path.basename(path))


def _elimina(doc_id: int, user: dict):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, username, file_path FROM documenti WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row or not _puo_accedere(user, row):
            raise HTTPException(404, "Documento non trovato")
        if row["file_path"] and os.path.exists(row["file_path"]):
            os.remove(row["file_path"])
        conn.execute("DELETE FROM documenti WHERE id = ?", (doc_id,))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Documento eliminato"}


@router.delete("/storico/{doc_id}")
def elimina_documento_storico(doc_id: int, user: dict = Depends(get_current_user)):
    return _elimina(doc_id, user)


@router.delete("/{doc_id}")
def elimina_documento(doc_id: int, user: dict = Depends(get_current_user)):
    return _elimina(doc_id, user)

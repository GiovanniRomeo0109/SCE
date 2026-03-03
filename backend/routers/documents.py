from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import sqlite3
import os
from database import get_db
from services.docx_generator import genera_psc, genera_pos, genera_notifica_preliminare

router = APIRouter()

DOCS_DIR = "documenti_generati"
os.makedirs(DOCS_DIR, exist_ok=True)


class GeneraRequest(BaseModel):
    tipo_documento: str           # psc | pos | notifica_preliminare
    form_data: dict
    contenuto_ai: Optional[dict] = None
    # metadati opzionali per lo storico
    nome_cantiere: Optional[str] = None
    impresa_nome:  Optional[str] = None


@router.post("/genera")
def genera_documento(req: GeneraRequest, db: sqlite3.Connection = Depends(get_db)):
    GENERATORS = {
        "psc":                  genera_psc,
        "pos":                  genera_pos,
        "notifica_preliminare": genera_notifica_preliminare,
    }

    gen_fn = GENERATORS.get(req.tipo_documento)
    if not gen_fn:
        raise HTTPException(400, f"Tipo documento non supportato: {req.tipo_documento}")

    try:
        file_path = gen_fn(req.form_data, req.contenuto_ai, DOCS_DIR)
    except Exception as exc:
        raise HTTPException(500, f"Errore nella generazione del documento: {exc}")

    # Salva record nel DB
    cur = db.execute("""
        INSERT INTO documenti_generati
            (tipo_documento, nome_cantiere, impresa_nome, file_path)
        VALUES (?, ?, ?, ?)
    """, (req.tipo_documento,
          req.nome_cantiere or req.form_data.get("citta_cantiere", ""),
          req.impresa_nome  or req.form_data.get("impresa_ragione_sociale", ""),
          file_path))
    db.commit()
    doc_id = cur.lastrowid

    return {
        "success":      True,
        "doc_id":       doc_id,
        "filename":     os.path.basename(file_path),
        "download_url": f"/api/documents/download/{doc_id}",
    }


@router.get("/download/{doc_id}")
def download_documento(doc_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT * FROM documenti_generati WHERE id=?", (doc_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Documento non trovato")

    path = row["file_path"]
    if not os.path.exists(path):
        raise HTTPException(404, "File non trovato sul disco")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=os.path.basename(path),
    )


@router.get("/storico")
def storico_documenti(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("""
        SELECT id, tipo_documento, nome_cantiere, impresa_nome, versione, created_at
        FROM documenti_generati
        ORDER BY created_at DESC
        LIMIT 100
    """).fetchall()
    return [dict(r) for r in rows]


@router.delete("/storico/{doc_id}")
def elimina_documento(doc_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT file_path FROM documenti_generati WHERE id=?", (doc_id,)
    ).fetchone()
    if row and os.path.exists(row["file_path"]):
        os.remove(row["file_path"])
    db.execute("DELETE FROM documenti_generati WHERE id=?", (doc_id,))
    db.commit()
    return {"message": "Documento eliminato"}

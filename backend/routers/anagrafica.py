from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import sqlite3
from database import get_db

router = APIRouter()


# ═══════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════

class CommittenteIn(BaseModel):
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


class ImpresaIn(BaseModel):
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


class CoordinatoreIn(BaseModel):
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


# ═══════════════════════════════════════════════
# COMMITTENTI
# ═══════════════════════════════════════════════

@router.get("/committenti")
def list_committenti(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM committenti ORDER BY cognome, nome, ragione_sociale"
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/committenti/{id}")
def get_committente(id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM committenti WHERE id=?", (id,)).fetchone()
    if not row:
        raise HTTPException(404, "Committente non trovato")
    return dict(row)


@router.post("/committenti", status_code=201)
def create_committente(data: CommittenteIn, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("""
        INSERT INTO committenti
            (tipo, nome, cognome, ragione_sociale, codice_fiscale, piva,
             indirizzo, citta, cap, provincia, telefono, email, pec)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (data.tipo, data.nome, data.cognome, data.ragione_sociale,
          data.codice_fiscale, data.piva, data.indirizzo, data.citta,
          data.cap, data.provincia, data.telefono, data.email, data.pec))
    db.commit()
    return {"id": cur.lastrowid, "message": "Committente creato"}


@router.put("/committenti/{id}")
def update_committente(id: int, data: CommittenteIn, db: sqlite3.Connection = Depends(get_db)):
    db.execute("""
        UPDATE committenti SET
            tipo=?, nome=?, cognome=?, ragione_sociale=?, codice_fiscale=?,
            piva=?, indirizzo=?, citta=?, cap=?, provincia=?,
            telefono=?, email=?, pec=?, updated_at=datetime('now')
        WHERE id=?
    """, (data.tipo, data.nome, data.cognome, data.ragione_sociale,
          data.codice_fiscale, data.piva, data.indirizzo, data.citta,
          data.cap, data.provincia, data.telefono, data.email, data.pec, id))
    db.commit()
    return {"message": "Committente aggiornato"}


@router.delete("/committenti/{id}")
def delete_committente(id: int, db: sqlite3.Connection = Depends(get_db)):
    db.execute("DELETE FROM committenti WHERE id=?", (id,))
    db.commit()
    return {"message": "Committente eliminato"}


# ═══════════════════════════════════════════════
# IMPRESE
# ═══════════════════════════════════════════════

@router.get("/imprese")
def list_imprese(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM imprese ORDER BY ragione_sociale"
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/imprese/{id}")
def get_impresa(id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM imprese WHERE id=?", (id,)).fetchone()
    if not row:
        raise HTTPException(404, "Impresa non trovata")
    return dict(row)


@router.post("/imprese", status_code=201)
def create_impresa(data: ImpresaIn, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("""
        INSERT INTO imprese
            (ragione_sociale, codice_fiscale, piva, indirizzo, citta, cap, provincia,
             telefono, email, pec, cciaa, numero_cciaa, inail_pat, inps, cassa_edile, ccnl,
             nome_dl, cognome_dl, nome_rspp, cognome_rspp,
             nome_mc, cognome_mc, nome_rls, cognome_rls)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (data.ragione_sociale, data.codice_fiscale, data.piva,
          data.indirizzo, data.citta, data.cap, data.provincia,
          data.telefono, data.email, data.pec,
          data.cciaa, data.numero_cciaa, data.inail_pat, data.inps, data.cassa_edile, data.ccnl,
          data.nome_dl, data.cognome_dl,
          data.nome_rspp, data.cognome_rspp,
          data.nome_mc, data.cognome_mc,
          data.nome_rls, data.cognome_rls))
    db.commit()
    return {"id": cur.lastrowid, "message": "Impresa creata"}


@router.put("/imprese/{id}")
def update_impresa(id: int, data: ImpresaIn, db: sqlite3.Connection = Depends(get_db)):
    db.execute("""
        UPDATE imprese SET
            ragione_sociale=?, codice_fiscale=?, piva=?, indirizzo=?, citta=?,
            cap=?, provincia=?, telefono=?, email=?, pec=?,
            cciaa=?, numero_cciaa=?, inail_pat=?, inps=?, cassa_edile=?, ccnl=?,
            nome_dl=?, cognome_dl=?,
            nome_rspp=?, cognome_rspp=?,
            nome_mc=?, cognome_mc=?,
            nome_rls=?, cognome_rls=?,
            updated_at=datetime('now')
        WHERE id=?
    """, (data.ragione_sociale, data.codice_fiscale, data.piva,
          data.indirizzo, data.citta, data.cap, data.provincia,
          data.telefono, data.email, data.pec,
          data.cciaa, data.numero_cciaa, data.inail_pat, data.inps, data.cassa_edile, data.ccnl,
          data.nome_dl, data.cognome_dl,
          data.nome_rspp, data.cognome_rspp,
          data.nome_mc, data.cognome_mc,
          data.nome_rls, data.cognome_rls, id))
    db.commit()
    return {"message": "Impresa aggiornata"}


@router.delete("/imprese/{id}")
def delete_impresa(id: int, db: sqlite3.Connection = Depends(get_db)):
    db.execute("DELETE FROM imprese WHERE id=?", (id,))
    db.commit()
    return {"message": "Impresa eliminata"}


# ═══════════════════════════════════════════════
# COORDINATORI
# ═══════════════════════════════════════════════

@router.get("/coordinatori")
def list_coordinatori(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM coordinatori ORDER BY cognome, nome"
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/coordinatori/{id}")
def get_coordinatore(id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM coordinatori WHERE id=?", (id,)).fetchone()
    if not row:
        raise HTTPException(404, "Coordinatore non trovato")
    return dict(row)


@router.post("/coordinatori", status_code=201)
def create_coordinatore(data: CoordinatoreIn, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("""
        INSERT INTO coordinatori
            (nome, cognome, codice_fiscale, ordine_professionale, numero_ordine,
             provincia_ordine, titolo_studio, anni_esperienza, attestato_corso,
             data_corso, data_aggiornamento, indirizzo, citta, cap, provincia,
             telefono, email, pec)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (data.nome, data.cognome, data.codice_fiscale,
          data.ordine_professionale, data.numero_ordine, data.provincia_ordine,
          data.titolo_studio, data.anni_esperienza, data.attestato_corso,
          data.data_corso, data.data_aggiornamento,
          data.indirizzo, data.citta, data.cap, data.provincia,
          data.telefono, data.email, data.pec))
    db.commit()
    return {"id": cur.lastrowid, "message": "Coordinatore creato"}


@router.put("/coordinatori/{id}")
def update_coordinatore(id: int, data: CoordinatoreIn, db: sqlite3.Connection = Depends(get_db)):
    db.execute("""
        UPDATE coordinatori SET
            nome=?, cognome=?, codice_fiscale=?, ordine_professionale=?,
            numero_ordine=?, provincia_ordine=?, titolo_studio=?, anni_esperienza=?,
            attestato_corso=?, data_corso=?, data_aggiornamento=?,
            indirizzo=?, citta=?, cap=?, provincia=?,
            telefono=?, email=?, pec=?, updated_at=datetime('now')
        WHERE id=?
    """, (data.nome, data.cognome, data.codice_fiscale,
          data.ordine_professionale, data.numero_ordine, data.provincia_ordine,
          data.titolo_studio, data.anni_esperienza, data.attestato_corso,
          data.data_corso, data.data_aggiornamento,
          data.indirizzo, data.citta, data.cap, data.provincia,
          data.telefono, data.email, data.pec, id))
    db.commit()
    return {"message": "Coordinatore aggiornato"}


@router.delete("/coordinatori/{id}")
def delete_coordinatore(id: int, db: sqlite3.Connection = Depends(get_db)):
    db.execute("DELETE FROM coordinatori WHERE id=?", (id,))
    db.commit()
    return {"message": "Coordinatore eliminato"}

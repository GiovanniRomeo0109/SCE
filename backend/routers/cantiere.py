"""
routers/cantiere.py — Presidi di emergenza e schemi di cantiere (blocco 5)
Montato con prefisso /api/progetti.
"""
import json
import os
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from auth import get_current_user
from database import get_conn
from routers.documents import _utente_da_richiesta
from routers.progetti import _progetto
from services import presidi as pres
from services import schemi as sch
from services.ai_costi import assicura_budget

router = APIRouter()
MAX_MB_SFONDO = 30


def _verifica(progetto_id, user):
    conn = get_conn()
    try:
        return dict(_progetto(conn, progetto_id, user))
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Presidi di emergenza
# ══════════════════════════════════════════════════════════════════════════════

class Indirizzo(BaseModel):
    indirizzo_cantiere: str


class Presidio(BaseModel):
    tipo: Optional[str] = None
    nome: Optional[str] = None
    indirizzo: Optional[str] = None
    telefono: Optional[str] = None
    distanza: Optional[str] = None
    percorso: Optional[str] = None
    confermato: Optional[bool] = None


@router.get("/{progetto_id}/presidi")
def presidi(progetto_id: int, user: dict = Depends(get_current_user)):
    p = _verifica(progetto_id, user)
    return {
        "indirizzo_cantiere": p.get("indirizzo_cantiere") or "",
        "indirizzo_proposto": pres.indirizzo_da_fascicolo(progetto_id),
        "presidi": pres.elenco(progetto_id),
        "tipi": pres.TIPI,
    }


@router.patch("/{progetto_id}/indirizzo")
def salva_indirizzo(progetto_id: int, body: Indirizzo, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    conn = get_conn()
    try:
        conn.execute("UPDATE progetti SET indirizzo_cantiere = ? WHERE id = ?",
                     (body.indirizzo_cantiere.strip() or None, progetto_id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.post("/{progetto_id}/presidi/cerca")
def cerca_presidi(progetto_id: int, user: dict = Depends(get_current_user)):
    p = _verifica(progetto_id, user)
    indirizzo = (p.get("indirizzo_cantiere") or "").strip()
    if len(indirizzo) < 5:
        raise HTTPException(400, "Indica l'indirizzo del cantiere prima di cercare i presidi")
    assicura_budget(user, pres.STIMA_EUR)
    try:
        esito = pres.cerca(progetto_id, user, indirizzo)
    except Exception as e:
        raise HTTPException(502, f"Ricerca web non riuscita: {getattr(e, 'message', str(e))}. Riprova più tardi.")
    return {**esito, "presidi": pres.elenco(progetto_id)}


@router.post("/{progetto_id}/presidi")
def aggiungi_presidio(progetto_id: int, body: Presidio, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    tipo = body.tipo if body.tipo in pres.TIPI else "altro"
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO progetto_presidi (progetto_id, ordine, tipo, nome, indirizzo, telefono, distanza, percorso,
                      confermato, manuale) VALUES (?,?,?,?,?,?,?,?,1,1)""",
            (progetto_id, pres.ORDINE[tipo], tipo, body.nome or "", body.indirizzo or "", body.telefono or "",
             body.distanza or "", body.percorso or ""))
        conn.commit()
    finally:
        conn.close()
    pres.aggiorna_tappa_9(progetto_id)
    return {"presidi": pres.elenco(progetto_id)}


@router.patch("/{progetto_id}/presidi/{presidio_id}")
def modifica_presidio(progetto_id: int, presidio_id: int, body: Presidio, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    campi = {k: v for k, v in body.dict().items() if v is not None}
    if "tipo" in campi and campi["tipo"] not in pres.TIPI:
        raise HTTPException(400, "Tipo non valido")
    if "confermato" in campi:
        campi["confermato"] = 1 if campi["confermato"] else 0
    conn = get_conn()
    try:
        if not conn.execute("SELECT 1 FROM progetto_presidi WHERE id=? AND progetto_id=?", (presidio_id, progetto_id)).fetchone():
            raise HTTPException(404, "Presidio non trovato")
        if campi:
            conn.execute(f"UPDATE progetto_presidi SET {', '.join(k + '=?' for k in campi)} WHERE id=?",
                         (*campi.values(), presidio_id))
            conn.commit()
    finally:
        conn.close()
    pres.aggiorna_tappa_9(progetto_id)
    return {"presidi": pres.elenco(progetto_id)}


@router.delete("/{progetto_id}/presidi/{presidio_id}")
def elimina_presidio(progetto_id: int, presidio_id: int, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    conn = get_conn()
    try:
        conn.execute("DELETE FROM progetto_presidi WHERE id=? AND progetto_id=?", (presidio_id, progetto_id))
        conn.commit()
    finally:
        conn.close()
    pres.aggiorna_tappa_9(progetto_id)
    return {"presidi": pres.elenco(progetto_id)}


# ══════════════════════════════════════════════════════════════════════════════
# Schemi di cantiere
# ══════════════════════════════════════════════════════════════════════════════

class NuovoSchema(BaseModel):
    nome: str


class ModificaSchema(BaseModel):
    nome: Optional[str] = None
    includi_psc: Optional[bool] = None
    elementi: Optional[List[dict]] = None
    scala: Optional[dict] = None
    azzera_scala: bool = False


class SfondoDocumento(BaseModel):
    documento_id: int
    pagina: int = 1


def _schema(progetto_id, schema_id):
    conn = get_conn()
    try:
        r = conn.execute("SELECT * FROM progetto_schemi WHERE id=? AND progetto_id=?", (schema_id, progetto_id)).fetchone()
    finally:
        conn.close()
    if not r:
        raise HTTPException(404, "Schema non trovato")
    return dict(r)


def _scheda(s: dict, completa: bool = False) -> dict:
    d = {k: s[k] for k in ("id", "nome", "sfondo_w", "sfondo_h", "sfondo_origine", "created_at", "updated_at")}
    d["includi_psc"] = bool(s["includi_psc"])
    d["ha_sfondo"] = bool(s["sfondo_path"] and os.path.exists(s["sfondo_path"]))
    d["scala"] = json.loads(s["scala_json"]) if s["scala_json"] else None
    elementi = json.loads(s["elementi_json"] or "[]")
    d["n_elementi"] = len(elementi)
    if completa:
        d["elementi"] = elementi
    return d


def _aggiorna_schema(schema_id, **campi):
    conn = get_conn()
    try:
        conn.execute(f"UPDATE progetto_schemi SET {', '.join(k + '=?' for k in campi)}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                     (*campi.values(), schema_id))
        conn.commit()
    finally:
        conn.close()


@router.get("/{progetto_id}/schemi")
def elenco_schemi(progetto_id: int, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM progetto_schemi WHERE progetto_id=? ORDER BY id", (progetto_id,)).fetchall()
        tavole = conn.execute(
            """SELECT id, nome_file, estensione, pagine, COALESCE(tipo_csp, tipo_ai) AS tipo FROM progetto_documenti
               WHERE progetto_id=? AND file_path IS NOT NULL AND estensione IN ('pdf','jpg','jpeg','png')
               ORDER BY (COALESCE(tipo_csp, tipo_ai) = 'tavola') DESC, nome_file""", (progetto_id,)).fetchall()
    finally:
        conn.close()
    return {"schemi": [_scheda(dict(r)) for r in rows], "documenti_sfondo": [dict(t) for t in tavole],
            "catalogo": {k: {"etichetta": v[0], "forma": v[1], "dimensioni_m": v[2]} for k, v in sch.ELEMENTI.items()}}


@router.post("/{progetto_id}/schemi")
def crea_schema(progetto_id: int, body: NuovoSchema, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    nome = body.nome.strip() or "Schema di cantiere"
    conn = get_conn()
    try:
        cur = conn.execute("INSERT INTO progetto_schemi (progetto_id, nome, sfondo_w, sfondo_h) VALUES (?,?,?,?)",
                           (progetto_id, nome, *sch.FORMATO_VUOTO))
        conn.commit()
        sid = cur.lastrowid
    finally:
        conn.close()
    return _scheda(_schema(progetto_id, sid), completa=True)


@router.get("/{progetto_id}/schemi/{schema_id}")
def leggi_schema(progetto_id: int, schema_id: int, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    return _scheda(_schema(progetto_id, schema_id), completa=True)


@router.patch("/{progetto_id}/schemi/{schema_id}")
def modifica_schema(progetto_id: int, schema_id: int, body: ModificaSchema, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    _schema(progetto_id, schema_id)
    campi = {}
    if body.nome is not None:
        campi["nome"] = body.nome.strip() or "Schema di cantiere"
    if body.includi_psc is not None:
        campi["includi_psc"] = 1 if body.includi_psc else 0
    if body.elementi is not None:
        campi["elementi_json"] = json.dumps(body.elementi, ensure_ascii=False)
    if body.scala is not None:
        m = float(body.scala.get("m_per_px") or 0)
        if not 0 < m < 1000:
            raise HTTPException(400, "Scala non valida")
        campi["scala_json"] = json.dumps(body.scala)
    if body.azzera_scala:
        campi["scala_json"] = None
    if campi:
        _aggiorna_schema(schema_id, **campi)
    return _scheda(_schema(progetto_id, schema_id), completa=True)


@router.post("/{progetto_id}/schemi/{schema_id}/duplica")
def duplica_schema(progetto_id: int, schema_id: int, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    s = _schema(progetto_id, schema_id)
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO progetto_schemi (progetto_id, nome, includi_psc, sfondo_path, sfondo_w, sfondo_h,
                      sfondo_origine, scala_json, elementi_json) VALUES (?,?,0,?,?,?,?,?,?)""",
            (progetto_id, f"{s['nome']} (copia)", sch.duplica_sfondo(s["sfondo_path"], progetto_id),
             s["sfondo_w"], s["sfondo_h"], s["sfondo_origine"], s["scala_json"], s["elementi_json"]))
        conn.commit()
        sid = cur.lastrowid
    finally:
        conn.close()
    return _scheda(_schema(progetto_id, sid))


@router.delete("/{progetto_id}/schemi/{schema_id}")
def elimina_schema(progetto_id: int, schema_id: int, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    s = _schema(progetto_id, schema_id)
    if s["sfondo_path"] and os.path.exists(s["sfondo_path"]):
        os.remove(s["sfondo_path"])
    conn = get_conn()
    try:
        conn.execute("DELETE FROM progetto_schemi WHERE id=?", (schema_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


def _imposta_sfondo(progetto_id, schema, contenuto, nome_file, pagina, origine):
    try:
        path, w, h = sch.sfondo_da_file(contenuto, nome_file, pagina, progetto_id, schema["sfondo_path"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Impossibile leggere il file: {e}")
    campi = {"sfondo_path": path, "sfondo_w": w, "sfondo_h": h, "sfondo_origine": origine}
    # Cambiando sfondo le coordinate in pixel non corrispondono più: scala da rifare
    if schema["sfondo_w"] and (schema["sfondo_w"], schema["sfondo_h"]) != (w, h):
        campi["scala_json"] = None
    _aggiorna_schema(schema["id"], **campi)
    return _scheda(_schema(progetto_id, schema["id"]), completa=True)


@router.post("/{progetto_id}/schemi/{schema_id}/sfondo")
async def carica_sfondo(progetto_id: int, schema_id: int, file: UploadFile = File(...), pagina: int = Form(1),
                        user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    s = _schema(progetto_id, schema_id)
    contenuto = await file.read()
    if len(contenuto) > MAX_MB_SFONDO * 1024 * 1024:
        raise HTTPException(400, f"File troppo grande: il limite è {MAX_MB_SFONDO} MB")
    return _imposta_sfondo(progetto_id, s, contenuto, file.filename or "sfondo", pagina,
                           f"{file.filename}" + (f", pagina {pagina}" if (file.filename or "").lower().endswith(".pdf") else ""))


@router.post("/{progetto_id}/schemi/{schema_id}/sfondo-documento")
def sfondo_da_documento(progetto_id: int, schema_id: int, body: SfondoDocumento, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    s = _schema(progetto_id, schema_id)
    conn = get_conn()
    try:
        d = conn.execute("SELECT nome_file, file_path FROM progetto_documenti WHERE id=? AND progetto_id=?",
                         (body.documento_id, progetto_id)).fetchone()
    finally:
        conn.close()
    if not d or not d["file_path"] or not os.path.exists(d["file_path"]):
        raise HTTPException(404, "Documento non disponibile (il file originale potrebbe essere stato eliminato)")
    with open(d["file_path"], "rb") as f:
        contenuto = f.read()
    return _imposta_sfondo(progetto_id, s, contenuto, d["nome_file"], body.pagina,
                           f"{d['nome_file']}" + (f", pagina {body.pagina}" if d["nome_file"].lower().endswith(".pdf") else ""))


@router.delete("/{progetto_id}/schemi/{schema_id}/sfondo")
def togli_sfondo(progetto_id: int, schema_id: int, user: dict = Depends(get_current_user)):
    _verifica(progetto_id, user)
    s = _schema(progetto_id, schema_id)
    if s["sfondo_path"] and os.path.exists(s["sfondo_path"]):
        os.remove(s["sfondo_path"])
    _aggiorna_schema(schema_id, sfondo_path=None, sfondo_w=sch.FORMATO_VUOTO[0], sfondo_h=sch.FORMATO_VUOTO[1],
                     sfondo_origine=None, scala_json=None)
    return _scheda(_schema(progetto_id, schema_id), completa=True)


@router.get("/{progetto_id}/schemi/{schema_id}/sfondo.png")
def immagine_sfondo(progetto_id: int, schema_id: int, request: Request, token: Optional[str] = None):
    user = _utente_da_richiesta(request, token)
    _verifica(progetto_id, user)
    s = _schema(progetto_id, schema_id)
    if not s["sfondo_path"] or not os.path.exists(s["sfondo_path"]):
        raise HTTPException(404, "Nessuno sfondo")
    return FileResponse(s["sfondo_path"], media_type="image/png")


@router.get("/{progetto_id}/schemi/{schema_id}/export.dxf")
def esporta_dxf(progetto_id: int, schema_id: int, request: Request, token: Optional[str] = None):
    user = _utente_da_richiesta(request, token)
    _verifica(progetto_id, user)
    s = _schema(progetto_id, schema_id)
    try:
        dati = sch.esporta_dxf(s)
    except ValueError as e:
        raise HTTPException(400, str(e))
    nome = re.sub(r"[^A-Za-z0-9]+", "_", s["nome"]).strip("_")[:40] or "schema"
    return Response(dati, media_type="application/dxf",
                    headers={"Content-Disposition": f'attachment; filename="Schema_{nome}.dxf"'})

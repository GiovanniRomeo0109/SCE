"""
Router autenticazione e statistiche utilizzo
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import date
import sqlite3, os
from auth import create_token, hash_password, get_users, get_current_user

router = APIRouter()

def get_db():
    db_path = os.environ.get("DB_PATH", "cantieri.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginRequest):
    users = get_users()
    user = users.get(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    stored_hash = user.get("password_hash", "")
    input_hash = hash_password(req.password)
    if stored_hash != input_hash:
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    token = create_token(req.username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "nome": user.get("nome", req.username),
        "username": req.username,
        "max_calls_giorno": user.get("max_calls_giorno", 20),
    }

@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    db = get_db()
    oggi = date.today().isoformat()
    row = db.execute(
        "SELECT COUNT(*) as n FROM usage_log WHERE username=? AND giorno=?",
        (user["username"], oggi)
    ).fetchone()
    calls_oggi = row["n"] if row else 0
    return {
        "username": user["username"],
        "nome": user.get("nome", user["username"]),
        "max_calls_giorno": user.get("max_calls_giorno", 20),
        "calls_oggi": calls_oggi,
        "calls_rimanenti": max(0, user.get("max_calls_giorno", 20) - calls_oggi),
    }

@router.get("/usage")
def usage_stats(user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute(
        """SELECT giorno, tipo_operazione, COUNT(*) as n
           FROM usage_log WHERE username=?
           GROUP BY giorno, tipo_operazione
           ORDER BY giorno DESC LIMIT 30""",
        (user["username"],)
    ).fetchall()
    return {"stats": [dict(r) for r in rows]}

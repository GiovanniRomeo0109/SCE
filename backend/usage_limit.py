"""
Controllo limiti utilizzo giornalieri per utente
Da importare nei router che fanno chiamate API costose
"""
import sqlite3, os
from datetime import date
from fastapi import HTTPException, Depends
from auth import get_current_user

def get_db():
    db_path = os.environ.get("DB_PATH", "cantieri.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def check_and_log(user: dict, tipo_operazione: str):
    """
    Verifica che l'utente non abbia superato il limite giornaliero.
    Se ok, registra la chiamata nel log.
    Lancia HTTPException 429 se limite superato.
    """
    db = get_db()
    oggi = date.today().isoformat()
    max_calls = user.get("max_calls_giorno", 20)

    row = db.execute(
        "SELECT COUNT(*) as n FROM usage_log WHERE username=? AND giorno=?",
        (user["username"], oggi)
    ).fetchone()
    calls_oggi = row["n"] if row else 0

    if calls_oggi >= max_calls:
        raise HTTPException(
            status_code=429,
            detail=f"Limite giornaliero raggiunto ({max_calls} operazioni). "
                   f"Il contatore si azzera a mezzanotte."
        )

    db.execute(
        "INSERT INTO usage_log (username, giorno, tipo_operazione) VALUES (?,?,?)",
        (user["username"], oggi, tipo_operazione)
    )
    db.commit()

def require_credits(tipo: str):
    """
    Dependency factory: usa come Depends(require_credits("verifica_psc"))
    """
    def _check(user: dict = Depends(get_current_user)):
        check_and_log(user, tipo)
        return user
    return _check

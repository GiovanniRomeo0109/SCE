"""
Autenticazione JWT per demo SCE
Utenti definiti tramite variabile d'ambiente DEMO_USERS (JSON)
"""
import os, json, hashlib, hmac, base64, time
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.environ.get("JWT_SECRET", "cambia-questa-chiave-in-produzione")
TOKEN_EXPIRE_HOURS = 12
bearer_scheme = HTTPBearer()

# ── Carica utenti da env ───────────────────────────────────────────────────────
def get_users() -> dict:
    raw = os.environ.get("DEMO_USERS", "[]")
    try:
        lista = json.loads(raw)
        return {u["username"]: u for u in lista}
    except Exception:
        return {}

# ── JWT minimale (senza dipendenze extra) ─────────────────────────────────────
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64d(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * pad)

def create_token(username: str) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({
        "sub": username,
        "exp": int(time.time()) + TOKEN_EXPIRE_HOURS * 3600,
        "iat": int(time.time()),
    }).encode())
    msg = f"{header}.{payload}".encode()
    sig = _b64(hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"

def verify_token(token: str) -> Optional[str]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload, sig = parts
        msg = f"{header}.{payload}".encode()
        expected = _b64(hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_b64d(payload))
        if data.get("exp", 0) < time.time():
            return None
        return data.get("sub")
    except Exception:
        return None

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ── Dependency FastAPI ─────────────────────────────────────────────────────────
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    username = verify_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token non valido o scaduto")
    users = get_users()
    user = users.get(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Utente non trovato")
    return user

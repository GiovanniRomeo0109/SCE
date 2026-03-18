import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from database import get_user_by_username

SECRET_KEY = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 ore

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ── Password ───────────────────────────────────────────────────────────────────
def _trunc(plain: str) -> str:
    """Tronca a 72 byte (limite bcrypt) gestendo caratteri multibyte."""
    encoded = plain.encode("utf-8")
    if len(encoded) <= 72:
        return plain
    return encoded[:72].decode("utf-8", errors="ignore")

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_trunc(plain), hashed)

def hash_password(plain: str) -> str:
    return pwd_context.hash(_trunc(plain))

# ── Token ──────────────────────────────────────────────────────────────────────
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return {}

# ── Autenticazione utente ──────────────────────────────────────────────────────
def authenticate_user(username: str, password: str):
    """Verifica username e password contro il DB. Ritorna il record utente o None."""
    user = get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    if not user.get("is_active", 1):
        return None
    return user

# ── Dependency: utente corrente ────────────────────────────────────────────────
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_user_by_username(username)
    if not user or not user.get("is_active", 1):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato o disabilitato",
        )
    return user

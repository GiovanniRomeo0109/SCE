from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, field_validator
import re

from auth import authenticate_user, create_access_token, hash_password, get_current_user
from database import create_user, get_user_by_username, get_user_by_email

router = APIRouter()

# ── Schemi ─────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    nome_cognome: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username deve avere almeno 3 caratteri")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username può contenere solo lettere, numeri e underscore")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_valid(cls, v):
        if len(v) < 6:
            raise ValueError("La password deve avere almeno 6 caratteri")
        return v

    @field_validator("nome_cognome")
    @classmethod
    def nome_valid(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Inserisci il nome e cognome")
        return v

# ── Login ──────────────────────────────────────────────────────────────────────
@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username o password non validi",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": user["username"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
        "nome_cognome": user.get("nome_cognome", ""),
    }

# ── Registrazione ──────────────────────────────────────────────────────────────
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    # Controlla duplicati
    if get_user_by_username(body.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username già in uso — scegline un altro",
        )
    if get_user_by_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email già registrata",
        )

    # Crea utente
    hashed = hash_password(body.password)
    ok = create_user(body.username, body.email, body.nome_cognome, hashed)
    if not ok:
        raise HTTPException(status_code=500, detail="Errore durante la registrazione")

    # Ritorna token direttamente → accesso immediato
    token = create_access_token({"sub": body.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": body.username,
        "nome_cognome": body.nome_cognome,
    }

# ── Me ─────────────────────────────────────────────────────────────────────────
@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "username": current_user["username"],
        "email": current_user.get("email", ""),
        "nome_cognome": current_user.get("nome_cognome", ""),
    }

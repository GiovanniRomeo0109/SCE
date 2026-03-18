from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, field_validator

from auth import authenticate_user, create_access_token, hash_password, get_current_user
from database import create_user, get_user_by_username, get_user_by_email

router = APIRouter()

# ── Schemi ─────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str          # sarà uguale all'email
    email: EmailStr
    nome_cognome: str
    password: str

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
    # Supporta login sia con email che con username legacy
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        # Prova anche per email (nel caso username sia diverso da email)
        from database import get_user_by_email
        user_by_email = get_user_by_email(form_data.username)
        if user_by_email:
            from auth import verify_password
            if verify_password(form_data.password, user_by_email["password_hash"]):
                user = user_by_email
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o password non validi",
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
    email = body.email.lower().strip()

    # Controlla duplicati su email (che è anche lo username)
    if get_user_by_email(email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email già registrata — accedi o usa un'altra email",
        )

    hashed = hash_password(body.password)
    try:
        ok = create_user(email, email, body.nome_cognome, hashed)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Errore DB: {ex}")
    if not ok:
        raise HTTPException(status_code=409, detail='Email già registrata')

    token = create_access_token({"sub": email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": email,
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

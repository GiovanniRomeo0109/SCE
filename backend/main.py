"""
main.py aggiornato per Railway
- Serve React build come file statici
- Registra router auth
- CORS aggiornato per produzione
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os, pathlib

from database import init_db
from routers import agent, anagrafica, estrazione, verifica
from routers.auth_router import router as auth_router

app = FastAPI(title="SCE — Sicurezza Cantieri Edili")

# ── CORS ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    print("✅ Database inizializzato")

# ── API Routers ───────────────────────────────────────────────────────────────
app.include_router(auth_router,  prefix="/api/auth",      tags=["Auth"])
app.include_router(agent.router, prefix="/api/agent",     tags=["Agent"])
app.include_router(anagrafica.router, prefix="/api/anagrafica", tags=["Anagrafica"])
app.include_router(estrazione.router, prefix="/api/estrazione", tags=["Estrazione"])
app.include_router(verifica.router,   prefix="/api/verifica",   tags=["Verifica"])

# ── Serve React build (solo in produzione) ────────────────────────────────────
STATIC_DIR = pathlib.Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR / "static")), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_react(full_path: str = ""):
        # Le rotte /api/* non arrivano qui (gestite sopra)
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"status": "SCE API running"}

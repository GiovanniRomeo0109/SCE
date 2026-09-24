"""
main.py aggiornato per Railway
- Serve React build come file statici
- Registra router auth
- CORS aggiornato per produzione
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os, pathlib

from database import init_db
from routers import agent, anagrafica, estrazione, verifica, documents, progetti, elenchi, tappe, costi, cantiere, finale
from routers.auth_router import router as auth_router
from usage_limit import require_credits

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

# ── Progetti chiusi: sola lettura ─────────────────────────────────────────────
# Un unico controllo per tutti i router: su un progetto chiuso sono ammesse solo le letture,
# l'export del PSC e l'eliminazione del progetto.
import re as _re
from fastapi import Request as _Request
from fastapi.responses import JSONResponse as _JSONResponse

_RE_PROGETTO = _re.compile(r"^/api/progetti/(\d+)/(.+)$")
_AMMESSI_CHIUSO = ("export-psc",)
# Progetti manuali: niente documenti per l'AI, niente generazione delle tappe, niente ricerca web dei presidi
_VIETATI_MANUALE = _re.compile(r"^(documenti|documenti/\d+/rielabora|tappe/bozza|tappe/\d+/genera|presidi/cerca)$")


@app.middleware("http")
async def sola_lettura_progetti_chiusi(request: _Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        m = _RE_PROGETTO.match(request.url.path)
        if m and m.group(2) not in _AMMESSI_CHIUSO:
            from database import get_conn
            conn = get_conn()
            try:
                r = conn.execute("SELECT stato, modalita FROM progetti WHERE id = ?", (int(m.group(1)),)).fetchone()
            finally:
                conn.close()
            if r and r["stato"] == "chiuso":
                return _JSONResponse({"detail": "Il progetto è chiuso: è in sola lettura. Puoi ancora scaricare il PSC."},
                                     status_code=409)
            if r and r["modalita"] == "manuale" and request.method == "POST" and _VIETATI_MANUALE.match(m.group(2)):
                return _JSONResponse({"detail": "Funzione non disponibile nei progetti manuali: le tappe si compilano a mano."},
                                     status_code=409)
    return await call_next(request)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    # Worker che elabora in background i documenti dei progetti PSC
    from services.worker_progetti import avvia_worker
    avvia_worker()
    print("✅ Database inizializzato")

# ── Healthcheck ───────────────────────────────────────────────────────────────
@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}

# ── API Routers ───────────────────────────────────────────────────────────────
app.include_router(auth_router,  prefix="/api/auth",      tags=["Auth"])
app.include_router(agent.router, prefix="/api/agent",     tags=["Agent"])
app.include_router(anagrafica.router, prefix="/api/anagrafica", tags=["Anagrafica"])
# Estrazione: controllo budget/limiti a livello di router.
# NB: il costo reale sarà tracciato quando estrazione.py userà TrackedClient.
app.include_router(estrazione.router, prefix="/api/estrazione", tags=["Estrazione"],
                   dependencies=[Depends(require_credits("estrazione"))])
app.include_router(verifica.router,   prefix="/api/verifica",   tags=["Verifica"])
app.include_router(documents.router,  prefix="/api/documents",  tags=["Documents"])
app.include_router(progetti.router,   prefix="/api/progetti",   tags=["Progetti PSC"])
app.include_router(tappe.router,      prefix="/api/progetti",   tags=["Tappe PSC"])
app.include_router(costi.router,      prefix="/api/progetti",   tags=["Costi e tempi"])
app.include_router(cantiere.router,   prefix="/api/progetti",   tags=["Emergenze e schemi"])
app.include_router(finale.router,     prefix="/api/progetti",   tags=["Documento finale"])
app.include_router(finale.router_studio, prefix="/api/studio",  tags=["Studio"])
app.include_router(elenchi.router,    prefix="/api/elenchi",    tags=["Elenchi prezzi"])

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

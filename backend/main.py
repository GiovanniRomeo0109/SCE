from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import anagrafica, documents, agent
from routers import estrazione

app = FastAPI(
    title="SafetyDocs API — Sicurezza Cantieri Edili",
    description=(
        "API per la generazione della documentazione obbligatoria di sicurezza "
        "nei cantieri edili italiani — D.Lgs. 81/2008"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    init_db()


# ── Router registration ────────────────────────────────────────────────────────
app.include_router(anagrafica.router, prefix="/api/anagrafica", tags=["Anagrafica"])
app.include_router(documents.router,  prefix="/api/documents",  tags=["Documenti"])
app.include_router(agent.router,      prefix="/api/agent",      tags=["Agente AI"])
app.include_router(estrazione.router)


@app.get("/", tags=["Health"])
def root():
    return {
        "status":   "ok",
        "app":      "SafetyDocs API",
        "version":  "1.0.0",
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}

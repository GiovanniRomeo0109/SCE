#!/bin/bash
# ═══════════════════════════════════════════════
# SafetyDocs — Avvio Backend
# ═══════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   SafetyDocs — Backend Sicurezza Cantieri ║"
echo "║   D.Lgs. 81/2008 — v1.0.0                ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Verifica ANTHROPIC_API_KEY
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠  ATTENZIONE: ANTHROPIC_API_KEY non impostata."
    echo "   La generazione AI del contenuto non funzionerà."
    echo "   Esporta la chiave con:"
    echo "   export ANTHROPIC_API_KEY='sk-ant-...'"
    echo ""
fi

# Crea virtualenv se non esiste
if [ ! -d "venv" ]; then
    echo "📦 Creazione ambiente virtuale..."
    python3 -m venv venv
fi

# Attiva venv
source venv/bin/activate

# Installa dipendenze
echo "📦 Installazione dipendenze..."
pip install -q -r requirements.txt

# Crea cartella output documenti
mkdir -p documenti_generati

echo ""
echo "🚀 Avvio server su http://localhost:8000"
echo "📚 Documentazione API: http://localhost:8000/docs"
echo "🔍 ReDoc: http://localhost:8000/redoc"
echo ""
echo "Premi CTRL+C per fermare il server"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

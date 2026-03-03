@echo off
:: ═══════════════════════════════════════════════
:: SafetyDocs — Avvio Backend (Windows)
:: ═══════════════════════════════════════════════

echo.
echo  SafetyDocs ^— Backend Sicurezza Cantieri
echo  D.Lgs. 81/2008 ^— v1.0.0
echo.

cd /d "%~dp0"

:: Verifica ANTHROPIC_API_KEY
if "%ANTHROPIC_API_KEY%"=="" (
    echo  ATTENZIONE: ANTHROPIC_API_KEY non impostata.
    echo  Imposta la variabile con:
    echo  set ANTHROPIC_API_KEY=sk-ant-...
    echo.
)

:: Crea virtualenv se non esiste
if not exist "venv\" (
    echo  Creazione ambiente virtuale...
    python -m venv venv
)

:: Attiva venv e installa dipendenze
call venv\Scripts\activate.bat
echo  Installazione dipendenze...
pip install -q -r requirements.txt

:: Crea cartella output
if not exist "documenti_generati\" mkdir documenti_generati

echo.
echo  Avvio server su http://localhost:8000
echo  Documentazione API: http://localhost:8000/docs
echo  Premi CTRL+C per fermare
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

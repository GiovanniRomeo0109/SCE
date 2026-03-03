# SafetyDocs — Backend API
## Documentazione Sicurezza Cantieri Edili — D.Lgs. 81/2008

---

## Struttura del progetto

```
backend/
├── main.py                     # Applicazione FastAPI principale
├── database.py                 # Database SQLite (init + connessione)
├── requirements.txt            # Dipendenze Python
├── start.sh                    # Script avvio (macOS/Linux)
├── start.bat                   # Script avvio (Windows)
├── skill/
│   └── SKILL.md                # Normativa completa D.Lgs. 81/2008
├── routers/
│   ├── anagrafica.py           # CRUD committenti, imprese, coordinatori
│   ├── agent.py                # Verifica obbligatorietà + AI content
│   └── documents.py            # Generazione e download DOCX
└── services/
    └── docx_generator.py       # Template DOCX professionali
```

---

## Installazione e avvio

### Prerequisiti
- Python 3.9+
- Chiave API Anthropic (`ANTHROPIC_API_KEY`)

### macOS / Linux

```bash
# 1. Entra nella cartella backend
cd backend

# 2. Imposta la chiave API
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. Rendi eseguibile lo script e avvia
chmod +x start.sh
./start.sh
```

### Windows

```batch
:: 1. Apri il terminale nella cartella backend
:: 2. Imposta la chiave API
set ANTHROPIC_API_KEY=sk-ant-...

:: 3. Avvia
start.bat
```

### Avvio manuale (tutte le piattaforme)

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
mkdir -p documenti_generati
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Reference

### Base URL
```
http://localhost:8000
```

### Documentazione interattiva
- Swagger UI: http://localhost:8000/docs
- ReDoc:       http://localhost:8000/redoc

---

### Anagrafica

#### Committenti
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET    | `/api/anagrafica/committenti` | Lista tutti |
| GET    | `/api/anagrafica/committenti/{id}` | Dettaglio |
| POST   | `/api/anagrafica/committenti` | Crea nuovo |
| PUT    | `/api/anagrafica/committenti/{id}` | Aggiorna |
| DELETE | `/api/anagrafica/committenti/{id}` | Elimina |

#### Imprese Esecutrici
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET    | `/api/anagrafica/imprese` | Lista tutte |
| POST   | `/api/anagrafica/imprese` | Crea nuova |
| PUT    | `/api/anagrafica/imprese/{id}` | Aggiorna |
| DELETE | `/api/anagrafica/imprese/{id}` | Elimina |

#### Coordinatori CSP/CSE
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET    | `/api/anagrafica/coordinatori` | Lista tutti |
| POST   | `/api/anagrafica/coordinatori` | Crea nuovo |
| PUT    | `/api/anagrafica/coordinatori/{id}` | Aggiorna |
| DELETE | `/api/anagrafica/coordinatori/{id}` | Elimina |

---

### Agente AI

#### Verifica Obbligatorietà
```
POST /api/agent/check-obbligatorieta
```
**Body:**
```json
{
  "document_type": "notifica_preliminare",   // o "psc" o "pos"
  "uomini_giorno": 250,
  "max_lavoratori": 15,
  "rischi_allegato_xi": false,
  "num_imprese": 3,
  "tipo_soggetto": "impresa_esecutrice"
}
```
**Risposta:**
```json
{
  "obbligatorio": true,
  "motivazioni": ["Durata cantiere di 250 UG supera la soglia di 200 UG"],
  "riferimenti_normativi": ["Art. 99 co. 1, D.Lgs. 81/2008"],
  "avvertenze": []
}
```

#### Generazione Contenuto AI
```
POST /api/agent/genera-contenuto
```
**Body:**
```json
{
  "tipo_documento": "psc",
  "form_data": { ... }
}
```
Chiama Claude per generare le sezioni narrative del documento.

---

### Documenti

#### Genera Documento DOCX
```
POST /api/documents/genera
```
**Body:**
```json
{
  "tipo_documento": "psc",
  "form_data": {
    "descrizione_opera": "Costruzione edificio residenziale",
    "indirizzo_cantiere": "Via Roma 10",
    "citta_cantiere": "Milano",
    "provincia_cantiere": "MI",
    "committente_nome": "Mario",
    "committente_cognome": "Rossi",
    "csp_nome": "Ing. Carlo",
    "csp_cognome": "Bianchi",
    "costi_sicurezza": "15000"
  },
  "contenuto_ai": { ... },
  "nome_cantiere": "Milano Via Roma"
}
```
**Risposta:**
```json
{
  "success": true,
  "doc_id": 1,
  "filename": "PSC_Milano_20250302_143022.docx",
  "download_url": "/api/documents/download/1"
}
```

#### Download
```
GET /api/documents/download/{doc_id}
```
Scarica il file DOCX generato.

#### Storico
```
GET /api/documents/storico
```
Lista documenti generati (ultimi 100).

---

## Database

Il database SQLite (`cantieri.db`) viene creato automaticamente al primo avvio.

**Tabelle:**
- `committenti` — Anagrafica committenti (persone fisiche e giuridiche)
- `imprese` — Anagrafica imprese esecutrici con tutte le figure della sicurezza
- `coordinatori` — Anagrafica CSP/CSE
- `documenti_generati` — Storico documenti prodotti

---

## Documenti generati

I documenti DOCX vengono salvati nella cartella `documenti_generati/`.

### Documenti supportati

| Documento | Norma | Quando obbligatorio |
|-----------|-------|---------------------|
| **Notifica Preliminare** | Art. 99, All. XII | UG > 200 oppure > 20 lavoratori contemporanei oppure rischi All. XI |
| **PSC** | Art. 100, All. XV | Più di una impresa esecutrice |
| **POS** | Art. 101, All. XV | Ogni impresa esecutrice (sempre) |

---

## Note tecniche

- I documenti DOCX includono tutti i campi obbligatori previsti dalla normativa
- Il contenuto testuale delle sezioni narrative viene generato da Claude (Anthropic API)
- L'analisi dell'obbligatorietà è deterministica (no AI) basata sulla normativa
- I documenti includono sempre: intestazione professionale, riferimenti normativi per sezione, avviso di revisione professionale, piè di pagina con data generazione
- L'anagrafica persistente evita di reinserire dati di committenti/imprese/coordinatori ricorrenti

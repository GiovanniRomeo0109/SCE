# ISTRUZIONI INTEGRAZIONE — Modulo Verifica Documenti

## 1. FILE DA CREARE/COPIARE

### Backend
```
backend/
  skill/
    VERIFICA_PSC_POS.md          ← dalla cartella verifica_module/backend/
  routers/
    verifica.py                  ← dalla cartella verifica_module/backend/
  services/
    pdf_generator_verifica.py    ← dalla cartella verifica_module/backend/
```

### Frontend
```
frontend/src/
  pages/
    VerificaDocumenti.jsx        ← dalla cartella verifica_module/frontend/
```

---

## 2. MODIFICA main.py — Registra il router

Apri `backend/main.py` e aggiungi dopo gli import esistenti:

```python
from routers import verifica
```

E dopo gli altri `app.include_router(...)`:

```python
app.include_router(verifica.router, prefix="/api/verifica", tags=["verifica"])
```

---

## 3. MODIFICA database.py — Verifica colonna 'stato'

Apri `backend/database.py` e controlla che la tabella `documenti_generati` 
abbia la colonna `stato`. Se non c'è, aggiungila nella CREATE TABLE:

```python
# Nella funzione init_db(), nella CREATE TABLE documenti_generati:
"""CREATE TABLE IF NOT EXISTS documenti_generati (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_documento TEXT NOT NULL,
    nome_cantiere TEXT,
    data_generazione TEXT,
    file_path TEXT,
    stato TEXT DEFAULT 'Generato'    -- ← aggiungi questa riga se mancante
)"""
```

Se la tabella esiste già, esegui da terminale nella cartella backend:
```bash
python -c "import sqlite3; db=sqlite3.connect('safetydocs.db'); db.execute('ALTER TABLE documenti_generati ADD COLUMN stato TEXT DEFAULT \"Generato\"'); db.commit()"
```

---

## 4. MODIFICA services/pdf_generator.py

Apri `backend/services/pdf_generator.py` (se esiste) oppure crea la cartella:

```python
# In backend/services/__init__.py (crea se non esiste)
# (file vuoto)
```

Poi rinomina o aggiungi:
```
backend/services/pdf_generator_verifica.py  (già creato)
```

Il router verifica.py importa:
```python
from services.pdf_generator import genera_verbale_incongruenze
```

Aggiungi questa riga in cima a `services/pdf_generator_verifica.py`:

```python
# Alias per compatibilità con l'import nel router
genera_verbale_incongruenze = genera_verbale_incongruenze  # già definita nel file
```

Oppure più semplicemente in `verifica.py` cambia l'import in:
```python
from services.pdf_generator_verifica import genera_verbale_incongruenze, genera_report_verifica
```

---

## 5. MODIFICA App.jsx — Aggiungi route

```jsx
// In cima: aggiungi import
import VerificaDocumenti from './pages/VerificaDocumenti';

// Nelle routes, DOPO la route /storico:
<Route path="/verifica" element={<VerificaDocumenti />} />
```

---

## 6. MODIFICA Sidebar.jsx — Aggiungi voce menu

Trova l'array dei link di navigazione e aggiungi dopo "Storico":

```jsx
{ path: '/verifica', icon: '🔍', label: 'Verifica Documenti' },
```

---

## 7. MODIFICA utils/api.js — Aggiungi funzioni verifica

```js
// Aggiungi in fondo a api.js (prima di export default):

export const verificaPsc = (formData) =>
  api.post('/verifica/verifica-psc', formData,
    { headers: { 'Content-Type': 'multipart/form-data' } });

export const verificaPos = (formData) =>
  api.post('/verifica/verifica-pos', formData,
    { headers: { 'Content-Type': 'multipart/form-data' } });

export const verificaCongruita = (formData) =>
  api.post('/verifica/verifica-congruita', formData,
    { headers: { 'Content-Type': 'multipart/form-data' } });

export const generaVerbale = (payload) =>
  api.post('/verifica/genera-verbale', payload);
```

---

## 8. DIPENDENZE PYTHON

Verifica che nel venv siano installate (dovrebbero già esserci):
```bash
pip install reportlab python-docx anthropic --break-system-packages
```

---

## 9. STORICO — Mostrare documenti "In verifica"

In `frontend/src/pages/Storico.jsx`, il documento viene salvato con 
`tipo_documento = "verifica_psc"` / `"verifica_pos"` / `"verifica_congruita"`.

Se vuoi mostrare un badge colorato per questi tipi, aggiungi:

```jsx
// Nella funzione che renderizza il tipo documento nello Storico:
const getTipoLabel = (tipo) => {
  const labels = {
    'psc': '📗 PSC',
    'pos': '📘 POS', 
    'notifica_preliminare': '📋 Notifica',
    'verifica_psc': '🔍 Verifica PSC',
    'verifica_pos': '🔍 Verifica POS',
    'verifica_congruita': '🔗 Verifica Congruità',
    'verbale_incongruenze': '📄 Verbale Incongruenze',
  };
  return labels[tipo] || tipo;
};
```

---

## FLUSSO UTENTE

```
Dashboard → [🔍 Verifica Documenti]
  ↓
Inserisci nome cantiere
Scegli modalità:
  ├─ Verifica PSC → carica PSC → avvia → risultati con non-conformità → scarica PDF
  ├─ Verifica POS → carica 1-5 POS → avvia → risultati per ogni POS → scarica PDF
  └─ Verifica Congruità → carica PSC + 1-5 POS → avvia
       → per ogni POS: lista incongruenze espandibili
       → valida/modifica ogni incongruenza
       → genera Verbale PDF (tutte o solo validate)
```

---

## NOTE TECNICHE

- Il report PDF verifica viene salvato nel DB e scaricabile dallo Storico
- Il Verbale incongruenze è generato on-demand (non in automatico)
- Claude usa `claude-sonnet-4-6` per tutte le verifiche
- I PDF vengono caricati come `base64` (supporto nativo Claude)
- I DOCX vengono estratti come testo
- Max timeout consigliato per verifica congruità PSC+5POS: 3-4 minuti

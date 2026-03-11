"""
Router verifica conformità PSC e POS — D.Lgs. 81/2008 Allegato XV
Approccio due passaggi: estrazione → verifica sistematica
Fix: max_tokens=16000, parser robusto, checklist basata su testo legale esatto
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from typing import List, Optional
import anthropic
import os, json, sqlite3, base64, re, logging, pathlib
from datetime import datetime
from auth import get_current_user
from usage_limit import require_credits

router = APIRouter()

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = pathlib.Path(os.getcwd()) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("verifica")
log.setLevel(logging.DEBUG)
if not log.handlers:
    fh = logging.FileHandler(LOG_DIR / "verifica.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]\n%(message)s\n" + "─"*80))
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s [VERIFICA] %(message)s"))
    log.addHandler(sh)

# ── Skill ─────────────────────────────────────────────────────────────────────
_skill: Optional[str] = None

def get_skill() -> str:
    global _skill
    if _skill is None:
        path = os.path.join(os.path.dirname(__file__), "../skill/VERIFICA_PSC_POS.md")
        try:
            with open(path, "r", encoding="utf-8") as f:
                _skill = f.read()
            log.info(f"Skill caricata: {len(_skill)} caratteri")
        except FileNotFoundError:
            log.error("SKILL FILE NON TROVATO!")
            _skill = ""
    return _skill

def get_db():
    db_path = os.environ.get("DB_PATH", "cantieri.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ── Lettura documento ─────────────────────────────────────────────────────────
def leggi_documento(file_bytes: bytes, filename: str) -> dict:
    ext = filename.lower().rsplit(".", 1)[-1]
    log.info(f"Lettura: {filename} ({len(file_bytes)} bytes, tipo={ext})")
    if ext == "pdf":
        b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
        return {"tipo": "pdf", "b64": b64, "filename": filename}
    elif ext in ("docx", "doc"):
        try:
            import io
            from docx import Document as DocxDoc
            doc = DocxDoc(io.BytesIO(file_bytes))
            righe = []
            for p in doc.paragraphs:
                t = p.text.strip()
                if t:
                    righe.append(t)
            for table in doc.tables:
                for row in table.rows:
                    riga = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                    if riga:
                        righe.append(riga)
            testo = "\n".join(righe)
            log.info(f"DOCX: {len(testo)} caratteri, {len(righe)} righe")
            log.debug(f"Prime 800 chr:\n{testo[:800]}")
            if len(testo) < 100:
                raise HTTPException(400, f"Documento '{filename}' vuoto o non leggibile.")
            return {"tipo": "testo", "contenuto": testo, "filename": filename}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Errore lettura DOCX '{filename}': {e}")
    else:
        raise HTTPException(400, f"Formato non supportato: {ext}")

def build_messages(doc_info: dict, prompt: str) -> list:
    if doc_info["tipo"] == "pdf":
        return [{"role": "user", "content": [
            {"type": "document", "source": {"type": "base64",
             "media_type": "application/pdf", "data": doc_info["b64"]}},
            {"type": "text", "text": prompt}
        ]}]
    return [{"role": "user", "content":
        f"=== TESTO COMPLETO DEL DOCUMENTO ===\n\n{doc_info['contenuto']}\n\n"
        f"=== FINE DOCUMENTO ===\n\n{prompt}"}]

# ── Parser JSON robusto ───────────────────────────────────────────────────────
def clean_json(raw: str) -> dict:
    original = raw
    raw = raw.strip()
    # rimuovi markdown code fence
    if "```" in raw:
        for part in raw.split("```"):
            p = part.strip().lstrip("json").strip()
            if p.startswith("{"):
                raw = p
                break
    raw = raw.strip()
    # trova { ... }
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end+1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning(f"JSON troncato o malformato ({e}) — recupero parziale...")
        result = {"_parse_error": str(e), "_raw_parziale": True,
                  "non_conformita": [], "punti_conformi": []}
        # recupera non_conformita
        m = re.search(r'"non_conformita"\s*:\s*(\[)', raw, re.DOTALL)
        if m:
            arr_start = m.start(1)
            depth, arr_end = 0, arr_start
            for i in range(arr_start, len(raw)):
                if raw[i] == '[': depth += 1
                elif raw[i] == ']':
                    depth -= 1
                    if depth == 0:
                        arr_end = i + 1
                        break
            try:
                result["non_conformita"] = json.loads(raw[arr_start:arr_end])
                log.info(f"Recuperate {len(result['non_conformita'])} non_conformita dal JSON troncato")
            except Exception:
                # recupero item per item
                items = re.findall(r'\{[^{}]*"id"\s*:[^{}]*\}', raw[arr_start:], re.DOTALL)
                parsed = []
                for item in items:
                    try:
                        parsed.append(json.loads(item))
                    except Exception:
                        pass
                result["non_conformita"] = parsed
                log.info(f"Recupero item-per-item: {len(parsed)} non_conformita")
        # recupera campi scalari
        for field in ["punteggio_conformita","giudizio_sintetico","documento_analizzato",
                       "nome_file","data_verifica","impresa","giudizio"]:
            m2 = re.search(rf'"{field}"\s*:\s*"?([^",\n}}]+)"?', raw)
            if m2:
                val = m2.group(1).strip().strip('"')
                try: result[field] = int(val)
                except ValueError: result[field] = val
        # riepilogo calcolato
        nc = result["non_conformita"]
        result["riepilogo"] = {
            "totale_verifiche": len(nc),
            "critici":    sum(1 for x in nc if x.get("severita") == "CRITICO"),
            "importanti": sum(1 for x in nc if x.get("severita") == "IMPORTANTE"),
            "consigli":   sum(1 for x in nc if x.get("severita") == "CONSIGLIO"),
            "conformi":   0
        }
        log.info(f"Risultato recuperato: {result.get('giudizio_sintetico')} — "
                 f"{len(nc)} NC ({result['riepilogo']['critici']} critici)")
        return result

def salva_db(db, tipo, nome, risultato) -> int:
    try:
        cur = db.execute(
            "INSERT INTO documenti_generati (tipo_documento, nome_cantiere, "
            "data_generazione, file_path, stato) VALUES (?,?,?,?,?)",
            (f"verifica_{tipo}", nome, datetime.now().isoformat(),
             json.dumps(risultato, ensure_ascii=False), "In verifica"))
        db.commit()
        return cur.lastrowid
    except Exception as e:
        log.error(f"Errore DB: {e}")
        return -1

# ══════════════════════════════════════════════════════════════════════════════
# PASSAGGIO 1: ESTRAZIONE CONTENUTO REALE
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_ESTRAZIONE_PSC = """
Leggi il documento e riporta ESATTAMENTE il testo trovato per ogni campo.
Se un campo NON è presente nel documento scrivi "ASSENTE".
Non inventare, non integrare, non interpretare.

Rispondi SOLO con JSON valido:
{
  "indirizzo_cantiere": "...",
  "descrizione_contesto": "...",
  "descrizione_opera_scelte_progettuali": "...",
  "data_inizio": "...",
  "data_fine": "...",
  "durata_uomini_giorno": "...",
  "responsabile_lavori": "...",
  "csp_nominativo": "...",
  "csp_titolo_studio": "...",
  "csp_attestato_formazione": "...",
  "csp_aggiornamento": "...",
  "csp_ordine_professionale": "...",
  "cse_nominativo": "...",
  "cse_attestato_formazione": "...",
  "datori_lavoro_imprese": "...",
  "relazione_rischi_area_cantiere": "...",
  "relazione_rischi_organizzazione": "...",
  "relazione_rischi_lavorazioni": "...",
  "relazione_rischi_interferenze": "...",
  "linee_aeree_condutture": "...",
  "rischio_traffico_stradale": "...",
  "rischio_annegamento": "...",
  "rischi_area_circostante": "...",
  "recinzione_accessi_segnalazioni": "...",
  "servizi_igienico_assistenziali": "...",
  "viabilita_cantiere": "...",
  "impianti_alimentazione_reti": "...",
  "impianto_terra_scariche": "...",
  "consultazione_rls_art102": "...",
  "riunione_coordinamento_art92": "...",
  "accesso_mezzi_fornitura": "...",
  "dislocazione_impianti": "...",
  "zone_carico_scarico": "...",
  "zone_deposito_stoccaggio": "...",
  "zone_materiali_incendio_esplosione": "...",
  "rischio_investimento_veicoli": "...",
  "rischio_seppellimento_scavi": "...",
  "rischio_ordigni_bellici": "...",
  "rischio_caduta_alto": "...",
  "rischio_incendio_esplosione_materiali": "...",
  "rischio_sbalzi_temperatura": "...",
  "rischio_elettrocuzione": "...",
  "rischio_rumore": "...",
  "rischio_sostanze_chimiche": "...",
  "analisi_interferenze_lavorazioni": "...",
  "cronoprogramma": "...",
  "prescrizioni_sfasamento_spaziale_temporale": "...",
  "modalita_verifica_prescrizioni": "...",
  "misure_coordinamento_uso_comune": "...",
  "modalita_cooperazione_coordinamento_dl": "...",
  "organizzazione_pronto_soccorso": "...",
  "organizzazione_antincendio_evacuazione": "...",
  "riferimenti_telefonici_pronto_soccorso": "...",
  "riferimenti_telefonici_prevenzione_incendi": "...",
  "planimetria_presente": "si/no",
  "costi_apprestamenti": "...",
  "costi_misure_preventive_dpi_interferenti": "...",
  "costi_impianti_terra_antincendio": "...",
  "costi_protezione_collettiva": "...",
  "costi_procedure": "...",
  "costi_sfasamento": "...",
  "costi_coordinamento": "...",
  "costi_totale": "...",
  "costi_analitica_per_voci": "si/no",
  "costi_non_soggetti_ribasso": "..."
}
"""

PROMPT_ESTRAZIONE_POS = """
Leggi il documento POS e riporta ESATTAMENTE il testo trovato per ogni campo.
Se un campo NON è presente nel documento scrivi "ASSENTE".
Non inventare, non integrare, non interpretare.
Per ogni lavoratore riporta ESATTAMENTE le date scritte nel documento.

Rispondi SOLO con JSON valido:
{
  "nominativo_datore_lavoro": "...",
  "indirizzo_sede_legale": "...",
  "telefono_sede_legale": "...",
  "telefono_uffici_cantiere": "...",
  "specifica_attivita_lavorazioni": "...",
  "lavorazioni_subaffidatari": "...",
  "nominativo_addetti_ps": "...",
  "nominativo_addetti_antincendio": "...",
  "nominativo_addetti_emergenze": "...",
  "nominativo_rls": "...",
  "nominativo_medico_competente": "...",
  "motivazione_no_mc": "...",
  "nominativo_rspp": "...",
  "attestato_rspp": "...",
  "nominativo_direttore_tecnico": "...",
  "nominativo_capocantiere": "...",
  "numero_qualifiche_lavoratori": "...",
  "mansioni_sicurezza_figure": "...",
  "descrizione_attivita_cantiere": "...",
  "modalita_organizzative": "...",
  "turni_lavoro": "...",
  "patentino_imprese_art27": "...",
  "lavoratori": [
    {
      "nome": "...",
      "mansione": "...",
      "data_visita_medica": "...",
      "esito_visita": "...",
      "data_formazione_generale": "...",
      "data_formazione_specifica": "...",
      "aggiornamento_formazione": "..."
    }
  ],
  "elenco_ponteggi": "...",
  "elenco_ponti_ruote": "...",
  "opere_provvisionali": "...",
  "macchine": [
    {
      "nome": "...",
      "modello": "...",
      "dichiarazione_ce": "...",
      "verifica_periodica": "..."
    }
  ],
  "sostanze_pericolose": "...",
  "schede_sicurezza_sds": "...",
  "valutazione_rumore": "...",
  "misure_preventive_protettive": "...",
  "misure_integrative_psc": "...",
  "procedure_complementari_psc": "...",
  "elenco_dpi": "...",
  "documentazione_informazione_lavoratori": "...",
  "documentazione_formazione_lavoratori": "...",
  "costi_sicurezza": "...",
  "costi_non_soggetti_ribasso": "..."
}
"""

# ══════════════════════════════════════════════════════════════════════════════
# PASSAGGIO 2: CHECKLIST BASATA SU ALLEGATO XV
# ══════════════════════════════════════════════════════════════════════════════
def build_prompt_verifica_psc(estrazione: dict, filename: str, skill: str) -> str:
    now = datetime.now().strftime('%d/%m/%Y %H:%M')

    if estrazione.get("_fallback") and "_testo_grezzo" in estrazione:
        contesto = f"TESTO COMPLETO DEL DOCUMENTO (estrazione JSON fallita — analizza direttamente):\n{estrazione['_testo_grezzo']}"
    else:
        contesto = f"CONTENUTO ESTRATTO DAL DOCUMENTO (questo è TUTTO ciò che è nel documento):\n{json.dumps(estrazione, ensure_ascii=False, indent=2)}"

    return f"""
{skill}

---

Sei un ispettore della sicurezza sul lavoro con 25 anni di esperienza nei cantieri.
Devi verificare la conformità di un PSC rispetto all'Allegato XV del D.Lgs. 81/2008.

{contesto}

ISTRUZIONE FONDAMENTALE:
Ogni campo con valore "ASSENTE" significa che quella informazione NON È nel documento.
Un requisito dell'Allegato XV non soddisfatto è una non conformità CERTA.
Non essere benevolo. Non assumere che qualcosa ci sia se non è nell'estrazione.

ESEGUI LA VERIFICA COMPLETA su tutti i requisiti dell'Allegato XV elencati nella skill.
Per ogni requisito: confronta il valore estratto con quanto richiede la legge.

Per ogni NON CONFORMITÀ includi:
- id: codice (es. A1, B2, M9)
- sezione: nome sezione Allegato XV
- descrizione: cosa manca o è sbagliato (specifica)
- norma_violata: punto esatto Allegato XV o articolo D.Lgs. 81/2008
- severita: CRITICO / IMPORTANTE / CONSIGLIO
- sanzione_applicabile: sanzione prevista per i CRITICI (null per gli altri)
- testo_trovato: valore esatto dall'estrazione
- testo_corretto: testo che dovrebbe essere presente

Per ogni PUNTO CONFORME includi id, sezione, descrizione.

Calcola punteggio: (requisiti_soddisfatti / requisiti_applicabili) * 100
Giudizio: CONFORME (0 critici, max 3 importanti, punteggio ≥85) /
          CONFORME CON RISERVE (1-3 critici o 4-8 importanti, punteggio 60-84) /
          NON CONFORME (4+ critici o 9+ importanti o punteggio <60)

Rispondi SOLO con JSON valido (NESSUN testo prima o dopo):
{{
  "documento_analizzato": "PSC",
  "nome_file": "{filename}",
  "data_verifica": "{now}",
  "punteggio_conformita": 0,
  "giudizio_sintetico": "NON CONFORME",
  "non_conformita": [
    {{
      "id": "A1",
      "sezione": "Identificazione opera — All. XV 2.1.2a",
      "descrizione": "...",
      "norma_violata": "All. XV punto 2.1.2 lett. a n.1 D.Lgs. 81/2008",
      "severita": "CRITICO",
      "sanzione_applicabile": "Art. 157 co.1 lett. b D.Lgs. 81/2008",
      "testo_trovato": "ASSENTE",
      "testo_corretto": "..."
    }}
  ],
  "punti_conformi": [
    {{
      "id": "B1",
      "sezione": "Soggetti — All. XV 2.1.2b",
      "descrizione": "..."
    }}
  ],
  "riepilogo": {{
    "totale_verifiche": 0,
    "critici": 0,
    "importanti": 0,
    "consigli": 0,
    "conformi": 0
  }},
  "note_aggiuntive": "..."
}}
"""


def build_prompt_verifica_pos(estrazione: dict, filename: str, skill: str) -> str:
    now = datetime.now().strftime('%d/%m/%Y %H:%M')

    if estrazione.get("_fallback") and "_testo_grezzo" in estrazione:
        contesto = f"TESTO COMPLETO DEL DOCUMENTO (estrazione JSON fallita — analizza direttamente):\n{estrazione['_testo_grezzo']}"
    else:
        contesto = f"CONTENUTO ESTRATTO DAL DOCUMENTO:\n{json.dumps(estrazione, ensure_ascii=False, indent=2)}"

    return f"""
{skill}

---

Sei un ispettore della sicurezza sul lavoro con 25 anni di esperienza.
Devi verificare la conformità di un POS rispetto all'Allegato XV punto 3.2.1 del D.Lgs. 81/2008.

{contesto}

ISTRUZIONE FONDAMENTALE:
Ogni campo "ASSENTE" = informazione NON nel documento = non conformità CERTA.
Non essere benevolo. Verifica ogni singolo requisito dell'Allegato XV punto 3.2.1.

REGOLE SPECIFICHE PER IL POS:

1. MEDICO COMPETENTE (punto 3.2.1 lett. a n.4):
   - Se "ASSENTE" o "non necessario": le imprese EDILI ed ELETTRICHE hanno SEMPRE
     rischi soggetti a sorveglianza sanitaria obbligatoria (rumore, polveri, movimentazione
     carichi, lavori in quota). La sorveglianza sanitaria è OBBLIGATORIA → CRITICO.
   - Sanzione: Art. 55 co.5 lett. c D.Lgs. 81/2008

2. OGNI LAVORATORE nell'elenco "lavoratori":
   a) data_visita_medica: se anno < 2024 per rischio alto (edile/elettrico) → PROBABILE SCADUTA → CRITICO
      (periodicità annuale per rischio alto — art. 41 D.Lgs. 81/2008)
   b) data_formazione_generale: se ASSENTE → CRITICO (Accordo SR 21/12/2011 — 4h obbligatorie)
   c) data_formazione_specifica: se ASSENTE → CRITICO (12h obbligatorie rischio alto)

3. OGNI MACCHINA nell'elenco "macchine":
   - dichiarazione_ce ASSENTE → CRITICO (D.Lgs. 22/2023)

4. SCHEDE DI SICUREZZA (punto 3.2.1 lett. e):
   - Se sostanze pericolose presenti e SDS non tutte disponibili → CRITICO

5. VALUTAZIONE RUMORE (punto 3.2.1 lett. f):
   - Se ASSENTE → IMPORTANTE (obbligatoria per imprese edili)

6. COSTI NON SOGGETTI A RIBASSO (punto 4.1.4):
   - Se dicitura assente → CRITICO

7. PATENTINO ART. 27 (obbligatorio dal 1/10/2024):
   - Se ASSENTE → IMPORTANTE

Rispondi SOLO con JSON valido (NESSUN testo prima o dopo):
{{
  "documento_analizzato": "POS",
  "nome_file": "{filename}",
  "impresa": "<ragione sociale estratta>",
  "data_verifica": "{now}",
  "punteggio_conformita": 0,
  "giudizio_sintetico": "NON CONFORME",
  "non_conformita": [
    {{
      "id": "N10",
      "sezione": "Dati impresa — All. XV 3.2.1a n.4",
      "descrizione": "...",
      "norma_violata": "All. XV punto 3.2.1 lett. a n.4 + Art. 41 D.Lgs. 81/2008",
      "severita": "CRITICO",
      "sanzione_applicabile": "Art. 55 co.5 lett. c D.Lgs. 81/2008",
      "testo_trovato": "...",
      "testo_corretto": "..."
    }}
  ],
  "punti_conformi": [
    {{
      "id": "N1",
      "sezione": "Dati impresa — All. XV 3.2.1a n.1",
      "descrizione": "..."
    }}
  ],
  "riepilogo": {{
    "totale_verifiche": 0,
    "critici": 0,
    "importanti": 0,
    "consigli": 0,
    "conformi": 0
  }},
  "note_aggiuntive": "..."
}}
"""

# ══════════════════════════════════════════════════════════════════════════════
# FUNZIONE CORE
# ══════════════════════════════════════════════════════════════════════════════

def verifica_documento(doc_info: dict, tipo: str, client: anthropic.Anthropic) -> dict:
    log.info(f"{'='*60}\nVERIFICA {tipo.upper()}: {doc_info['filename']}\n{'='*60}")

    # ── Passaggio 1: estrazione ───────────────────────────────────────────────
    log.info("PASSAGGIO 1: ESTRAZIONE")
    prompt_est = PROMPT_ESTRAZIONE_PSC if tipo == "psc" else PROMPT_ESTRAZIONE_POS

    r1 = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=(
            "Sei un lettore tecnico preciso. Estrai informazioni riportando ESATTAMENTE "
            "il testo presente nel documento. Se un campo non è presente scrivi ASSENTE. "
            "Non inventare. Rispondi SOLO con JSON valido."
        ),
        messages=build_messages(doc_info, prompt_est),
    )
    raw1 = r1.content[0].text
    log.debug(f"RISPOSTA ESTRAZIONE:\n{raw1}")
    estrazione = clean_json(raw1)
    if estrazione.get("_raw_parziale") or estrazione.get("errore"):
        log.warning("Estrazione JSON fallita — fallback: invio testo grezzo al Passaggio 2")
    # Usa il testo del documento direttamente come contesto per la verifica
    if doc_info["tipo"] == "testo":
        estrazione = {"_testo_grezzo": doc_info["contenuto"], "_fallback": True}
    else:
        # Per PDF già inviato come documento, riprova con max_tokens maggiore
        r1b = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            system="Estrai informazioni riportando ESATTAMENTE il testo. Se assente scrivi ASSENTE. SOLO JSON valido.",
            messages=build_messages(doc_info, prompt_est),
        )
        estrazione = clean_json(r1b.content[0].text)
        log.info(f"Retry estrazione: {len(estrazione)} campi")

    assenti = [k for k, v in estrazione.items()
               if isinstance(v, str) and v.strip().upper() == "ASSENTE"]
    log.info(f"Estrazione OK — {len(estrazione)} campi, {len(assenti)} ASSENTI: {assenti}")

    # ── Passaggio 2: verifica ─────────────────────────────────────────────────
    log.info("PASSAGGIO 2: VERIFICA ALLEGATO XV")
    skill = get_skill()

    if tipo == "psc":
        prompt_ver = build_prompt_verifica_psc(estrazione, doc_info["filename"], skill)
    else:
        prompt_ver = build_prompt_verifica_pos(estrazione, doc_info["filename"], skill)

    log.info(f"Prompt verifica: {len(prompt_ver)} caratteri")

    r2 = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,          # FIX: era 8000 — causa del troncamento
        system=(
            "Sei un ispettore senior della sicurezza nei cantieri italiani. "
            "Sei INFLESSIBILE: segnali OGNI non conformità rispetto all'Allegato XV D.Lgs. 81/2008. "
            "Basi la verifica SOLO sui dati estratti forniti. "
            "ASSENTE = informazione non nel documento = non conformità CERTA. "
            "Rispondi SOLO con JSON valido, NESSUN testo prima o dopo le parentesi graffe."
        ),
        messages=[{"role": "user", "content": prompt_ver}],
    )
    raw2 = r2.content[0].text
    log.debug(f"RISPOSTA VERIFICA:\n{raw2}")

    risultato = clean_json(raw2)
    nc = risultato.get("non_conformita", [])
    rie = risultato.get("riepilogo", {})
    log.info(
        f"RISULTATO: {risultato.get('giudizio_sintetico')} — "
        f"punteggio={risultato.get('punteggio_conformita')}% — "
        f"NC={len(nc)} (C={rie.get('critici',0)}, I={rie.get('importanti',0)}, "
        f"cons={rie.get('consigli',0)}) — conformi={rie.get('conformi',0)}"
    )
    for item in nc:
        log.info(f"  [{item.get('severita','?')}] {item.get('id','?')} — "
                 f"{str(item.get('descrizione',''))[:80]}")
    return risultato

# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1 — VERIFICA PSC
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/verifica-psc")
async def verifica_psc(
    file: UploadFile = File(...),
    nome_cantiere: str = Form(default="Cantiere"),
    user: dict = Depends(require_credits("verifica_psc")),
):
    doc_info = leggi_documento(await file.read(), file.filename)
    risultato = verifica_documento(doc_info, "psc", anthropic.Anthropic())
    risultato["doc_id"] = salva_db(get_db(), "psc", nome_cantiere, risultato)
    return risultato

# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2 — VERIFICA POS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/verifica-pos")
async def verifica_pos(
    files: List[UploadFile] = File(...),
    nome_cantiere: str = Form(default="Cantiere"),
    user: dict = Depends(require_credits("verifica_pos")),
):
    if len(files) > 5:
        raise HTTPException(400, "Massimo 5 POS per volta.")
    client = anthropic.Anthropic()
    db = get_db()
    risultati = []
    for f in files:
        doc_info = leggi_documento(await f.read(), f.filename)
        ris = verifica_documento(doc_info, "pos", client)
        ris["doc_id"] = salva_db(db, "pos", nome_cantiere, ris)
        risultati.append(ris)
    return {"risultati": risultati, "totale_pos": len(risultati)}

# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3 — VERIFICA CONGRUITÀ PSC-POS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/verifica-congruita")
async def verifica_congruita(
    psc: UploadFile = File(...),
    pos_files: List[UploadFile] = File(...),
    nome_cantiere: str = Form(default="Cantiere"),
    user: dict = Depends(require_credits("verifica_congruita")),
):
    if len(pos_files) > 5:
        raise HTTPException(400, "Massimo 5 POS per volta.")
    client = anthropic.Anthropic()
    db = get_db()
    skill = get_skill()
    now = datetime.now().strftime('%d/%m/%Y %H:%M')

    psc_info = leggi_documento(await psc.read(), psc.filename)

    # Estrai PSC
    r_psc = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=3000,
        system="Estrai informazioni da documenti tecnici. Rispondi SOLO con JSON valido.",
        messages=build_messages(psc_info, """
Estrai dal PSC i seguenti dati in JSON:
{
  "cantiere": "indirizzo e committente",
  "periodo_lavori": "data inizio e fine",
  "imprese_previste": "per ogni impresa: ragione sociale, attività, periodo, aree di lavoro",
  "dpi_minimi_obbligatori": "lista DPI prescritti per tutti",
  "prescrizioni_interferenze": "regole sfasamento spaziale/temporale tra imprese",
  "misure_coordinamento": "modalità riunioni, verifica prescrizioni",
  "piano_emergenze": "procedure, punto raccolta, numeri emergenza incluso CSE",
  "costi_totali": "importo costi sicurezza"
}
"""),
    )
    psc_dati = clean_json(r_psc.content[0].text)
    log.info(f"PSC per congruità estratto: {json.dumps(psc_dati, ensure_ascii=False)[:400]}")

    risultati = []
    for pos_file in pos_files:
        pos_info = leggi_documento(await pos_file.read(), pos_file.filename)

        # Estrai POS
        r_pos = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=2000,
            system="Estrai informazioni da documenti tecnici. Rispondi SOLO con JSON valido.",
            messages=build_messages(pos_info, """
Estrai dal POS i seguenti dati in JSON:
{
  "impresa": "ragione sociale",
  "cantiere_indicato": "indirizzo cantiere nel POS",
  "periodo_intervento": "date inizio e fine",
  "attivita_lavorazioni": "lavorazioni descritte",
  "aree_lavoro": "aree indicate",
  "dpi_indicati": "DPI con norme EN",
  "interferenze_psc_citate": "prescrizioni PSC richiamate o ASSENTE",
  "piano_emergenze": "procedure presenti",
  "punto_raccolta": "indicato o ASSENTE",
  "numero_cse": "numero CSE riportato o ASSENTE"
}
"""),
        )
        pos_dati = clean_json(r_pos.content[0].text)

        # Verifica congruità
        prompt_cong = f"""
{skill}

---

Sei un ispettore senior. Verifica la CONGRUITÀ del POS rispetto al PSC.
Confronta ogni elemento punto per punto.

DATI PSC — {psc.filename}:
{json.dumps(psc_dati, ensure_ascii=False, indent=2)}

DATI POS — {pos_file.filename}:
{json.dumps(pos_dati, ensure_ascii=False, indent=2)}

ELEMENTI DA VERIFICARE (All. XV punto 2.3.2 e 3.2.1 lett. g-h):

1. PERIODO: le date del POS rientrano nel periodo PSC? Fuori range → CRITICO
2. ATTIVITÀ: le lavorazioni del POS sono previste nel PSC per quell'impresa? Non previste → CRITICO
3. AREE: le aree del POS coincidono con quelle assegnate nel PSC? Discordanza → CRITICO
4. INTERFERENZE: il POS recepisce le prescrizioni di sfasamento del PSC?
   interferenze_psc_citate = ASSENTE → CRITICO (All. XV 3.2.1 lett. g)
5. DPI: i DPI del POS includono almeno quelli prescritti nel PSC? Inferiori → CRITICO
6. EMERGENZE: piano emergenze POS allineato al PSC? Discordanza → IMPORTANTE
7. PUNTO RACCOLTA: citato nel POS? ASSENTE → IMPORTANTE
8. NUMERO CSE: riportato nel POS? ASSENTE → IMPORTANTE

Rispondi SOLO con JSON valido:
{{
  "pos_analizzato": "{pos_file.filename}",
  "psc_riferimento": "{psc.filename}",
  "data_verifica": "{now}",
  "giudizio": "CONGRUENTE|NON CONGRUENTE|CONGRUENTE CON RISERVE",
  "incongruenze": [
    {{
      "id": "INC-01",
      "elemento": "elemento verificato",
      "valore_psc": "valore nel PSC",
      "valore_pos": "valore nel POS o ASSENTE",
      "descrizione": "descrizione precisa dell'incongruenza",
      "norma_violata": "All. XV punto ...",
      "severita": "CRITICO|IMPORTANTE|CONSIGLIO",
      "modifica_richiesta": "testo da inserire/modificare nel POS",
      "sezione_pos_da_modificare": "sezione del POS",
      "validata": false,
      "nota_utente": ""
    }}
  ],
  "elementi_congruenti": [
    {{"elemento": "...", "descrizione": "..."}}
  ],
  "riepilogo": {{
    "totale_verifiche": 8,
    "critici": 0,
    "importanti": 0,
    "consigli": 0,
    "congruenti": 0
  }}
}}
"""
        r_cong = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=8000,
            system="Ispettore senior inflessibile. Segnala ogni incongruenza. SOLO JSON valido.",
            messages=[{"role": "user", "content": prompt_cong}],
        )
        raw_cong = r_cong.content[0].text
        log.debug(f"CONGRUITÀ {pos_file.filename}:\n{raw_cong}")
        ris = clean_json(raw_cong)
        log.info(f"Congruità {pos_file.filename}: {ris.get('giudizio')} — "
                 f"{len(ris.get('incongruenze',[]))} incongruenze")
        ris["doc_id"] = salva_db(db, "congruita", nome_cantiere, ris)
        ris["pos_filename"] = pos_file.filename
        risultati.append(ris)

    return {"psc_filename": psc.filename, "risultati": risultati, "totale_pos": len(risultati)}

# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 4 — GENERA VERBALE PDF
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/genera-verbale")
async def genera_verbale(
    payload: dict,
    user: dict = Depends(get_current_user),
):
    from services.pdf_generator_verifica import genera_verbale_incongruenze
    output_dir = os.path.join(os.path.dirname(__file__), "../output")
    os.makedirs(output_dir, exist_ok=True)
    path = genera_verbale_incongruenze(
        incongruenze=payload.get("incongruenze", []),
        pos_filename=payload.get("pos_filename", "POS"),
        psc_filename=payload.get("psc_filename", "PSC"),
        nome_cantiere=payload.get("nome_cantiere", "Cantiere"),
        output_dir=output_dir,
    )
    db = get_db()
    cur = db.execute(
        "INSERT INTO documenti_generati (tipo_documento, nome_cantiere, "
        "data_generazione, file_path, stato) VALUES (?,?,?,?,?)",
        ("verbale_incongruenze", payload.get("nome_cantiere", "Cantiere"),
         datetime.now().isoformat(), path, "Generato"))
    db.commit()
    return {"doc_id": cur.lastrowid, "path": path}

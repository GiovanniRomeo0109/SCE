"""
Router per la verifica di conformita' PSC e POS.
VERSIONE CON LOGGING DIAGNOSTICO COMPLETO.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import List, Optional
import anthropic
import os
import json
import sqlite3
import base64
import logging
import pathlib
from datetime import datetime

router = APIRouter()

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = pathlib.Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log = logging.getLogger("verifica")
log.setLevel(logging.DEBUG)
if not log.handlers:
    fh = logging.FileHandler(LOG_DIR / "verifica.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]\n%(message)s\n" + "─"*80))
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
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
            log.error("SKILL FILE NON TROVATO — verifica senza normativa di riferimento!")
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
    log.info(f"Lettura documento: {filename} ({len(file_bytes)} bytes, tipo={ext})")

    if ext == "pdf":
        b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
        log.info(f"PDF convertito in base64: {len(b64)} caratteri")
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
            log.info(f"DOCX estratto: {len(testo)} caratteri, {len(righe)} righe")
            log.debug(f"PRIME 500 CARATTERI ESTRATTE:\n{testo[:500]}")
            if len(testo) < 100:
                raise HTTPException(400, f"Documento '{filename}' troppo corto o vuoto.")
            return {"tipo": "testo", "contenuto": testo, "filename": filename}
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Errore lettura DOCX: {e}")
            raise HTTPException(400, f"Errore lettura DOCX '{filename}': {str(e)}")
    else:
        raise HTTPException(400, f"Formato non supportato: {ext}")


def build_messages(doc_info: dict, testo_prompt: str) -> list:
    if doc_info["tipo"] == "pdf":
        return [{"role": "user", "content": [
            {"type": "document", "source": {
                "type": "base64", "media_type": "application/pdf", "data": doc_info["b64"]
            }},
            {"type": "text", "text": testo_prompt}
        ]}]
    else:
        return [{"role": "user", "content":
            f"=== TESTO COMPLETO DEL DOCUMENTO ===\n\n{doc_info['contenuto']}\n\n"
            f"=== FINE DOCUMENTO ===\n\n{testo_prompt}"
        }]


def clean_json(raw: str) -> dict:
    original = raw
    raw = raw.strip()
    if "```" in raw:
        parts = raw.split("```")
        for p in parts:
            p2 = p.strip()
            if p2.startswith("json"):
                p2 = p2[4:].strip()
            if p2.startswith("{"):
                raw = p2
                break
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end+1]
    try:
        result = json.loads(raw)
        return result
    except Exception as e:
        log.error(f"Errore parsing JSON: {e}\nRAW (prime 500 chr): {original[:500]}")
        return {"errore": "Impossibile parsare la risposta AI", "raw": original[:800]}


def salva_db(db, tipo: str, nome: str, risultato: dict) -> int:
    try:
        cur = db.execute(
            "INSERT INTO documenti_generati (tipo_documento, nome_cantiere, data_generazione, file_path, stato) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"verifica_{tipo}", nome, datetime.now().isoformat(),
             json.dumps(risultato, ensure_ascii=False), "In verifica")
        )
        db.commit()
        return cur.lastrowid
    except Exception as e:
        log.error(f"Errore salvataggio DB: {e}")
        return -1


# ══════════════════════════════════════════════════════════════════════════════
# FUNZIONE CORE: VERIFICA IN DUE PASSAGGI CON LOGGING COMPLETO
# ══════════════════════════════════════════════════════════════════════════════

def verifica_documento_due_passaggi(doc_info: dict, tipo: str, client: anthropic.Anthropic) -> dict:

    log.info(f"{'='*60}")
    log.info(f"INIZIO VERIFICA {tipo.upper()}: {doc_info['filename']}")
    log.info(f"{'='*60}")

    # ── PASSAGGIO 1: ESTRAZIONE ───────────────────────────────────────────────
    log.info("PASSAGGIO 1: ESTRAZIONE CONTENUTO")

    if tipo == "psc":
        prompt_estrazione = """
Leggi attentamente il documento allegato e rispondi SOLO con un JSON che elenca
TUTTO quello che riesci a trovare nel documento, copiando il testo ESATTO presente.

Se un'informazione NON e' presente nel documento, scrivi esattamente: "ASSENTE"
Se un'informazione e' presente ma incompleta, scrivi il testo trovato e aggiungi "(INCOMPLETO)"

{
  "natura_opera": "<testo esatto trovato o ASSENTE>",
  "indirizzo_cantiere": "<testo esatto trovato o ASSENTE>",
  "data_inizio": "<testo esatto trovato o ASSENTE>",
  "data_fine": "<testo esatto trovato o ASSENTE>",
  "durata_uomini_giorno": "<testo esatto trovato o ASSENTE>",
  "n_lavoratori_max": "<testo esatto trovato o ASSENTE>",
  "n_imprese": "<testo esatto trovato o ASSENTE>",
  "importo_lavori": "<testo esatto trovato o ASSENTE>",
  "committente_nome": "<testo esatto trovato o ASSENTE>",
  "committente_cf": "<testo esatto trovato o ASSENTE>",
  "rl_nominato": "<si/no/coincide con committente o ASSENTE>",
  "csp_nome": "<testo esatto trovato o ASSENTE>",
  "csp_ordine": "<testo esatto trovato o ASSENTE>",
  "csp_attestato_120h": "<testo esatto trovato o ASSENTE>",
  "csp_aggiornamento_40h": "<testo esatto trovato o ASSENTE>",
  "cse_nome": "<testo esatto trovato o ASSENTE>",
  "cse_attestato_120h": "<testo esatto trovato o ASSENTE>",
  "imprese_elencate": "<lista imprese con ragione sociale PIVA DL o ASSENTE>",
  "analisi_rischi_area": "<testo trovato sulla sezione rischi area o ASSENTE>",
  "sottoservizi_trattati": "<si con dettaglio / no / ASSENTE>",
  "linee_aeree_trattate": "<si con dettaglio / no / ASSENTE>",
  "traffico_trattato": "<si con dettaglio / no / ASSENTE>",
  "amianto_trattato": "<si con dettaglio inclusa norma citata / no / ASSENTE>",
  "matrice_rischi_presente": "<si/no>",
  "interferenze_trattate": "<testo trovato o ASSENTE>",
  "cronoprogramma_presente": "<si/no>",
  "layout_cantiere": "<si/no>",
  "servizi_igienici": "<testo trovato o ASSENTE>",
  "primo_soccorso": "<testo trovato o ASSENTE>",
  "antincendio": "<testo trovato o ASSENTE>",
  "impianto_elettrico_cantiere": "<testo trovato o ASSENTE>",
  "dpi_elencati": "<lista DPI trovata con norme EN o ASSENTE>",
  "procedure_emergenza": "<testo trovato o ASSENTE>",
  "numeri_emergenza": "<testo trovato o ASSENTE>",
  "costi_sicurezza_totale": "<importo trovato o ASSENTE>",
  "costi_dettagliati": "<si/no>",
  "costi_non_soggetti_ribasso": "<presente nel documento la dicitura / ASSENTE>",
  "note_libere": "<qualsiasi altra informazione rilevante>"
}

IMPORTANTE: Non inventare nulla. Se non trovi l'informazione nel documento, scrivi ASSENTE.
Rispondi SOLO con il JSON, senza testo aggiuntivo.
"""
    else:
        prompt_estrazione = """
Leggi attentamente il documento POS allegato e rispondi SOLO con un JSON.
Per ogni campo copia il testo ESATTO presente nel documento.
Se non trovi l'informazione scrivi: "ASSENTE"

{
  "ragione_sociale": "<testo esatto trovato o ASSENTE>",
  "codice_fiscale": "<testo esatto trovato o ASSENTE>",
  "piva": "<testo esatto trovato o ASSENTE>",
  "sede_legale": "<testo esatto trovato o ASSENTE>",
  "rea_cciaa": "<testo esatto trovato o ASSENTE>",
  "inail_pat": "<testo esatto trovato o ASSENTE>",
  "cassa_edile": "<testo esatto trovato o ASSENTE>",
  "ccnl": "<testo esatto trovato o ASSENTE>",
  "patentino_art27": "<testo esatto trovato o ASSENTE>",
  "datore_lavoro": "<nome e CF trovati o ASSENTE>",
  "rspp_nome": "<testo esatto trovato o ASSENTE>",
  "rspp_attestato": "<testo esatto trovato o ASSENTE>",
  "medico_competente": "<nome trovato o ASSENTE o testo esatto se scritto 'non necessario'>",
  "rls": "<nome trovato o ASSENTE>",
  "preposto": "<nome trovato o ASSENTE>",
  "addetto_ps": "<nome + data attestato trovati o ASSENTE>",
  "addetto_antincendio": "<nome + data attestato trovati o ASSENTE>",
  "descrizione_attivita": "<testo trovato o ASSENTE>",
  "fasi_lavorative": "<testo trovato o ASSENTE>",
  "periodo_intervento": "<date trovate o ASSENTE>",
  "n_lavoratori": "<numero trovato o ASSENTE>",
  "aree_lavoro": "<testo trovato o ASSENTE>",
  "lavoratori": [
    {"nome": "<nome>", "mansione": "<mansione>",
     "idoneita_sanitaria": "<data visita medica e esito ESATTI come nel documento>",
     "formazione_generale": "<data attestato ESATTA come nel documento>",
     "formazione_specifica": "<data attestato ESATTA come nel documento>"}
  ],
  "macchine": [
    {"nome": "<nome macchina>",
     "dichiarazione_ce": "<testo trovato / ASSENTE>",
     "verifica_periodica": "<testo trovato / ASSENTE>"}
  ],
  "sostanze_pericolose": "<lista sostanze con SDS presente/assente per ognuna o ASSENTE>",
  "valutazione_rischi_specifica": "<testo trovato>",
  "rischi_specifici": "<elenco rischi trovati o ASSENTE>",
  "dpi_specifici": "<lista DPI con norme EN o ASSENTE>",
  "interferenze_psc": "<citazione delle prescrizioni PSC trovata o ASSENTE>",
  "piano_emergenze": "<testo trovato o ASSENTE>",
  "punto_raccolta": "<testo trovato o ASSENTE>",
  "numeri_emergenza_completi": "<lista numeri trovata o ASSENTE>",
  "costi_sicurezza": "<importo trovato o ASSENTE>",
  "costi_non_soggetti_ribasso": "<presente nel documento la dicitura / ASSENTE>",
  "note_libere": "<qualsiasi altra informazione rilevante>"
}

Per i lavoratori riporta ESATTAMENTE le date come scritte nel documento.
Rispondi SOLO con il JSON, senza testo aggiuntivo.
"""

    msgs_estrazione = build_messages(doc_info, prompt_estrazione)
    log.info(f"Invio richiesta estrazione a Claude (lunghezza prompt: {len(prompt_estrazione)} chr)")

    r1 = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=(
            "Sei un lettore tecnico preciso. Il tuo compito e' ESTRARRE informazioni da un documento "
            "riportando ESATTAMENTE il testo presente, senza interpretare ne' integrare. "
            "Se un campo non e' presente nel documento scrivi ASSENTE. "
            "Rispondi SOLO con JSON valido."
        ),
        messages=msgs_estrazione,
    )

    raw_estrazione = r1.content[0].text
    log.info(f"RISPOSTA ESTRAZIONE ({len(raw_estrazione)} chr):")
    log.debug(f"TESTO GREZZO ESTRAZIONE:\n{raw_estrazione}")

    estrazione = clean_json(raw_estrazione)
    log.info(f"ESTRAZIONE PARSED OK — campi trovati: {list(estrazione.keys())}")

    # Conta quanti campi sono ASSENTE
    assenti = [k for k, v in estrazione.items()
               if isinstance(v, str) and "ASSENTE" in v.upper()]
    log.info(f"CAMPI ASSENTI ({len(assenti)}): {assenti}")

    # ── PASSAGGIO 2: VERIFICA ─────────────────────────────────────────────────
    log.info("PASSAGGIO 2: VERIFICA SISTEMATICA")

    skill = get_skill()
    skill_preview = skill[:200] if skill else "VUOTA"
    log.info(f"Skill disponibile: {len(skill)} chr. Preview: {skill_preview}...")

    if tipo == "psc":
        prompt_verifica = f"""
{skill}

---

Sei un ispettore senior della sicurezza nei cantieri italiani.
Hai appena estratto il contenuto di un PSC. Ora devi verificarlo.

CONTENUTO ESTRATTO DAL DOCUMENTO (questo e' TUTTO cio' che e' scritto nel documento):
{json.dumps(estrazione, ensure_ascii=False, indent=2)}

ISTRUZIONI CRITICHE:
- I campi con valore "ASSENTE" significano che quella informazione NON E' nel documento
- Ogni campo ASSENTE che e' obbligatorio per legge E' una non conformita' CERTA
- Non assumere che qualcosa ci sia se non e' nell'estrazione
- Sii inflessibile: se manca, segnalalo sempre

VERIFICA OBBLIGATORIA (controlla tutte le 38 voci checklist sezioni A-F):

SEZIONE A — Identificazione opera:
- A1: natura_opera e' ASSENTE? -> CRITICO: All. XV 2.1.2a
- A2: indirizzo_cantiere e' ASSENTE? -> CRITICO
- A3: data_inizio e' ASSENTE? -> CRITICO
- A4: data_fine e' ASSENTE? -> CRITICO
- A5: durata_uomini_giorno e' ASSENTE? -> CRITICO
- A6: n_lavoratori_max e' ASSENTE? -> IMPORTANTE
- A7: n_imprese e' ASSENTE? -> IMPORTANTE

SEZIONE B — Soggetti:
- B1: committente_nome e' ASSENTE? -> CRITICO
- B2: committente_cf e' ASSENTE? -> IMPORTANTE
- B3: rl_nominato e' ASSENTE? -> CRITICO
- B4: csp_nome e' ASSENTE? -> CRITICO
- B5: csp_attestato_120h e' ASSENTE? -> CRITICO: Art. 98
- B6: csp_aggiornamento_40h e' ASSENTE? -> CRITICO: Art. 98
- B7: cse_nome e' ASSENTE? -> CRITICO
- B8: imprese_elencate e' ASSENTE? -> IMPORTANTE

SEZIONE C — Analisi rischi:
- C1: sottoservizi_trattati e' ASSENTE o no? -> se ASSENTE: CRITICO
- C2: linee_aeree_trattate e' ASSENTE? -> CRITICO: Art. 83
- C5: matrice_rischi_presente e' no/ASSENTE? -> CRITICO
- C10: interferenze_trattate e' ASSENTE? -> CRITICO
- C11: cronoprogramma_presente e' no? -> CRITICO

SEZIONE D — Organizzazione:
- D4: layout_cantiere e' ASSENTE? -> IMPORTANTE
- D5: servizi_igienici e' ASSENTE? -> CRITICO
- D6: primo_soccorso e' ASSENTE? -> CRITICO
- D7: antincendio e' ASSENTE? -> CRITICO
- D8: impianto_elettrico_cantiere e' ASSENTE? -> CRITICO

SEZIONE E — Prescrizioni:
- E1: dpi_elencati e' ASSENTE? -> CRITICO
- E4: procedure_emergenza e' ASSENTE? -> CRITICO
- E5: numeri_emergenza e' ASSENTE? -> IMPORTANTE

SEZIONE F — Costi:
- F1: costi_sicurezza_totale e' ASSENTE? -> CRITICO: All. XV punto 4
- F2: costi_dettagliati e' no? -> CRITICO
- F6: costi_non_soggetti_ribasso e' ASSENTE? -> CRITICO: Art. 100 co.1

Per ogni non conformita' trovata includi il testo estratto ("testo_trovato") e proponi il testo corretto.

Rispondi SOLO con JSON valido (nessun testo prima o dopo):
{{
  "documento_analizzato": "PSC",
  "nome_file": "{doc_info['filename']}",
  "data_verifica": "{datetime.now().strftime('%d/%m/%Y %H:%M')}",
  "punteggio_conformita": <0-100>,
  "giudizio_sintetico": "<CONFORME|NON CONFORME|CONFORME CON RISERVE>",
  "non_conformita": [
    {{
      "id": "<es. A1>",
      "sezione": "<nome sezione>",
      "descrizione": "<descrizione specifica>",
      "norma_violata": "<articolo e decreto>",
      "severita": "<CRITICO|IMPORTANTE|CONSIGLIO>",
      "sanzione_applicabile": "<sanzione o null>",
      "testo_trovato": "<valore estratto dal JSON sopra>",
      "testo_corretto": "<testo che dovrebbe essere presente>"
    }}
  ],
  "punti_conformi": [
    {{
      "id": "<es. A2>",
      "sezione": "<sezione>",
      "descrizione": "<cosa e' presente e conforme>"
    }}
  ],
  "riepilogo": {{
    "totale_verifiche": <n>,
    "critici": <n>,
    "importanti": <n>,
    "consigli": <n>,
    "conformi": <n>
  }},
  "note_aggiuntive": "<osservazioni>"
}}
"""
    else:  # pos
        prompt_verifica = f"""
{skill}

---

Sei un ispettore senior della sicurezza nei cantieri italiani.
Hai appena estratto il contenuto di un POS. Ora devi verificarlo.

CONTENUTO ESTRATTO DAL DOCUMENTO (questo e' TUTTO cio' che e' scritto nel documento):
{json.dumps(estrazione, ensure_ascii=False, indent=2)}

ISTRUZIONI CRITICHE:
- I campi con valore "ASSENTE" significano che quella informazione NON E' nel documento
- Ogni campo ASSENTE obbligatorio per legge E' una non conformita' CERTA
- Non assumere che qualcosa ci sia se non e' nell'estrazione

REGOLE SPECIFICHE POS:
1. medico_competente = "non necessario" o simile: le lavorazioni elettriche/edili prevedono 
   SEMPRE sorveglianza sanitaria obbligatoria -> CRITICO se non nominato
2. Per ogni lavoratore in "lavoratori": controlla la data di idoneita_sanitaria
   - Se data precedente al 2023 -> visita PROBABILMENTE SCADUTA -> CRITICO per quel lavoratore
   - Se "non disponibile" o ASSENTE -> CRITICO
3. Per ogni lavoratore: se formazione_generale o formazione_specifica e' ASSENTE -> CRITICO
4. Per ogni macchina in "macchine": se dichiarazione_ce e' ASSENTE -> CRITICO
5. costi_non_soggetti_ribasso ASSENTE -> CRITICO: Art. 100 co.1
6. interferenze_psc ASSENTE -> IMPORTANTE: prescrizioni PSC non recepite
7. patentino_art27 ASSENTE -> IMPORTANTE: obbligatorio dal 1/10/2024

Rispondi SOLO con JSON valido (nessun testo prima o dopo):
{{
  "documento_analizzato": "POS",
  "nome_file": "{doc_info['filename']}",
  "impresa": "<ragione sociale estratta>",
  "data_verifica": "{datetime.now().strftime('%d/%m/%Y %H:%M')}",
  "punteggio_conformita": <0-100>,
  "giudizio_sintetico": "<CONFORME|NON CONFORME|CONFORME CON RISERVE>",
  "non_conformita": [
    {{
      "id": "<es. H3>",
      "sezione": "<nome sezione>",
      "descrizione": "<descrizione specifica con nome del lavoratore se applicabile>",
      "norma_violata": "<articolo e decreto>",
      "severita": "<CRITICO|IMPORTANTE|CONSIGLIO>",
      "sanzione_applicabile": "<sanzione o null>",
      "testo_trovato": "<valore estratto dal JSON sopra>",
      "testo_corretto": "<testo che dovrebbe essere presente>"
    }}
  ],
  "punti_conformi": [
    {{
      "id": "<es. G1>",
      "sezione": "<sezione>",
      "descrizione": "<cosa e' conforme>"
    }}
  ],
  "riepilogo": {{
    "totale_verifiche": <n>,
    "critici": <n>,
    "importanti": <n>,
    "consigli": <n>,
    "conformi": <n>
  }},
  "note_aggiuntive": "<osservazioni>"
}}
"""

    log.info(f"Invio richiesta verifica a Claude (lunghezza prompt: {len(prompt_verifica)} chr)")

    msgs_verifica = [{"role": "user", "content": prompt_verifica}]
    r2 = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=(
            "Sei un ispettore senior della sicurezza nei cantieri italiani con 25 anni di esperienza. "
            "Sei INFLESSIBILE e SCRUPOLOSO: segnali OGNI non conformita'. "
            "Basi la verifica ESCLUSIVAMENTE sui dati estratti forniti nel prompt. "
            "Un campo ASSENTE nell'estrazione significa che quell'informazione NON E' nel documento. "
            "Non inventare, non assumere, non essere benevolo. "
            "Rispondi SOLO con JSON valido, senza NESSUN testo prima o dopo le parentesi graffe."
        ),
        messages=msgs_verifica,
    )

    raw_verifica = r2.content[0].text
    log.info(f"RISPOSTA VERIFICA ({len(raw_verifica)} chr):")
    log.debug(f"TESTO GREZZO VERIFICA:\n{raw_verifica}")

    risultato = clean_json(raw_verifica)

    # Log riassuntivo
    nc = risultato.get("non_conformita", [])
    pc = risultato.get("punti_conformi", [])
    rie = risultato.get("riepilogo", {})
    log.info(
        f"RISULTATO FINALE:\n"
        f"  Giudizio: {risultato.get('giudizio_sintetico')}\n"
        f"  Punteggio: {risultato.get('punteggio_conformita')}%\n"
        f"  Non conformita': {len(nc)} (critici={rie.get('critici',0)}, "
        f"importanti={rie.get('importanti',0)}, consigli={rie.get('consigli',0)})\n"
        f"  Punti conformi: {len(pc)}"
    )
    if nc:
        log.info("NON CONFORMITA' TROVATE:")
        for item in nc:
            log.info(f"  [{item.get('severita')}] {item.get('id')} — {item.get('descrizione','')[:80]}")

    return risultato


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1 — VERIFICA PSC
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/verifica-psc")
async def verifica_psc(
    file: UploadFile = File(...),
    nome_cantiere: str = Form(default="Cantiere"),
):
    file_bytes = await file.read()
    doc_info = leggi_documento(file_bytes, file.filename)
    client = anthropic.Anthropic()
    risultato = verifica_documento_due_passaggi(doc_info, "psc", client)
    db = get_db()
    doc_id = salva_db(db, "psc", nome_cantiere, risultato)
    risultato["doc_id"] = doc_id
    return risultato


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2 — VERIFICA POS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/verifica-pos")
async def verifica_pos(
    files: List[UploadFile] = File(...),
    nome_cantiere: str = Form(default="Cantiere"),
):
    if len(files) > 5:
        raise HTTPException(400, "Massimo 5 POS per volta.")
    client = anthropic.Anthropic()
    db = get_db()
    risultati = []
    for file in files:
        file_bytes = await file.read()
        doc_info = leggi_documento(file_bytes, file.filename)
        ris = verifica_documento_due_passaggi(doc_info, "pos", client)
        doc_id = salva_db(db, "pos", nome_cantiere, ris)
        ris["doc_id"] = doc_id
        risultati.append(ris)
    return {"risultati": risultati, "totale_pos": len(risultati)}


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3 — VERIFICA CONGRUITA' POS-PSC
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/verifica-congruita")
async def verifica_congruita(
    psc: UploadFile = File(...),
    pos_files: List[UploadFile] = File(...),
    nome_cantiere: str = Form(default="Cantiere"),
):
    if len(pos_files) > 5:
        raise HTTPException(400, "Massimo 5 POS per volta.")

    client = anthropic.Anthropic()
    db = get_db()
    skill = get_skill()

    psc_bytes = await psc.read()
    psc_info = leggi_documento(psc_bytes, psc.filename)

    log.info(f"VERIFICA CONGRUITA': PSC={psc.filename}, POS={[f.filename for f in pos_files]}")

    prompt_est_psc = """
Leggi questo PSC e riassumi in JSON i punti chiave:
{
  "cantiere": "<indirizzo e committente>",
  "date_lavori": "<data inizio e fine>",
  "imprese_e_attivita": "<per ogni impresa: ragione sociale, attivita' assegnata, periodo, aree>",
  "dpi_obbligatori": "<lista DPI minimi prescritti per tutti>",
  "procedure_coordinamento": "<regole di coordinamento tra imprese>",
  "interferenze": "<prescrizioni specifiche per le sovrapposizioni>",
  "piano_emergenze": "<procedure e punto raccolta>",
  "numeri_emergenza": "<lista completa numeri incluso CSE>",
  "costi_sicurezza_totale": "<importo>"
}
Rispondi SOLO con JSON valido.
"""
    r_psc = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=3000,
        system="Estrai informazioni da documenti tecnici. Rispondi SOLO con JSON valido.",
        messages=build_messages(psc_info, prompt_est_psc),
    )
    psc_estratto = clean_json(r_psc.content[0].text)
    log.info(f"PSC estratto: {json.dumps(psc_estratto, ensure_ascii=False)[:300]}")

    risultati_congruita = []

    for pos_file in pos_files:
        pos_bytes = await pos_file.read()
        pos_info = leggi_documento(pos_bytes, pos_file.filename)

        prompt_est_pos = """
Leggi questo POS e riassumi in JSON:
{
  "impresa": "<ragione sociale>",
  "cantiere": "<indirizzo cantiere>",
  "periodo_intervento": "<date inizio e fine>",
  "attivita_descritte": "<lavorazioni descritte>",
  "aree_indicate": "<aree di lavoro>",
  "dpi_prescritti": "<DPI con norme EN>",
  "interferenze_citate": "<prescrizioni PSC citate o ASSENTE>",
  "piano_emergenze_pos": "<procedure presenti>",
  "punto_raccolta": "<indicato o ASSENTE>",
  "numeri_emergenza": "<lista numeri incluso CSE o ASSENTE>"
}
Rispondi SOLO con JSON valido.
"""
        r_pos = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=2000,
            system="Estrai informazioni da documenti tecnici. Rispondi SOLO con JSON valido.",
            messages=build_messages(pos_info, prompt_est_pos),
        )
        pos_estratto = clean_json(r_pos.content[0].text)
        log.info(f"POS estratto ({pos_file.filename}): {json.dumps(pos_estratto, ensure_ascii=False)[:300]}")

        prompt_cong = f"""
{skill}

---

Sei un ispettore senior. Verifica la CONGRUITA' del POS rispetto al PSC.

PSC — {psc.filename}:
{json.dumps(psc_estratto, ensure_ascii=False, indent=2)}

POS — {pos_file.filename}:
{json.dumps(pos_estratto, ensure_ascii=False, indent=2)}

REGOLE ZERO-TRUST:
1. Date POS fuori dal range PSC -> CRITICO
2. Attivita' POS non previste nel PSC -> CRITICO
3. DPI POS inferiori al minimo PSC -> CRITICO
4. interferenze_citate = ASSENTE -> CRITICO: prescrizioni PSC non recepite
5. piano_emergenze_pos non allineato al PSC -> IMPORTANTE
6. punto_raccolta ASSENTE -> IMPORTANTE
7. Numero CSE non nei numeri_emergenza -> IMPORTANTE

Rispondi SOLO con JSON valido:
{{
  "pos_analizzato": "{pos_file.filename}",
  "psc_riferimento": "{psc.filename}",
  "data_verifica": "{datetime.now().strftime('%d/%m/%Y %H:%M')}",
  "giudizio": "CONGRUENTE|NON CONGRUENTE|CONGRUENTE CON RISERVE",
  "incongruenze": [
    {{
      "id": "INC-01",
      "elemento": "elemento verificato",
      "valore_psc": "valore nel PSC",
      "valore_pos": "valore nel POS",
      "descrizione": "descrizione precisa",
      "severita": "CRITICO|IMPORTANTE|CONSIGLIO",
      "modifica_richiesta": "testo da inserire nel POS",
      "sezione_pos_da_modificare": "sezione del POS",
      "validata": false,
      "nota_utente": ""
    }}
  ],
  "elementi_congruenti": [
    {{"elemento": "elemento", "descrizione": "congruenza"}}
  ],
  "riepilogo": {{
    "totale_verifiche": 10,
    "critici": 0,
    "importanti": 0,
    "consigli": 0,
    "congruenti": 0
  }}
}}
"""
        r_cong = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=6000,
            system="Sei un ispettore senior inflessibile. Segnali ogni incongruenza. Rispondi SOLO con JSON valido.",
            messages=[{"role": "user", "content": prompt_cong}],
        )
        raw_cong = r_cong.content[0].text
        log.debug(f"RISPOSTA CONGRUITA' GREZZA:\n{raw_cong}")
        ris = clean_json(raw_cong)
        log.info(f"Congruita' {pos_file.filename}: {ris.get('giudizio')} — {len(ris.get('incongruenze',[]))} incongruenze")

        doc_id = salva_db(db, "congruita", nome_cantiere, ris)
        ris["doc_id"] = doc_id
        ris["pos_filename"] = pos_file.filename
        risultati_congruita.append(ris)

    return {"psc_filename": psc.filename, "risultati": risultati_congruita, "totale_pos": len(risultati_congruita)}


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 4 — GENERA VERBALE PDF
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/genera-verbale")
async def genera_verbale(payload: dict):
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
        "INSERT INTO documenti_generati (tipo_documento, nome_cantiere, data_generazione, file_path, stato) "
        "VALUES (?, ?, ?, ?, ?)",
        ("verbale_incongruenze", payload.get("nome_cantiere", "Cantiere"),
         datetime.now().isoformat(), path, "Generato")
    )
    db.commit()
    return {"doc_id": cur.lastrowid, "path": path}

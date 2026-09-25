"""
services/documenti_progetto.py — Lettura dei documenti di un progetto PSC

- riconosce formato, numero di pagine e presenza di testo
- divide i PDF in blocchi da massimo 100 pagine (limite API)
- invia come IMMAGINE (documento PDF visivo) i PDF senza testo e le tavole grafiche,
  come TESTO i documenti testuali (più economico)
- classifica i documenti con una sola chiamata Haiku per gruppo di file
- estrae il "fascicolo" di dati utili al PSC da ogni blocco
"""
import base64
import io
import json
import re

MODELLO = "claude-haiku-4-5-20251001"

# codice: (etichetta, priorità di elaborazione, modalità)
#   modalità: testo | visivo | elenco (nessuna AI)
TIPI = {
    "elenco_prezzi":        ("Elenco prezzi",                    0,  "elenco"),
    "contratto":            ("Contratto d'appalto",              1,  "testo"),
    "relazione_tecnica":    ("Relazione tecnica / illustrativa", 2,  "testo"),
    "computo":              ("Computo metrico",                  3,  "testo"),
    "cronoprogramma":       ("Cronoprogramma",                   4,  "testo"),
    "capitolato":           ("Capitolato",                       5,  "testo"),
    "relazione_specialistica": ("Relazione specialistica (geologica, strutturale, impianti)", 6, "testo"),
    "titolo_edilizio":      ("Titolo edilizio (PdC, SCIA, CILA)", 7, "testo"),
    "visura_camerale":      ("Visura camerale / documenti impresa", 7, "testo"),
    "altro":                ("Altro documento",                  8,  "testo"),
    "tavola":               ("Tavola grafica",                   9,  "visivo"),
    "foto":                 ("Foto sopralluogo",                 10, "visivo"),
}

ESTENSIONI_AMMESSE = {"pdf", "docx", "xlsx", "xls", "ods", "xml", "jpg", "jpeg", "png"}
PAGINE_PER_BLOCCO = 100
MAX_BYTES_BLOCCO = 24 * 1024 * 1024       # margine sotto il limite di 32 MB per richiesta
CARATTERI_PER_BLOCCO = 150_000            # ~45.000 token per blocco testuale
TOKEN_PER_PAGINA_VISIVA = 2000
TOKEN_PER_IMMAGINE = 1600
OUTPUT_TOKEN_ESTRAZIONE = 6000
OUTPUT_TOKEN_STIMA = 2500                 # output medio atteso, per la stima prima della chiamata


def etichetta(tipo: str) -> str:
    return TIPI.get(tipo, TIPI["altro"])[0]


def priorita(tipo: str) -> int:
    return TIPI.get(tipo, TIPI["altro"])[1]


def modalita(tipo: str) -> str:
    return TIPI.get(tipo, TIPI["altro"])[2]


# ══════════════════════════════════════════════════════════════════════════════
# Analisi locale del file (senza AI)
# ══════════════════════════════════════════════════════════════════════════════

def _testo_pagine_pdf(contenuto: bytes) -> list:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(contenuto))
    pagine = []
    for p in reader.pages:
        try:
            pagine.append(p.extract_text() or "")
        except Exception:
            pagine.append("")
    return pagine


def analizza_file(contenuto: bytes, nome_file: str) -> dict:
    """Pagine, presenza di testo e anteprima testuale (per la classificazione)."""
    est = nome_file.lower().rsplit(".", 1)[-1]
    info = {"estensione": est, "pagine": None, "ha_testo": None, "anteprima": ""}
    try:
        if est == "pdf":
            pagine = _testo_pagine_pdf(contenuto)
            info["pagine"] = len(pagine)
            con_testo = sum(1 for t in pagine if len(t.strip()) > 80)
            # PDF "con testo" se almeno l'80% delle pagine ne contiene
            info["ha_testo"] = bool(pagine) and con_testo / len(pagine) >= 0.8
            info["anteprima"] = "\n".join(pagine[:3])[:2500]
        elif est == "docx":
            info["ha_testo"] = True
            info["anteprima"] = testo_docx(contenuto)[:2500]
        elif est in ("xlsx", "xls", "ods"):
            info["ha_testo"] = True
            info["anteprima"] = testo_foglio(contenuto, est)[:2500]
        elif est == "xml":
            info["ha_testo"] = True
            info["anteprima"] = contenuto[:2500].decode("utf-8", errors="ignore")
        elif est in ("jpg", "jpeg", "png"):
            info["ha_testo"] = False
    except Exception as e:
        info["errore_lettura"] = str(e)
    return info


def testo_docx(contenuto: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(contenuto))
    righe = [p.text for p in doc.paragraphs if p.text.strip()]
    for t in doc.tables:
        for r in t.rows:
            celle = [c.text.strip() for c in r.cells if c.text.strip()]
            if celle:
                righe.append(" | ".join(celle))
    return "\n".join(righe)


def testo_foglio(contenuto: bytes, est: str) -> str:
    import pandas as pd
    engine = {"ods": "odf", "xls": "xlrd", "xlsx": "openpyxl"}[est]
    fogli = pd.read_excel(io.BytesIO(contenuto), engine=engine, header=None, dtype=object, sheet_name=None)
    righe = []
    for nome, df in fogli.items():
        righe.append(f"[Foglio: {nome}]")
        for r in df.itertuples(index=False):
            celle = [str(c).strip() for c in r if c is not None and str(c) != "nan" and str(c).strip()]
            if celle:
                righe.append(" | ".join(celle))
    return "\n".join(righe)


def _immagine_jpeg(contenuto: bytes, lato_max: int = 1568) -> bytes:
    """Ridimensiona per restare nei limiti dell'API (5 MB, ~1568 px) e ridurre i token."""
    from PIL import Image
    img = Image.open(io.BytesIO(contenuto))
    img = img.convert("RGB")
    img.thumbnail((lato_max, lato_max))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def miniatura_prima_pagina(contenuto: bytes) -> bytes:
    """Prima pagina di un PDF come JPEG piccolo, per classificare i PDF senza testo."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(contenuto)
    pagina = pdf[0]
    img = pagina.render(scale=0.8).to_pil()
    img.thumbnail((800, 800))
    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=70)
    return out.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# Suddivisione in blocchi
# ══════════════════════════════════════════════════════════════════════════════

def _pdf_sottoinsieme(contenuto: bytes, da: int, a: int) -> bytes:
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(contenuto))
    writer = PdfWriter()
    for i in range(da, a):
        writer.add_page(reader.pages[i])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _blocchi_pdf_visivi(contenuto: bytes, n_pagine: int) -> list:
    blocchi, da = [], 0
    while da < n_pagine:
        passo = PAGINE_PER_BLOCCO
        while True:
            a = min(da + passo, n_pagine)
            dati = _pdf_sottoinsieme(contenuto, da, a) if (da, a) != (0, n_pagine) else contenuto
            if len(dati) <= MAX_BYTES_BLOCCO or passo <= 5:
                break
            passo = max(5, passo // 2)       # blocco troppo pesante: dimezzo le pagine
        blocchi.append({
            "pagine_da": da + 1, "pagine_a": a,
            "contenuto": [{
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf",
                           "data": base64.standard_b64encode(dati).decode()},
            }],
            "stima_input": (a - da) * TOKEN_PER_PAGINA_VISIVA,
        })
        da = a
    return blocchi


def _blocchi_testo(testo: str, etichetta_unita: str = "Parte") -> list:
    blocchi = []
    for i in range(0, max(len(testo), 1), CARATTERI_PER_BLOCCO):
        parte = testo[i:i + CARATTERI_PER_BLOCCO]
        blocchi.append({
            "pagine_da": None, "pagine_a": None,
            "contenuto": [{"type": "text", "text": parte}],
            "stima_input": int(len(parte) / 3.2),
        })
    return blocchi


def prepara_blocchi(contenuto: bytes, nome_file: str, tipo: str) -> list:
    est = nome_file.lower().rsplit(".", 1)[-1]
    mod = modalita(tipo)

    if est in ("jpg", "jpeg", "png"):
        jpeg = _immagine_jpeg(contenuto)
        return [{
            "pagine_da": 1, "pagine_a": 1,
            "contenuto": [{"type": "image",
                           "source": {"type": "base64", "media_type": "image/jpeg",
                                      "data": base64.standard_b64encode(jpeg).decode()}}],
            "stima_input": TOKEN_PER_IMMAGINE,
        }]

    if est == "pdf":
        pagine = _testo_pagine_pdf(contenuto)
        con_testo = sum(1 for t in pagine if len(t.strip()) > 80)
        ha_testo = bool(pagine) and con_testo / len(pagine) >= 0.8
        if mod == "visivo" or not ha_testo:
            return _blocchi_pdf_visivi(contenuto, len(pagine))
        # PDF testuale: blocchi da 100 pagine di testo, con i numeri di pagina
        blocchi = []
        for da in range(0, len(pagine), PAGINE_PER_BLOCCO):
            a = min(da + PAGINE_PER_BLOCCO, len(pagine))
            testo = "\n".join(f"[Pagina {i + 1}]\n{pagine[i]}" for i in range(da, a))
            blocchi.append({
                "pagine_da": da + 1, "pagine_a": a,
                "contenuto": [{"type": "text", "text": testo}],
                "stima_input": int(len(testo) / 3.2),
            })
        return blocchi

    if est == "docx":
        return _blocchi_testo(testo_docx(contenuto))
    if est in ("xlsx", "xls", "ods"):
        return _blocchi_testo(testo_foglio(contenuto, est))
    if est == "xml":
        return _blocchi_testo(contenuto.decode("utf-8", errors="ignore"))
    raise ValueError(f"Formato non supportato: .{est}")


# ══════════════════════════════════════════════════════════════════════════════
# Classificazione (una chiamata per gruppo di file)
# ══════════════════════════════════════════════════════════════════════════════

def costruisci_richiesta_classificazione(documenti: list) -> list:
    """
    documenti: [{"id", "nome_file", "anteprima", "miniatura" (bytes|None)}]
    Restituisce il contenuto del messaggio utente.
    """
    elenco_tipi = "\n".join(f"- {k}: {v[0]}" for k, v in TIPI.items() if k != "foto")
    contenuto = [{"type": "text", "text": (
        "Classifica ciascun documento di un progetto edilizio in UNO di questi tipi:\n"
        f"{elenco_tipi}\n\n"
        "Rispondi SOLO con JSON: {\"documenti\": [{\"id\": <id>, \"tipo\": \"<codice>\"}]}\n"
        "Usa 'tavola' per disegni tecnici (piante, sezioni, prospetti, planimetrie). "
        "Usa 'altro' se non riconosci il documento.\n\nDOCUMENTI:"
    )}]
    for d in documenti:
        contenuto.append({"type": "text", "text":
            f"\n--- id={d['id']} · file: {d['nome_file']} ---\n{(d.get('anteprima') or '')[:1500]}"})
        if d.get("miniatura"):
            contenuto.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg",
                "data": base64.standard_b64encode(d["miniatura"]).decode()}})
    return contenuto


def interpreta_classificazione(testo: str) -> dict:
    dati = pulisci_json(testo)
    risultato = {}
    for d in (dati or {}).get("documenti", []):
        tipo = d.get("tipo")
        risultato[int(d["id"])] = tipo if tipo in TIPI else "altro"
    return risultato


# ══════════════════════════════════════════════════════════════════════════════
# Estrazione del fascicolo PSC
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_ESTRAZIONE = (
    "Sei un tecnico che prepara il fascicolo di dati per un Piano di Sicurezza e Coordinamento "
    "(D.Lgs. 81/2008, Allegato XV). Estrai SOLO informazioni presenti nel documento: non inventare "
    "e non dedurre. Indica la pagina di provenienza quando possibile. Rispondi SOLO con JSON valido."
)

PROMPT_ESTRAZIONE = """Tipo di documento: {tipo}
File: {nome_file}{pagine}

Estrai i dati utili al PSC in questo JSON (ometti le sezioni vuote, liste vuote ammesse):
{{
  "sintesi": "3-5 frasi su cosa contiene il documento",
  "dati_generali": {{"committente": "", "indirizzo_cantiere": "", "comune": "", "provincia": "",
                     "importo_lavori": "", "importo_sicurezza": "", "data_inizio": "", "data_fine": "",
                     "durata": "", "titolo_edilizio": "",
                     "importo_manodopera": "", "incidenza_manodopera_percentuale": ""}},
  "soggetti": [{{"ruolo": "committente|responsabile_lavori|progettista|direttore_lavori|CSP|CSE|impresa_affidataria|impresa_esecutrice|lavoratore_autonomo|altro",
                 "nome": "", "dettagli": ""}}],
  "opera": {{"descrizione": "", "tipologia_intervento": "", "anno_costruzione": "", "numero_piani": "",
             "altezza_gronda_m": "", "altezza_colmo_m": "", "superfici": "", "struttura": "", "copertura": ""}},
  "lavorazioni": [{{"descrizione": "", "quantita": "", "um": "", "pagina": ""}}],
  "area_cantiere": {{"accessi": "", "viabilita": "", "edifici_confinanti": "", "sottoservizi": "",
                     "linee_aeree": "", "vincoli": "", "spazi_disponibili": ""}},
  "rischi_segnalati": [{{"descrizione": "", "pagina": ""}}],
  "indizi_amianto": [{{"descrizione": "", "pagina": ""}}],
  "cronoprogramma": [{{"fase": "", "inizio": "", "fine": "", "durata": ""}}],
  "misure_da_elaborati": [{{"elemento": "", "valore": "", "pagina": "", "da_confermare": true}}],
  "dati_da_verificare": ["informazioni necessarie al PSC che il documento non chiarisce"]
}}
Per le misure lette da disegni o immagini imposta sempre "da_confermare": true."""


def costruisci_richiesta_estrazione(blocco: dict, nome_file: str, tipo: str) -> list:
    pagine = ""
    if blocco.get("pagine_da"):
        pagine = f" (pagine {blocco['pagine_da']}-{blocco['pagine_a']})"
    return blocco["contenuto"] + [{"type": "text", "text": PROMPT_ESTRAZIONE.format(
        tipo=etichetta(tipo), nome_file=nome_file, pagine=pagine)}]


def _prova_json(testo: str):
    """json.loads tollerante: a capo e tabulazioni dentro le stringhe (strict=False) e virgole finali."""
    for candidato in (testo, re.sub(r",\s*([}\]])", r"\1", testo)):
        try:
            return json.loads(candidato, strict=False)
        except json.JSONDecodeError:
            continue
    return None


def pulisci_json(testo: str):
    """Legge il JSON della risposta AI tollerando i difetti più comuni, per non dover ripetere
    (e pagare di nuovo) una chiamata andata a buon fine."""
    testo = (testo or "").strip()
    testo = re.sub(r"^```(?:json)?\s*", "", testo)
    testo = re.sub(r"\s*```\s*$", "", testo)
    dati = _prova_json(testo)
    if dati is None:
        m = re.search(r"\{.*\}", testo, re.DOTALL)
        if m:
            dati = _prova_json(m.group(0))
    return dati

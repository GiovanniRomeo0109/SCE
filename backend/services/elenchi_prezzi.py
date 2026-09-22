"""
services/elenchi_prezzi.py — Lettura degli elenchi prezzi (nessuna chiamata AI, costo zero)

Formati supportati:
  - XML  : schema dei prezzari regionali (<prezzario><settore><capitolo><paragrafo><prezzi><prezzo .../>)
  - ODS, XLS, XLSX : riconoscimento automatico delle colonne Codice / Descrizione / UM / Prezzo;
                     se non riconosciute → il CSP associa le colonne a mano (mappatura)
  - PDF  : solo PDF con testo (estrazione righe/tabelle). I PDF scansionati non sono supportati.

Ogni voce: {codice, descrizione, um, prezzo, perc_manodopera, capitolo}
"""
import io
import re
import xml.etree.ElementTree as ET

# ── Riconoscimento intestazioni ───────────────────────────────────────────────
SINONIMI = {
    "codice":          ["codice", "cod", "cod.", "articolo", "art", "art.", "voce", "n. voce", "tariffa", "id"],
    "descrizione":     ["descrizione", "desc", "descrizione voce", "designazione", "descrizione estesa"],
    "um":              ["um", "u.m.", "u.m", "umi", "unita di misura", "unità di misura", "unita", "unità", "misura"],
    "prezzo":          ["prezzo", "prezzo unitario", "importo unitario", "prezzo €", "€", "euro", "p.u.", "pu", "importo"],
    "perc_manodopera": ["% man.", "% man", "%man", "manodopera", "% manodopera", "inc. man.", "incidenza manodopera"],
}
CAMPI_OBBLIGATORI = ["codice", "descrizione", "um", "prezzo"]


class MappaturaRichiesta(Exception):
    """Le colonne non sono state riconosciute: serve l'associazione manuale del CSP."""
    def __init__(self, anteprima: list, n_colonne: int):
        super().__init__("Colonne non riconosciute")
        self.anteprima = anteprima
        self.n_colonne = n_colonne


class FormatoNonSupportato(Exception):
    pass


def _norm(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().lower()


def _numero(v):
    """Converte '1.234,56' / '35.78' / 35.78 in float; None se non numerico."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return None if v != v else float(v)   # scarta NaN
    s = str(v).strip().replace("€", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _testo(v) -> str:
    """Testo pulito: spazi speciali (\xa0) e spazi multipli normalizzati."""
    return re.sub(r"\s+", " ", str(v).replace("\xa0", " ")).strip()


def _vuoto(v) -> bool:
    return v is None or (isinstance(v, float) and v != v) or str(v).strip() == ""


# ══════════════════════════════════════════════════════════════════════════════
# XML (prezzari regionali)
# ══════════════════════════════════════════════════════════════════════════════

def leggi_xml(contenuto: bytes) -> list:
    try:
        root = ET.fromstring(contenuto)
    except ET.ParseError as e:
        raise FormatoNonSupportato(f"XML non valido: {e}")
    if not root.findall(".//prezzo"):
        raise FormatoNonSupportato("XML senza voci <prezzo>: formato non riconosciuto")

    voci = []
    for capitolo in root.iter("capitolo"):
        cap_desc = capitolo.get("desc", "")
        for par in capitolo.iter("paragrafo"):
            estesa = (par.findtext("estesa") or par.findtext("sint") or "").strip()
            for p in par.iter("prezzo"):
                testo = (p.text or "").strip()
                # La descrizione estesa del paragrafo dà il contesto, il testo della voce la variante
                if estesa and testo and not testo.lower().startswith(estesa.lower()[:30]):
                    descr = f"{estesa} — {testo}"
                else:
                    descr = testo or estesa
                voci.append({
                    "codice": p.get("cod", ""),
                    "descrizione": descr,
                    "um": p.get("umi", ""),
                    "prezzo": _numero(p.get("val")),
                    "perc_manodopera": _numero(p.get("man")),
                    "capitolo": cap_desc,
                })
    return [v for v in voci if v["codice"] and v["prezzo"] is not None]


# ══════════════════════════════════════════════════════════════════════════════
# Fogli di calcolo (ODS / XLS / XLSX)
# ══════════════════════════════════════════════════════════════════════════════

def _leggi_foglio(contenuto: bytes, estensione: str):
    import pandas as pd
    engine = {"ods": "odf", "xls": "xlrd", "xlsx": "openpyxl"}.get(estensione)
    if not engine:
        raise FormatoNonSupportato(f"Estensione non supportata: {estensione}")
    df = pd.read_excel(io.BytesIO(contenuto), engine=engine, header=None, dtype=object)
    return df.where(df.notna(), None).values.tolist()


def _trova_intestazione(righe: list):
    """Cerca nelle prime 30 righe una riga che contenga tutte le intestazioni obbligatorie."""
    for i, riga in enumerate(righe[:30]):
        mappa = {}
        for j, cella in enumerate(riga):
            c = _norm(cella)
            if not c:
                continue
            for campo, sinonimi in SINONIMI.items():
                if campo not in mappa and c in sinonimi:
                    mappa[campo] = j
        if all(k in mappa for k in CAMPI_OBBLIGATORI):
            return i, mappa
    return None, None


def _estrai_righe(righe: list, riga_intestazione: int, mappa: dict) -> list:
    voci, capitolo = [], ""
    for riga in righe[riga_intestazione + 1:]:
        def cella(campo):
            j = mappa.get(campo)
            return riga[j] if j is not None and j < len(riga) else None
        codice, descr = cella("codice"), cella("descrizione")
        prezzo = _numero(cella("prezzo"))
        if _vuoto(codice) and _vuoto(descr):
            continue
        if prezzo is None:
            # Riga di capitolo/paragrafo senza prezzo: la uso come contesto
            if not _vuoto(descr):
                capitolo = _testo(descr)
            continue
        voci.append({
            "codice": "" if _vuoto(codice) else _testo(codice),
            "descrizione": "" if _vuoto(descr) else _testo(descr),
            "um": "" if _vuoto(cella("um")) else _testo(cella("um")),
            "prezzo": prezzo,
            "perc_manodopera": _numero(cella("perc_manodopera")),
            "capitolo": capitolo,
        })
    return [v for v in voci if v["codice"] or v["descrizione"]]


def leggi_foglio(contenuto: bytes, estensione: str, mappatura: dict = None) -> list:
    """
    mappatura (facoltativa, dal CSP): {"riga_intestazione": int,
        "codice": col, "descrizione": col, "um": col, "prezzo": col, "perc_manodopera": col|None}
    """
    righe = _leggi_foglio(contenuto, estensione)
    if mappatura:
        mappa = {k: mappatura[k] for k in SINONIMI if mappatura.get(k) is not None}
        return _estrai_righe(righe, int(mappatura.get("riga_intestazione", -1)), mappa)

    i, mappa = _trova_intestazione(righe)
    if mappa is None:
        n_col = max((len(r) for r in righe[:40]), default=0)
        anteprima = [["" if _vuoto(c) else str(c)[:80] for c in r] for r in righe[:15]]
        raise MappaturaRichiesta(anteprima, n_col)
    return _estrai_righe(righe, i, mappa)


# ══════════════════════════════════════════════════════════════════════════════
# PDF con testo
# ══════════════════════════════════════════════════════════════════════════════

_UM = r"(?:m²|m³|m2|m3|mq|mc|ml|m|kg|t|q|h|ora|ore|cad|cad\.|nr|n\.|n|pz|corpo|a corpo|%|l|lt|km|gg|giorno|mese|cm)"
_RIGA_PDF = re.compile(
    rf"^(?P<codice>[A-Z0-9][A-Z0-9.\-/_]{{2,}})\s+(?P<descr>.+?)\s+(?P<um>{_UM})\s+"
    rf"(?P<prezzo>\d{{1,3}}(?:\.\d{{3}})*,\d{{2}}|\d+[.,]\d{{2}})(?:\s+(?P<man>\d{{1,3}}(?:[.,]\d+)?)\s*%?)?$",
    re.IGNORECASE,
)


def leggi_pdf(contenuto: bytes) -> list:
    import pdfplumber
    voci, capitolo, righe_testo = [], "", 0
    with pdfplumber.open(io.BytesIO(contenuto)) as pdf:
        for pagina in pdf.pages:
            testo = pagina.extract_text() or ""
            righe_testo += len(testo.strip())
            for riga in testo.splitlines():
                riga = riga.strip()
                m = _RIGA_PDF.match(riga)
                if m:
                    voci.append({
                        "codice": m.group("codice"),
                        "descrizione": m.group("descr").strip(),
                        "um": m.group("um"),
                        "prezzo": _numero(m.group("prezzo")),
                        "perc_manodopera": _numero(m.group("man")),
                        "capitolo": capitolo,
                    })
                elif riga and riga.isupper() and len(riga) < 120:
                    capitolo = riga
    if righe_testo < 200:
        raise FormatoNonSupportato(
            "Il PDF non contiene testo (probabilmente è scansionato). "
            "Carica l'elenco prezzi in formato XML, ODS o Excel."
        )
    if len(voci) < 3:
        raise FormatoNonSupportato(
            "Non sono riuscito a riconoscere le voci di prezzo nel PDF. "
            "Carica l'elenco prezzi in formato XML, ODS o Excel."
        )
    return voci


# ══════════════════════════════════════════════════════════════════════════════
# Ingresso unico
# ══════════════════════════════════════════════════════════════════════════════

def leggi_elenco(contenuto: bytes, nome_file: str, mappatura: dict = None) -> list:
    est = nome_file.lower().rsplit(".", 1)[-1]
    if est == "xml":
        return leggi_xml(contenuto)
    if est in ("ods", "xls", "xlsx"):
        return leggi_foglio(contenuto, est, mappatura)
    if est == "pdf":
        return leggi_pdf(contenuto)
    raise FormatoNonSupportato(f"Formato non supportato per un elenco prezzi: .{est}")


def sembra_elenco_prezzi(contenuto: bytes, nome_file: str) -> bool:
    """Riconoscimento locale (senza AI) per XML e fogli di calcolo."""
    est = nome_file.lower().rsplit(".", 1)[-1]
    try:
        if est == "xml":
            return b"<prezzo" in contenuto[:200000]
        if est in ("ods", "xls", "xlsx"):
            righe = _leggi_foglio(contenuto, est)
            _, mappa = _trova_intestazione(righe)
            if mappa is None:
                return False
            # Un computo ha anche una colonna quantità: in quel caso non è un elenco prezzi
            intest = " ".join(_norm(c) for r in righe[:30] for c in r)
            return not re.search(r"\bquantit|\bq\.t[aà]", intest)
    except Exception:
        return False
    return False

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import anthropic
import os
import json

router = APIRouter()

_skill_cache: Optional[str] = None


def get_skill() -> str:
    global _skill_cache
    if _skill_cache is None:
        skill_path = os.path.join(os.path.dirname(__file__), "../skill/SKILL.md")
        with open(skill_path, "r", encoding="utf-8") as f:
            _skill_cache = f.read()
    return _skill_cache


# ═══════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════

class ObbligatorietaRequest(BaseModel):
    document_type: str          # notifica_preliminare | psc | pos
    uomini_giorno: Optional[int] = None
    max_lavoratori: Optional[int] = None
    rischi_allegato_xi: Optional[bool] = False
    num_imprese: Optional[int] = None
    tipo_soggetto: Optional[str] = None   # impresa_esecutrice | lavoratore_autonomo


class ContenutoRequest(BaseModel):
    tipo_documento: str
    form_data: dict


# ═══════════════════════════════════════════════
# VERIFICA OBBLIGATORIETÀ
# ═══════════════════════════════════════════════

@router.post("/check-obbligatorieta")
def check_obbligatorieta(req: ObbligatorietaRequest):
    """
    Determina se un documento è obbligatorio in base ai parametri del cantiere.
    Logica puramente normativa, nessuna chiamata AI.
    """
    result = {
        "obbligatorio": False,
        "motivazioni": [],
        "riferimenti_normativi": [],
        "avvertenze": [],
    }

    # ── NOTIFICA PRELIMINARE ──────────────────────────────────────
    if req.document_type == "notifica_preliminare":
        ug = req.uomini_giorno or 0
        ml = req.max_lavoratori or 0

        if ug > 200:
            result["obbligatorio"] = True
            result["motivazioni"].append(
                f"Durata cantiere di {ug} uomini-giorno supera la soglia di 200 UG"
            )
            result["riferimenti_normativi"].append("Art. 99 co. 1, D.Lgs. 81/2008")

        if ml > 20:
            result["obbligatorio"] = True
            result["motivazioni"].append(
                f"Numero massimo di {ml} lavoratori contemporanei supera la soglia di 20"
            )
            result["riferimenti_normativi"].append("Art. 99 co. 1, D.Lgs. 81/2008")

        if req.rischi_allegato_xi:
            result["obbligatorio"] = True
            result["motivazioni"].append(
                "Presenza di lavori comportanti rischi particolari (Allegato XI)"
            )
            result["riferimenti_normativi"].append(
                "Art. 99 co. 1 lett. c, D.Lgs. 81/2008 — Allegato XI"
            )

        if not result["obbligatorio"]:
            result["motivazioni"].append(
                f"Il cantiere ({ug} UG, max {ml} lavoratori, "
                f"no rischi All. XI) non supera le soglie dell'art. 99. "
                "La Notifica Preliminare non è obbligatoria."
            )
            result["avvertenze"].append(
                "Verificare sempre i parametri definitivi: "
                "eventuali variazioni in corso d'opera potrebbero rendere la Notifica obbligatoria."
            )

    # ── PSC ──────────────────────────────────────────────────────
    elif req.document_type == "psc":
        ni = req.num_imprese or 1
        ug = req.uomini_giorno or 0

        if ni > 1:
            result["obbligatorio"] = True
            result["motivazioni"].append(
                f"Sono previste {ni} imprese esecutrici nel cantiere (anche non contemporanee)"
            )
            result["riferimenti_normativi"].append("Art. 90 co. 3, D.Lgs. 81/2008")

        elif ug > 200:
            result["obbligatorio"] = True
            result["motivazioni"].append(
                f"Cantiere di {ug} UG con una sola impresa esecutrice ma presenza di subappaltatori"
            )
            result["riferimenti_normativi"].append("Art. 90 co. 3, D.Lgs. 81/2008")

        if not result["obbligatorio"]:
            result["motivazioni"].append(
                "Con una sola impresa esecutrice e nessun subappaltatore il PSC non è obbligatorio."
            )
            result["avvertenze"].append(
                "Il PSC rimane facoltativo e può essere redatto volontariamente. "
                "Alcune stazioni appaltanti lo richiedono contrattualmente."
            )

    # ── POS ──────────────────────────────────────────────────────
    elif req.document_type == "pos":
        ts = req.tipo_soggetto or "impresa_esecutrice"

        if ts == "impresa_esecutrice":
            result["obbligatorio"] = True
            result["motivazioni"].append(
                "Il POS è obbligatorio per ogni impresa esecutrice, "
                "indipendentemente dalle dimensioni del cantiere e dal numero di lavoratori."
            )
            result["riferimenti_normativi"].append("Art. 101 co. 1, D.Lgs. 81/2008")
        else:
            result["motivazioni"].append(
                "I lavoratori autonomi (senza dipendenti) non sono tenuti a redigere il POS."
            )
            result["avvertenze"].append(
                "Il lavoratore autonomo deve comunque rispettare le prescrizioni del PSC "
                "e adeguarsi alle direttive del CSE (art. 94, D.Lgs. 81/2008)."
            )

    else:
        raise HTTPException(400, f"Tipo documento non supportato: {req.document_type}")

    # deduplication
    result["riferimenti_normativi"] = list(dict.fromkeys(result["riferimenti_normativi"]))
    return result


# ═══════════════════════════════════════════════
# GENERAZIONE CONTENUTO AI
# ═══════════════════════════════════════════════

@router.post("/genera-contenuto")
def genera_contenuto_ai(req: ContenutoRequest):
    """
    Usa Claude per generare il contenuto testuale delle sezioni del documento.
    Restituisce un dict con i contenuti per ogni sezione.
    """
    client = anthropic.Anthropic()
    skill = get_skill()

    form_json = json.dumps(req.form_data, ensure_ascii=False, indent=2)

    prompts = {
        "psc": f"""Sei un Coordinatore per la Sicurezza esperto (CSP) italiano.
Devi generare il contenuto delle sezioni narrative di un PSC (Piano di Sicurezza e Coordinamento)
conforme all'Allegato XV del D.Lgs. 81/2008.

Dati del cantiere:
{form_json}

Genera ESCLUSIVAMENTE un oggetto JSON valido (senza backtick, senza markdown) con queste chiavi:
{{
  "rischi_area": "...",
  "rischi_lavorazioni": "...",
  "rischi_interferenze": "...",
  "viabilita": "...",
  "zone_carico": "...",
  "zone_stoccaggio": "...",
  "recinzione": "...",
  "impianti": "...",
  "servizi_igienici": "...",
  "primo_soccorso": "...",
  "coordinamento": "...",
  "emergenze_procedure": "..."
}}
Ogni valore deve essere un testo professionale in italiano, specifico per il cantiere descritto,
con riferimenti normativi pertinenti. Minimo 3-5 frasi per sezione.
""",
        "pos": f"""Sei un esperto di sicurezza sul lavoro italiano.
Devi generare il contenuto delle sezioni narrative di un POS (Piano Operativo di Sicurezza)
conforme all'Allegato XV punto 3 del D.Lgs. 81/2008.

Dati dell'impresa e cantiere:
{form_json}

Genera ESCLUSIVAMENTE un oggetto JSON valido con queste chiavi:
{{
  "rischi_specifici": "...",
  "misure_prevenzione": "...",
  "procedure_operative": "...",
  "gestione_emergenze": "..."
}}
Testi professionali in italiano, specifici per l'attività dell'impresa, con riferimenti normativi.
""",
        "notifica_preliminare": f"""Sei un tecnico della sicurezza italiano.
Verifica i dati della Notifica Preliminare e genera note integrative.

Dati:
{form_json}

Genera ESCLUSIVAMENTE un oggetto JSON valido con queste chiavi:
{{
  "note_cantiere": "...",
  "note_trasmissione": "..."
}}
""",
    }

    prompt = prompts.get(req.tipo_documento)
    if not prompt:
        raise HTTPException(400, f"Tipo documento non supportato: {req.tipo_documento}")

    system = (
        "Sei un esperto di sicurezza nei cantieri edili italiani con 20 anni di esperienza. "
        "Conosci perfettamente il D.Lgs. 81/2008 e tutta la normativa correlata. "
        "Rispondi SEMPRE e SOLO con JSON valido, senza testo aggiuntivo.\n\n"
        f"NORMATIVA DI RIFERIMENTO:\n{skill[:4000]}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Pulizia del JSON
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()

    try:
        contenuto = json.loads(raw)
    except json.JSONDecodeError:
        # fallback: restituisce il testo grezzo
        contenuto = {"raw_text": raw}

    return {"contenuto": contenuto}

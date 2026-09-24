"""
services/checklist.py — Checklist A–M della metodologia (verifica obbligatoria prima dell'export)

Compilata dal CSP: ogni voce "Sì", "No" o "Non pertinente" (con motivazione).
L'export del PSC è bloccato finché tutte le voci non sono "Sì" oppure "Non pertinente" motivate.
La checklist resta nell'app: non entra nel documento finale.
"""
from database import get_conn

SEZIONI = [
    ("A", "Obbligo PSC", ["Ho verificato se sono previste più imprese?", "Ho verificato l'art. 90?",
                          "Sono stati individuati CSP e CSE?", "Ho verificato eventuali particolarità dell'intervento?"]),
    ("B", "Opera", ["Conosco il progetto?", "Conosco le lavorazioni?", "Conosco materiali e tecnologie?",
                    "Ho considerato le fasi costruttive?"]),
    ("C", "Area — documentazione del sopralluogo", ["Accessi?", "Viabilità?", "Sottoservizi?", "Edifici confinanti?",
                                                    "Linee elettriche?", "Rischi ambientali?", "Altri cantieri?"]),
    ("D", "Organizzazione", ["Recinzione?", "Accessi?", "Viabilità?", "Depositi?", "Baraccamenti?", "Servizi?",
                             "Impianti?", "Emergenze?", "Segnaletica?"]),
    ("E", "Lavorazioni", ["Ho individuato tutte le fasi?", "Ho individuato le sottofasi necessarie?",
                          "Ho associato le imprese?", "Ho individuato attrezzature e apprestamenti?"]),
    ("F", "Rischi", ["Rischi dell'area?", "Rischi delle lavorazioni?", "Rischi particolari?", "Rischi interferenziali?"]),
    ("G", "Coordinamento", ["Interferenze?", "Misure per eliminarle/ridurle?", "Uso comune?", "Cooperazione?",
                            "Informazione?", "Riunioni?"]),
    ("H", "Cronoprogramma", ["Durata delle fasi?", "Contemporaneità?", "Sequenza?", "Sottofasi?", "Uomini-giorno?"]),
    ("I", "Emergenze", ["Primo soccorso?", "Antincendio?", "Evacuazione?", "Numeri utili?", "Accesso dei soccorsi?"]),
    ("L", "Costi", ["Ho individuato i costi della sicurezza?", "Sono stimati analiticamente?", "Sono coerenti con il PSC?"]),
    ("M", "Controllo finale", ["PSC ↔ progetto?", "PSC ↔ layout?", "PSC ↔ cronoprogramma?", "PSC ↔ costi?",
                               "PSC ↔ POS futuri?", "PSC concretamente realizzabile?"]),
]
VOCI = {f"{l}.{i}": (l, testo) for l, _, voci in SEZIONI for i, testo in enumerate(voci, start=1)}
ESITI = ("si", "no", "np")


def stato(progetto_id: int) -> dict:
    conn = get_conn()
    try:
        rows = {r["voce"]: dict(r) for r in conn.execute(
            "SELECT voce, esito, motivazione FROM progetto_checklist WHERE progetto_id = ?", (progetto_id,)).fetchall()}
    finally:
        conn.close()
    sezioni, mancanti = [], []
    for lettera, titolo, voci in SEZIONI:
        el = []
        for i, testo in enumerate(voci, start=1):
            vid = f"{lettera}.{i}"
            r = rows.get(vid, {})
            esito, motiv = r.get("esito"), (r.get("motivazione") or "").strip()
            ok = esito == "si" or (esito == "np" and bool(motiv))
            if not ok:
                mancanti.append({"voce": vid, "testo": testo, "sezione": titolo,
                                 "motivo": "manca la motivazione" if esito == "np" else
                                           "risposta 'No'" if esito == "no" else "non compilata"})
            el.append({"voce": vid, "testo": testo, "esito": esito, "motivazione": motiv, "ok": ok})
        sezioni.append({"lettera": lettera, "titolo": titolo, "voci": el})
    totale = len(VOCI)
    return {"sezioni": sezioni, "completa": not mancanti, "mancanti": mancanti,
            "compilate": totale - len(mancanti), "totale": totale}


def salva(progetto_id: int, voce: str, esito, motivazione: str = None):
    if voce not in VOCI:
        raise ValueError("Voce inesistente")
    if esito not in ESITI + (None,):
        raise ValueError("Esito non valido")
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO progetto_checklist (progetto_id, voce, esito, motivazione) VALUES (?,?,?,?)
               ON CONFLICT(progetto_id, voce) DO UPDATE SET esito=excluded.esito,
               motivazione=excluded.motivazione, updated_at=CURRENT_TIMESTAMP""",
            (progetto_id, voce, esito, (motivazione or "").strip() or None))
        conn.commit()
    finally:
        conn.close()

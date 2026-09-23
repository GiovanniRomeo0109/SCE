"""
services/uomini_giorno.py — Uomini-giorno con due metodi (blocco 4)

Metodo A — cronoprogramma: Σ (durata in settimane × 5 giorni lavorativi × addetti medi)
Metodo B — incidenza della manodopera: importo manodopera ÷ costo giornaliero di un lavoratore
    importo manodopera: a) dal computo, se riporta manodopera o sua incidenza %
                        b) altrimenti importo lavori × percentuale indicata dal CSP
Costo giornaliero proposto: media delle 4 qualifiche edili base (4° livello, specializzato,
qualificato, comune) del capitolo manodopera negli elenchi (progetto → account → sistema) × 8 ore.
Valore per il PSC: scelto dal CSP, predefinito il maggiore.
"""
import json
import re
from datetime import date, timedelta

from database import get_conn
from services.costi_sicurezza import numero, elenchi_disponibili

GIORNI_PER_SETTIMANA = 5
ORE_PER_GIORNO = 8
QUALIFICHE = [
    ("OPERAIO 4° LIVELLO EDILE", r"^operaio\s+4\s*°?\s*livello\s+edile$"),
    ("OPERAIO SPECIALIZZATO EDILE", r"^operaio\s+specializzato\s+edile$"),
    ("OPERAIO QUALIFICATO EDILE", r"^operaio\s+qualificato\s+edile$"),
    ("OPERAIO COMUNE EDILE", r"^operaio\s+comune\s+edile$"),
]


def _progetto(progetto_id):
    conn = get_conn()
    try:
        return dict(conn.execute("SELECT * FROM progetti WHERE id=?", (progetto_id,)).fetchone())
    finally:
        conn.close()


def righe_cronoprogramma(progetto_id: int) -> list:
    conn = get_conn()
    try:
        r = conn.execute("SELECT contenuto_json FROM progetto_tappe WHERE progetto_id=? AND numero=5",
                         (progetto_id,)).fetchone()
    finally:
        conn.close()
    if not r or not r["contenuto_json"]:
        return []
    sez = next((s for s in json.loads(r["contenuto_json"])["sezioni"] if s["id"] == "cronoprogramma"), None)
    if not sez:
        return []
    col = {c: i for i, c in enumerate(sez["colonne"])}
    out = []
    for riga in sez["righe"]:
        g = lambda n: riga[col[n]] if n in col and col[n] < len(riga) else ""
        inizio, durata, fine = numero(g("Settimana inizio")), numero(g("Durata (settimane)")), numero(g("Settimana fine"))
        if durata is None and inizio is not None and fine is not None:
            durata = fine - inizio + 1
        if fine is None and inizio is not None and durata is not None:
            fine = inizio + durata - 1
        out.append({"cod": g("Cod."), "fase": g("Fase / lavorazione"), "impresa": g("Impresa"),
                    "inizio": inizio, "durata": durata, "fine": fine,
                    "contemporanea": g("Contemporanea a"), "addetti": numero(g("Addetti medi"))})
    return out


def _dati_fascicolo(progetto_id: int) -> dict:
    """Importo lavori e manodopera eventualmente estratti dai documenti (computo in primis)."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT e.dati_json, COALESCE(d.tipo_csp, d.tipo_ai) AS tipo FROM progetto_estrazioni e
               JOIN progetto_documenti d ON d.id = e.documento_id WHERE d.progetto_id = ?
               ORDER BY (COALESCE(d.tipo_csp, d.tipo_ai) = 'computo') DESC, d.priorita""",
            (progetto_id,)).fetchall()
    finally:
        conn.close()
    out = {"importo_lavori": None, "importo_manodopera": None, "incidenza": None, "fonte": None}
    for r in rows:
        dg = (json.loads(r["dati_json"] or "{}").get("dati_generali") or {})
        if out["importo_manodopera"] is None and numero(dg.get("importo_manodopera")):
            out["importo_manodopera"], out["fonte"] = numero(dg["importo_manodopera"]), r["tipo"]
        if out["incidenza"] is None and numero(dg.get("incidenza_manodopera_percentuale")):
            out["incidenza"] = numero(dg["incidenza_manodopera_percentuale"])
            out["fonte"] = out["fonte"] or r["tipo"]
        if out["importo_lavori"] is None and numero(dg.get("importo_lavori")):
            out["importo_lavori"] = numero(dg["importo_lavori"])
    return out


def costo_giornaliero_proposto(progetto_id: int, username: str) -> dict:
    elenchi = elenchi_disponibili(progetto_id, username)
    conn = get_conn()
    try:
        for livello in ("progetto", "account", "sistema"):
            for e in [x for x in elenchi if x["livello"] == livello]:
                voci = conn.execute(
                    "SELECT codice, descrizione, um, prezzo FROM elenchi_prezzi_voci WHERE elenco_id=? AND LOWER(um) IN ('h','ora','ore')",
                    (e["id"],)).fetchall()
                trovate = []
                for nome, regex in QUALIFICHE:
                    v = next((v for v in voci if re.match(regex, (v["descrizione"] or "").strip().lower())), None)
                    if v:
                        trovate.append({"qualifica": nome, "codice": v["codice"], "prezzo_orario": v["prezzo"]})
                if len(trovate) == len(QUALIFICHE):
                    media = sum(t["prezzo_orario"] for t in trovate) / len(trovate)
                    return {"valore": round(media * ORE_PER_GIORNO, 2), "media_oraria": round(media, 2),
                            "qualifiche": trovate, "elenco": e["nome"], "livello": livello}
    finally:
        conn.close()
    return None


def calcola(progetto_id: int, username: str) -> dict:
    p = _progetto(progetto_id)
    crono = righe_cronoprogramma(progetto_id)

    # Metodo A
    righe_ok = [r for r in crono if r["durata"] and r["addetti"]]
    ug_a = sum(r["durata"] * GIORNI_PER_SETTIMANA * r["addetti"] for r in righe_ok) if righe_ok else None
    senza_addetti = [r["fase"] for r in crono if r["durata"] and not r["addetti"]]

    # Metodo B
    fasc = _dati_fascicolo(progetto_id)
    proposta = costo_giornaliero_proposto(progetto_id, username)
    costo_g = p.get("costo_giornaliero") or (proposta or {}).get("valore")
    importo_lavori = p.get("importo_lavori") if p.get("importo_lavori") is not None else fasc["importo_lavori"]
    incidenza_csp = p.get("incidenza_manodopera")
    if fasc["importo_manodopera"]:
        importo_man, origine = fasc["importo_manodopera"], "computo (importo manodopera)"
    elif fasc["incidenza"] and importo_lavori:
        importo_man, origine = importo_lavori * fasc["incidenza"] / 100, f"computo (incidenza {fasc['incidenza']}%)"
    elif incidenza_csp is not None and importo_lavori:
        importo_man, origine = importo_lavori * incidenza_csp / 100, f"incidenza indicata dal CSP ({incidenza_csp}%)"
    else:
        importo_man, origine = None, None
    ug_b = round(importo_man / costo_g, 1) if importo_man and costo_g else None

    candidati = [v for v in (ug_a, ug_b) if v]
    maggiore = "cronoprogramma" if ug_a and (not ug_b or ug_a >= ug_b) else ("incidenza" if ug_b else None)
    scelta = p.get("ug_scelta") if p.get("ug_scelta") in ("cronoprogramma", "incidenza") else maggiore
    valore = ug_a if scelta == "cronoprogramma" else ug_b if scelta == "incidenza" else None
    if valore is None and candidati:
        valore, scelta = max(candidati), maggiore

    return {
        "giorni_per_settimana": GIORNI_PER_SETTIMANA,
        "cronoprogramma": {"uomini_giorno": round(ug_a, 1) if ug_a else None, "righe": crono,
                           "senza_addetti": senza_addetti},
        "incidenza": {"uomini_giorno": ug_b, "importo_lavori": importo_lavori,
                      "importo_lavori_da_documenti": fasc["importo_lavori"],
                      "incidenza_csp": incidenza_csp, "incidenza_documenti": fasc["incidenza"],
                      "importo_manodopera": round(importo_man, 2) if importo_man else None,
                      "origine_manodopera": origine, "costo_giornaliero": costo_g,
                      "costo_giornaliero_csp": p.get("costo_giornaliero"), "proposta": proposta},
        "scelta": scelta, "maggiore": maggiore, "valore": round(valore, 1) if valore else None,
        "data_inizio_lavori": p.get("data_inizio_lavori"),
    }


def data_settimana(data_inizio: str, settimana: int):
    """Lunedì della settimana n (la settimana 1 contiene la data di inizio)."""
    try:
        d0 = date.fromisoformat(data_inizio)
    except (TypeError, ValueError):
        return None
    lunedi = d0 - timedelta(days=d0.weekday())
    return lunedi + timedelta(weeks=int(settimana) - 1)

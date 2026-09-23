"""
services/presidi.py — Presidi di emergenza del cantiere (blocco 5)

- ricerca web (strumento web_search dell'API Anthropic) a partire dall'indirizzo del cantiere
- ogni presidio trovato è "da verificare", con il link della fonte, finché il CSP non lo conferma
- la tabella "Presidi e numeri di emergenza" della tappa 9 viene aggiornata dai presidi salvati:
  è un dato di fatto, non una modifica del CSP, quindi NON avvia la cascata
Distanze e percorsi sono indicativi: nessun servizio di mappe.
"""
import json
import logging
import re

from database import get_conn
from services.ai_costi import TrackedClient
from services.documenti_progetto import pulisci_json

log = logging.getLogger("presidi")

MODELLO = "claude-haiku-4-5-20251001"
MAX_RICERCHE = 6
STIMA_EUR = 0.15          # ricerche (~0,01 $ l'una) + risultati letti dal modello

TIPI = {
    "numero_emergenza": "Numero di emergenza",
    "pronto_soccorso":  "Pronto soccorso",
    "vigili_fuoco":     "Vigili del fuoco",
    "carabinieri":      "Carabinieri",
    "polizia_locale":   "Polizia locale",
    "guardia_medica":   "Guardia medica",
    "farmacia":         "Farmacia",
    "altro":            "Altro",
}
ORDINE = {k: i for i, k in enumerate(TIPI)}

SYSTEM = """Sei un tecnico della sicurezza che prepara la sezione emergenze di un PSC per un cantiere in Italia.
Cerca sul web, per l'indirizzo del cantiere indicato:
- il PRONTO SOCCORSO più vicino (con il nome dell'ospedale), con indirizzo e telefono;
- il comando o distaccamento dei VIGILI DEL FUOCO competente per la zona;
- la stazione dei CARABINIERI e la POLIZIA LOCALE competenti;
- la GUARDIA MEDICA (continuità assistenziale) di riferimento;
- la FARMACIA più vicina;
- i NUMERI DI EMERGENZA validi in quella zona (es. 112 Numero Unico Europeo se attivo nella regione,
  altrimenti 118, 115, 112, 113), indicando quale servizio risponde.
Per distanza e percorso dai solo un'indicazione di massima (es. "circa 4 km, 8 minuti in auto"):
non hai un servizio di mappe, non inventare precisione.
Non inventare nomi, indirizzi o numeri: se un dato non lo trovi, lascialo vuoto.
Per ogni presidio indica la pagina web da cui hai preso il dato.
Quando hai finito, rispondi SOLO con JSON:
{"presidi": [{"tipo": "pronto_soccorso|vigili_fuoco|carabinieri|polizia_locale|guardia_medica|farmacia|numero_emergenza",
  "nome": "", "indirizzo": "", "telefono": "", "distanza": "", "percorso": "",
  "fonte_url": "", "fonte_titolo": ""}], "note": ""}"""


def indirizzo_da_fascicolo(progetto_id: int) -> str:
    """Primo indirizzo del cantiere trovato nei dati estratti dai documenti."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT e.dati_json FROM progetto_estrazioni e JOIN progetto_documenti d ON d.id = e.documento_id
               WHERE d.progetto_id = ? ORDER BY d.priorita, d.id, e.blocco""", (progetto_id,)).fetchall()
    finally:
        conn.close()
    for r in rows:
        dg = (json.loads(r["dati_json"] or "{}").get("dati_generali") or {})
        via = (dg.get("indirizzo_cantiere") or "").strip()
        if via and "verificare" not in via.lower():
            comune, prov = (dg.get("comune") or "").strip(), (dg.get("provincia") or "").strip()
            parti = [via] + ([comune] if comune and comune.lower() not in via.lower() else [])
            testo = ", ".join(parti)
            return f"{testo} ({prov})" if prov and prov.lower() not in testo.lower() else testo
    return ""


def elenco(progetto_id: int) -> list:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM progetto_presidi WHERE progetto_id = ? ORDER BY ordine, id",
                            (progetto_id,)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["tipo_etichetta"] = TIPI.get(d["tipo"], "Altro")
        out.append(d)
    return out


def _fonti_dei_risultati(risposta) -> dict:
    """URL e titoli delle pagine effettivamente restituite dalla ricerca web."""
    fonti = {}
    for b in risposta.content:
        if getattr(b, "type", "") == "web_search_tool_result":
            for x in (getattr(b, "content", None) or []):
                url = getattr(x, "url", None) if not isinstance(x, dict) else x.get("url")
                tit = getattr(x, "title", None) if not isinstance(x, dict) else x.get("title")
                if url:
                    fonti[url] = tit or url
    return fonti


def cerca(progetto_id: int, user: dict, indirizzo: str) -> dict:
    """Esegue la ricerca e sostituisce i presidi NON confermati e non inseriti a mano."""
    client = TrackedClient(user, "ricerca_presidi")
    risposta = client.messages.create(
        model=MODELLO, max_tokens=3000, system=SYSTEM,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": MAX_RICERCHE,
                "user_location": {"type": "approximate", "country": "IT"}}],
        messages=[{"role": "user", "content": f"Indirizzo del cantiere: {indirizzo}"}],
    )
    testo = "".join(getattr(b, "text", "") for b in risposta.content if getattr(b, "type", "") == "text")
    dati = pulisci_json(testo[testo.find("{"):] if "{" in testo else testo) or {}
    fonti = _fonti_dei_risultati(risposta)

    nuovi = []
    for p in dati.get("presidi", []) or []:
        if not isinstance(p, dict) or not (p.get("nome") or p.get("telefono")):
            continue
        tipo = p.get("tipo") if p.get("tipo") in TIPI else "altro"
        url = (p.get("fonte_url") or "").strip()
        if url and url not in fonti and fonti:
            # la fonte indicata non è tra i risultati della ricerca: la sostituisco con la più vicina
            url = next((u for u in fonti if url.split("/")[2:3] == u.split("/")[2:3]), url)
        nuovi.append({k: (str(p.get(k) or "").strip()) for k in
                      ("nome", "indirizzo", "telefono", "distanza", "percorso", "fonte_titolo")} |
                     {"tipo": tipo, "fonte_url": url, "fonte_titolo": (p.get("fonte_titolo") or fonti.get(url, "")).strip()})

    conn = get_conn()
    try:
        conn.execute("DELETE FROM progetto_presidi WHERE progetto_id = ? AND confermato = 0 AND manuale = 0",
                     (progetto_id,))
        tenuti = {(r["tipo"], (r["nome"] or "").lower()) for r in conn.execute(
            "SELECT tipo, nome FROM progetto_presidi WHERE progetto_id = ?", (progetto_id,)).fetchall()}
        for p in nuovi:
            if (p["tipo"], p["nome"].lower()) in tenuti:
                continue
            conn.execute(
                """INSERT INTO progetto_presidi (progetto_id, ordine, tipo, nome, indirizzo, telefono, distanza,
                          percorso, fonte_url, fonte_titolo) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (progetto_id, ORDINE[p["tipo"]], p["tipo"], p["nome"], p["indirizzo"], p["telefono"],
                 p["distanza"], p["percorso"], p["fonte_url"], p["fonte_titolo"]))
        conn.commit()
    finally:
        conn.close()
    aggiorna_tappa_9(progetto_id)
    return {"trovati": len(nuovi), "ricerche": _n_ricerche(risposta), "note": dati.get("note", "")}


def _n_ricerche(risposta) -> int:
    server = getattr(risposta.usage, "server_tool_use", None)
    return (getattr(server, "web_search_requests", 0) or 0) if server else 0


def righe_tabella(progetto_id: int) -> list:
    """Righe per la tabella 'Presidi e numeri di emergenza' della tappa 9."""
    righe = []
    for p in elenco(progetto_id):
        rif = " — ".join(x for x in (p["indirizzo"], f"tel. {p['telefono']}" if p["telefono"] else "") if x)
        dist = " · ".join(x for x in (p["distanza"], p["percorso"]) if x)
        if not p["confermato"]:
            dist = (dist + " — " if dist else "") + "DA VERIFICARE"
        righe.append([f"{p['tipo_etichetta']}: {p['nome']}" if p["nome"] else p["tipo_etichetta"], rif, dist])
    return righe


def aggiorna_tappa_9(progetto_id: int):
    """Scrive i presidi nella tappa 9 (senza modificarne lo stato né avviare la cascata)."""
    righe = righe_tabella(progetto_id)
    conn = get_conn()
    try:
        t = conn.execute("SELECT contenuto_json FROM progetto_tappe WHERE progetto_id = ? AND numero = 9",
                         (progetto_id,)).fetchone()
        if not t or not t["contenuto_json"] or not righe:
            return
        cont = json.loads(t["contenuto_json"])
        for s in cont.get("sezioni", []):
            if s.get("id") == "presidi":
                s["righe"] = righe
        conn.execute("UPDATE progetto_tappe SET contenuto_json = ? WHERE progetto_id = ? AND numero = 9",
                     (json.dumps(cont, ensure_ascii=False), progetto_id))
        conn.commit()
    finally:
        conn.close()


def testo_per_prompt(progetto_id: int) -> str:
    """Presidi già noti, da usare nella (ri)generazione della tappa 9 invece di inventarli."""
    el = elenco(progetto_id)
    if not el:
        return ""
    return "PRESIDI DI EMERGENZA GIÀ INDIVIDUATI DAL CSP (usali, non inventarne altri):\n" + "\n".join(
        f"- {p['tipo_etichetta']}: {p['nome']} {p['indirizzo']} tel. {p['telefono']} {p['distanza']}"
        f"{'' if p['confermato'] else ' (da verificare)'}" for p in el)

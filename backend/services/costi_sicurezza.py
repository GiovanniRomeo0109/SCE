"""
services/costi_sicurezza.py — Stima analitica dei costi della sicurezza (blocco 4)

Flusso
1. SINCRONIZZAZIONE con la tappa 11 (tabella "Misure che rientrano nei costi della sicurezza"):
   - misura già presente → resta la voce/prezzo scelti; se la tappa cambia la quantità,
     l'importo si ricalcola (prezzo × nuova quantità)
   - misura nuova → "da abbinare" (abbinamento automatico)
   - misura non più presente → disattivata (non conta nei totali)
2. PRE-FILTRAGGIO LOCALE: per ogni misura si cercano nel DB le voci più pertinenti (parole
   chiave + unità di misura) nei tre livelli di elenchi: progetto → account → sistema.
   All'AI arrivano solo ~15 candidati per misura, mai l'elenco intero.
3. ABBINAMENTO AI (Haiku): sceglie la voce adatta dal livello più alto disponibile; se nessuna
   è adatta → "prezzo da definire" (il CSP può cercare una voce o inserire il prezzo a mano).
"""
import json
import logging
import re

from database import get_conn, get_user_by_username
from services.ai_costi import TrackedClient, verifica_disponibilita, stima_costo_eur
from services.documenti_progetto import pulisci_json

log = logging.getLogger("costi_sicurezza")

MODELLO = "claude-haiku-4-5-20251001"
CANDIDATI_PER_LIVELLO = 10
MISURE_PER_CHIAMATA = 10
LIVELLI = ("progetto", "account", "sistema")

CATEGORIE = {
    "a": "Apprestamenti previsti nel PSC",
    "b": "Misure preventive e protettive e DPI per lavorazioni interferenti",
    "c": "Impianti di terra, protezione scariche atmosferiche, antincendio, evacuazione fumi",
    "d": "Mezzi e servizi di protezione collettiva",
    "e": "Procedure contenute nel PSC per specifici motivi di sicurezza",
    "f": "Interventi per lo sfasamento spaziale o temporale delle lavorazioni interferenti",
    "g": "Misure di coordinamento per l'uso comune",
}

_STOP = set("""a al alla alle agli ai allo con da dal dalla dei del della delle degli di e ed
in il la le lo gli i per su sul sulla tra fra un una uno o od che non come nel nella nei
cantiere lavori lavoro opera opere fornitura posa compreso compresa compresi inclusi mese mesi
tipo altezza secondo norma normativa ogni eventuale eventuali previsto prevista""".split())

_UM_EQUIV = {
    "mq": "m2", "m²": "m2", "m2": "m2", "mc": "m3", "m³": "m3", "m3": "m3", "ml": "m", "m": "m",
    "cad": "cad", "n": "cad", "n.": "cad", "nr": "cad", "pz": "cad", "cadauno": "cad",
    "h": "h", "ora": "h", "ore": "h", "corpo": "corpo", "a corpo": "corpo", "kg": "kg",
    "giorno": "g", "gg": "g", "g": "g", "mese": "mese",
}


def categoria_lettera(testo: str) -> str:
    m = re.match(r"\s*\(?([a-gA-G])[\)\.\s:-]", (testo or "") + " ")
    return m.group(1).lower() if m else "altro"


def _chiave(misura: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (misura or "").lower()).strip()[:200]


def numero(v):
    """'120', '120,5', '1.200,50 m²' → float; None se non c'è un numero."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"\d[\d.]*(?:,\d+)?|\d+(?:\.\d+)?", str(v))
    if not m:
        return None
    s = m.group(0)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _um_base(um: str) -> str:
    """Unità di misura confrontabile: 'm²/mese' → 'm2/mese', 'cad/me' → 'cad/mese', 'mq' → 'm2'."""
    parti = (um or "").lower().replace(" ", "").split("/")
    base = _UM_EQUIV.get(parti[0], parti[0])
    a_tempo = len(parti) > 1 and parti[1].startswith("me")
    return base + ("/mese" if a_tempo else "")


def _parole(testo: str) -> list:
    parole = re.findall(r"[a-zàèéìòù0-9]{3,}", (testo or "").lower())
    return [p for p in parole if p not in _STOP]


def _radice(p: str) -> str:
    return p[:6] if len(p) > 6 else p


# ══════════════════════════════════════════════════════════════════════════════
# 1. Sincronizzazione con la tappa 11
# ══════════════════════════════════════════════════════════════════════════════

def _righe_tappa_11(progetto_id: int) -> list:
    conn = get_conn()
    try:
        row = conn.execute("SELECT contenuto_json FROM progetto_tappe WHERE progetto_id = ? AND numero = 11",
                           (progetto_id,)).fetchone()
    finally:
        conn.close()
    if not row or not row["contenuto_json"]:
        return []
    cont = json.loads(row["contenuto_json"])
    sez = next((s for s in cont.get("sezioni", []) if s.get("id") == "costi_psc"), None)
    if not sez:
        return []
    col = {c: i for i, c in enumerate(sez["colonne"])}
    out = []
    for r in sez["righe"]:
        get = lambda nome: r[col[nome]] if nome in col and col[nome] < len(r) else ""
        misura = get("Misura").strip()
        if misura:
            out.append({"categoria": get("Categoria 4.1.1 (a-g)").strip(), "misura": misura,
                        "um": get("U.M.").strip(), "quantita": numero(get("Quantità"))})
    return out


def sincronizza(progetto_id: int) -> int:
    """Allinea la stima alla tappa 11. Restituisce il numero di misure da abbinare."""
    righe = _righe_tappa_11(progetto_id)
    conn = get_conn()
    try:
        esistenti = {r["chiave"]: dict(r) for r in conn.execute(
            "SELECT * FROM progetto_costi WHERE progetto_id = ?", (progetto_id,)).fetchall()}
        viste = set()
        for i, r in enumerate(righe):
            k = _chiave(r["misura"])
            if not k or k in viste:
                continue
            viste.add(k)
            e = esistenti.get(k)
            if e:
                quantita = e["quantita"]
                # Se la tappa propone una quantità diversa da prima, vale la nuova
                if r["quantita"] != e["quantita_tappa"] or not e["quantita_csp"]:
                    quantita = r["quantita"]
                    quantita_csp = 0
                else:
                    quantita_csp = e["quantita_csp"]
                conn.execute(
                    """UPDATE progetto_costi SET attiva=1, ordine=?, categoria=?, misura=?, um_misura=?,
                              quantita_tappa=?, quantita=?, quantita_csp=?, updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (i, r["categoria"], r["misura"], r["um"], r["quantita"], quantita, quantita_csp, e["id"]))
            else:
                conn.execute(
                    """INSERT INTO progetto_costi (progetto_id, chiave, ordine, categoria, misura, um_misura,
                              quantita_tappa, quantita, stato) VALUES (?,?,?,?,?,?,?,?, 'da_abbinare')""",
                    (progetto_id, k, i, r["categoria"], r["misura"], r["um"], r["quantita"], r["quantita"]))
        for k, e in esistenti.items():
            if k not in viste and e["attiva"]:
                conn.execute("UPDATE progetto_costi SET attiva=0 WHERE id=?", (e["id"],))
        da_abbinare = conn.execute(
            "SELECT COUNT(*) AS n FROM progetto_costi WHERE progetto_id=? AND attiva=1 AND stato='da_abbinare'",
            (progetto_id,)).fetchone()["n"]
        conn.execute("UPDATE progetti SET costi_da_abbinare=?, costi_messaggio=NULL WHERE id=?",
                     (1 if da_abbinare else 0, progetto_id))
        conn.commit()
    finally:
        conn.close()
    return da_abbinare


# ══════════════════════════════════════════════════════════════════════════════
# 2. Elenchi disponibili e pre-filtraggio
# ══════════════════════════════════════════════════════════════════════════════

def elenchi_disponibili(progetto_id: int, username: str) -> list:
    """Elenchi pronti in ordine di priorità: progetto → account → sistema."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id, nome, livello FROM elenchi_prezzi WHERE stato = 'pronto' AND (
                   (livello = 'progetto' AND progetto_id = ?) OR
                   (livello = 'account' AND username = ?) OR livello = 'sistema')""",
            (progetto_id, username)).fetchall()
    finally:
        conn.close()
    ordine = {l: i for i, l in enumerate(LIVELLI)}
    return sorted([dict(r) for r in rows], key=lambda r: (ordine.get(r["livello"], 9), r["id"]))


def cerca_voci(elenchi: list, testo: str, um: str = "", per_livello: int = CANDIDATI_PER_LIVELLO) -> list:
    """Voci più pertinenti per un testo, per ciascun livello. Nessuna AI."""
    parole = _parole(testo)
    if not parole or not elenchi:
        return []
    radici = sorted({_radice(p) for p in parole}, key=len, reverse=True)[:6]
    um_b = _um_base(um)
    risultati = []
    conn = get_conn()
    try:
        for livello in LIVELLI:
            ids = [e["id"] for e in elenchi if e["livello"] == livello]
            if not ids:
                continue
            nomi = {e["id"]: e["nome"] for e in elenchi if e["livello"] == livello}
            cond = " OR ".join(["LOWER(descrizione) LIKE ?"] * len(radici))
            rows = conn.execute(
                f"""SELECT id, elenco_id, codice, descrizione, um, prezzo, capitolo FROM elenchi_prezzi_voci
                    WHERE elenco_id IN ({','.join('?' * len(ids))}) AND ({cond}) LIMIT 800""",
                (*ids, *[f"%{r}%" for r in radici])).fetchall()
            punteggi = []
            for r in rows:
                d = (r["descrizione"] or "").lower()
                p = sum(2 if len(x) >= 6 else 1 for x in radici if x in d)
                if um_b and _um_base(r["um"]) == um_b:
                    p += 1.5
                if re.search(r"cessione definitiva", d):
                    p -= 0.5            # di norma nel PSC si usa il nolo, non la cessione
                punteggi.append((p, r))
            punteggi.sort(key=lambda x: (-x[0], x[1]["id"]))
            for p, r in punteggi[:per_livello]:
                if p <= 0:
                    continue
                risultati.append({"voce_id": r["id"], "elenco_id": r["elenco_id"], "elenco_nome": nomi[r["elenco_id"]],
                                  "livello": livello, "codice": r["codice"], "descrizione": r["descrizione"],
                                  "um": r["um"], "prezzo": r["prezzo"], "punteggio": p})
    finally:
        conn.close()
    return risultati


# ══════════════════════════════════════════════════════════════════════════════
# 3. Abbinamento con l'AI
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_ABBINA = """Sei un tecnico che stima i costi della sicurezza di un PSC (D.Lgs. 81/2008, Allegato XV 4.1).
Per ogni misura scegli la voce di elenco prezzi più adatta tra i candidati forniti.
REGOLE
- Scegli dal livello più alto che contiene una voce adatta: prima PROGETTO, poi ACCOUNT, poi SISTEMA.
- Per apprestamenti a noleggio (recinzioni, baracche, ponteggi, parapetti) preferisci le voci di
  montaggio/nolo rispetto alla "cessione definitiva", salvo diversa indicazione della misura.
- Se nessun candidato descrive davvero la misura, rispondi null: è meglio "prezzo da definire" che una voce sbagliata.
- Se l'unità di misura della voce è diversa da quella della misura (es. m² contro m, oppure voce a
  mese), segnalalo in "nota" in una frase, indicando come adattare la quantità.
Rispondi SOLO con JSON: {"abbinamenti": [{"misura": <id>, "voce": "<id candidato>" | null, "nota": "..."}]}"""


def _richiesta(misure: list) -> str:
    parti = []
    for m in misure:
        parti.append(f"### MISURA id={m['id']}: {m['misura']} — U.M. {m['um_misura'] or 'non indicata'}"
                     f" — quantità {m['quantita'] if m['quantita'] is not None else 'n.d.'}")
        if not m["candidati"]:
            parti.append("  (nessun candidato trovato)")
        for c in m["candidati"]:
            parti.append(f"  [{c['cid']}] {c['livello'].upper()} · {c['codice']} · {c['um']} · € {c['prezzo']:.2f} · "
                         f"{c['descrizione'][:260]}")
    return "\n".join(parti)


def abbina(progetto_id: int) -> dict:
    """Abbina le misure 'da_abbinare'. Chiamata dal worker in background."""
    conn = get_conn()
    try:
        p = conn.execute("SELECT id, username FROM progetti WHERE id = ?", (progetto_id,)).fetchone()
        misure = [dict(r) for r in conn.execute(
            "SELECT * FROM progetto_costi WHERE progetto_id=? AND attiva=1 AND stato='da_abbinare' ORDER BY ordine",
            (progetto_id,)).fetchall()]
    finally:
        conn.close()
    if not p or not misure:
        _messaggio(progetto_id, 0, None)
        return {"abbinate": 0}
    user = get_user_by_username(p["username"])
    elenchi = elenchi_disponibili(progetto_id, p["username"])

    if not elenchi:
        _segna_da_definire([m["id"] for m in misure],
                           "Nessun elenco prezzi disponibile: carica un elenco nel progetto o nella pagina Elenchi prezzi")
        _messaggio(progetto_id, 0, "Nessun elenco prezzi disponibile: le misure restano con prezzo da definire.")
        return {"abbinate": 0}

    # Pre-filtraggio locale
    mappa_cand = {}
    senza = []
    for m in misure:
        cands = cerca_voci(elenchi, m["misura"], m["um_misura"])
        for j, c in enumerate(cands):
            c["cid"] = f"{m['id']}-{j}"
            mappa_cand[c["cid"]] = c
        m["candidati"] = cands
        if not cands:
            senza.append(m["id"])
    if senza:
        _segna_da_definire(senza, "Nessuna voce simile trovata negli elenchi")
    da_ai = [m for m in misure if m["candidati"]]

    abbinate = 0
    for i in range(0, len(da_ai), MISURE_PER_CHIAMATA):
        gruppo = da_ai[i:i + MISURE_PER_CHIAMATA]
        testo = _richiesta(gruppo)
        stima = stima_costo_eur(MODELLO, int((len(testo) + len(SYSTEM_ABBINA)) / 3.3), 150 * len(gruppo))
        motivo = verifica_disponibilita(user, stima)
        if motivo:
            _messaggio(progetto_id, 0,
                       "Versione demo limitata: budget insufficiente per abbinare automaticamente i prezzi. "
                       "Puoi cercare le voci o inserire i prezzi a mano." if motivo == "budget" else
                       "Raggiunto il limite giornaliero di chiamate: l'abbinamento dei prezzi riprenderà domani.")
            return {"abbinate": abbinate, "interrotto": motivo}
        try:
            client = TrackedClient(user, "abbinamento_prezzi")
            r = client.messages.create(model=MODELLO, max_tokens=200 * len(gruppo) + 300,
                                       system=SYSTEM_ABBINA,
                                       messages=[{"role": "user", "content": testo}])
            dati = pulisci_json(r.content[0].text) or {}
        except Exception as e:
            log.exception("Abbinamento prezzi fallito")
            _messaggio(progetto_id, 1, f"Errore durante l'abbinamento dei prezzi: {e}. Riprova più tardi.")
            return {"abbinate": abbinate, "errore": str(e)}
        scelte = {str(a.get("misura")): a for a in dati.get("abbinamenti", []) if isinstance(a, dict)}
        for m in gruppo:
            a = scelte.get(str(m["id"]), {})
            c = mappa_cand.get(str(a.get("voce"))) if a.get("voce") else None
            if c and c["cid"].startswith(f"{m['id']}-"):
                _applica_voce(m["id"], c, "abbinata", (a.get("nota") or "").strip() or None)
                abbinate += 1
            else:
                _segna_da_definire([m["id"]], (a.get("nota") or "").strip() or "Nessuna voce adatta negli elenchi")
    _messaggio(progetto_id, 0, None)
    return {"abbinate": abbinate}


def _applica_voce(riga_id: int, c: dict, stato: str, nota: str = None):
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE progetto_costi SET stato=?, livello=?, elenco_id=?, elenco_nome=?, codice=?,
                      descrizione_voce=?, um_voce=?, prezzo=?, nota=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (stato, c["livello"], c["elenco_id"], c["elenco_nome"], c["codice"], c["descrizione"],
             c["um"], c["prezzo"], nota, riga_id))
        conn.commit()
    finally:
        conn.close()


def _segna_da_definire(ids: list, nota: str):
    conn = get_conn()
    try:
        conn.executemany(
            """UPDATE progetto_costi SET stato='da_definire', livello=NULL, elenco_id=NULL, elenco_nome=NULL,
                      codice=NULL, descrizione_voce=NULL, um_voce=NULL, prezzo=NULL, nota=? WHERE id=?""",
            [(nota, i) for i in ids])
        conn.commit()
    finally:
        conn.close()


def _messaggio(progetto_id: int, da_abbinare: int, msg):
    conn = get_conn()
    try:
        conn.execute("UPDATE progetti SET costi_da_abbinare=?, costi_messaggio=? WHERE id=?",
                     (da_abbinare, msg, progetto_id))
        conn.commit()
    finally:
        conn.close()


def progetto_da_abbinare():
    conn = get_conn()
    try:
        r = conn.execute(
            """SELECT p.id FROM progetti p WHERE p.costi_da_abbinare = 1
               AND NOT EXISTS (SELECT 1 FROM progetto_tappe t WHERE t.progetto_id = p.id
                               AND t.numero = 11 AND t.stato IN ('in_coda','in_generazione'))
               ORDER BY p.id LIMIT 1""").fetchone()
    finally:
        conn.close()
    return r["id"] if r else None


# ══════════════════════════════════════════════════════════════════════════════
# 4. Lettura e totali
# ══════════════════════════════════════════════════════════════════════════════

def righe(progetto_id: int) -> list:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM progetto_costi WHERE progetto_id=? AND attiva=1 ORDER BY ordine, id",
                            (progetto_id,)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["categoria_lettera"] = categoria_lettera(d["categoria"])
        d["importo"] = round(d["prezzo"] * d["quantita"], 2) if d["prezzo"] is not None and d["quantita"] is not None else None
        um_m, um_v = _um_base(d["um_misura"]), _um_base(d["um_voce"])
        d["um_diverse"] = bool(d["prezzo"] is not None and um_m and um_v and um_m != um_v)
        out.append(d)
    return out


def totali(elenco: list) -> dict:
    per_cat = {}
    for r in elenco:
        k = r["categoria_lettera"]
        c = per_cat.setdefault(k, {"lettera": k, "descrizione": CATEGORIE.get(k, "Altre misure"),
                                    "importo": 0.0, "voci": 0, "da_definire": 0})
        c["voci"] += 1
        if r["importo"] is None:
            c["da_definire"] += 1
        else:
            c["importo"] = round(c["importo"] + r["importo"], 2)
    ordinate = [per_cat[k] for k in sorted(per_cat, key=lambda x: (x == "altro", x))]
    return {"categorie": ordinate, "totale": round(sum(c["importo"] for c in ordinate), 2),
            "da_definire": sum(c["da_definire"] for c in ordinate)}

"""
services/tappe_psc.py — Motore delle 12 tappe del PSC

- FASCICOLO: dati estratti da tutti i documenti del progetto (blocco 2), in forma compatta
  e deterministica, così resta identico tra una tappa e l'altra → PROMPT CACHING.
  Struttura della richiesta (la parte fissa è in cache, ~90% di risparmio sulla rilettura):
      system   = istruzioni + skill (METODOLOGIA, SKILL, RISCHI, [AMIANTO])   ← cache
      user[0]  = fascicolo di progetto                                        ← cache
      user[1]  = data inizio lavori + risposte al questionario del sopralluogo
      user[2]  = tappe precedenti (versione corrente, anche se modificata dal CSP)
      user[3]  = istruzioni della tappa + struttura JSON + eventuale nota del CSP
- CASCATA: dopo la (ri)generazione o la modifica manuale di una tappa, tutte le tappe
  successive già generate vengono rigenerate; quelle modificate a mano sono escluse e
  segnate "da ricontrollare".
- BOZZA COMPLETA: accoda le 12 tappe e le esegue in ordine nel worker in background.
- BUDGET: prima di ogni tappa si stima il costo; se non basta la catena si ferma, le tappe
  non eseguite restano visibili (con il contenuto precedente, segnate "da aggiornare").
"""
import json
import logging
import os
import re

from database import get_conn, get_user_by_username
from services import tappe_definizioni as td
from services.ai_costi import (TrackedClient, verifica_disponibilita, stima_costo_eur,
                               calcola_costo_usd, EUR_PER_USD)
from services.documenti_progetto import etichetta, pulisci_json

log = logging.getLogger("tappe_psc")

MODELLO = "claude-sonnet-4-6"
MAX_TOKENS_DEFAULT = 8000
MAX_CARATTERI_FASCICOLO = 480_000          # ~150.000 token
CARTELLA_SKILL = os.path.join(os.path.dirname(__file__), "..", "skill")
SKILL_BASE = ["METODOLOGIA_PSC.md", "SKILL.md", "RISCHI_PSC.md"]
SKILL_AMIANTO = "AMIANTO.md"
STATI_ATTIVI = ("in_coda", "in_generazione")

SYSTEM_BASE = """Sei un Coordinatore per la Sicurezza in fase di Progettazione (CSP) esperto.
Stai redigendo, tappa per tappa, un Piano di Sicurezza e Coordinamento (D.Lgs. 81/2008,
art. 100 e Allegato XV) seguendo la METODOLOGIA PSC riportata sotto.

REGOLE
1. Usa i dati del FASCICOLO DI PROGETTO, le RISPOSTE DEL CSP al questionario (che prevalgono
   sui documenti) e le TAPPE PRECEDENTI, che sono già state validate o corrette dal CSP:
   rispettale e mantieni la coerenza (stesse imprese, stessi codici di lavorazione, stesse settimane).
2. Non inventare dati di fatto (nomi, misure, date, quantità, indirizzi). Se un dato serve ma
   non è disponibile, scrivi letteralmente "DA VERIFICARE" nella cella o nel testo, aggiungilo
   in "da_verificare" e formula una domanda precisa in "domande_sopralluogo".
3. Le valutazioni tecniche (rischi, misure, soluzioni organizzative) sono invece il tuo compito:
   proponile in modo concreto e specifico per QUESTO cantiere, non generico.
4. Scrivi in italiano tecnico, chiaro, con frasi complete. Nelle tabelle una riga per elemento.
5. Rispondi SOLO con un oggetto JSON valido, con esattamente la struttura richiesta
   (stesse sezioni, stessi id, stesse colonne nello stesso ordine). Nessun testo fuori dal JSON.
"""


# ══════════════════════════════════════════════════════════════════════════════
# Skill e fascicolo
# ══════════════════════════════════════════════════════════════════════════════

def _leggi_skill(nome: str) -> str:
    try:
        with open(os.path.join(CARTELLA_SKILL, nome), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        log.warning(f"Skill non trovata: {nome}")
        return ""


def costruisci_system(con_amianto: bool) -> list:
    parti = [SYSTEM_BASE]
    for nome in SKILL_BASE + ([SKILL_AMIANTO] if con_amianto else []):
        testo = _leggi_skill(nome)
        if testo:
            parti.append(f"\n\n===== SKILL: {nome} =====\n{testo}")
    return [{"type": "text", "text": "".join(parti), "cache_control": {"type": "ephemeral"}}]


_RE_AMIANTO = re.compile(r"amianto|eternit|fibro-?cemento|cemento[- ]amianto|asbest", re.IGNORECASE)


def _indizi_amianto(documenti: list) -> bool:
    for d in documenti:
        for blocco in d["blocchi"]:
            dati = blocco or {}
            if dati.get("indizi_amianto"):
                return True
            anno = str((dati.get("opera") or {}).get("anno_costruzione", ""))
            m = re.search(r"(1[89]\d\d)", anno)
            if m and int(m.group(1)) < 1992:
                return True
            if _RE_AMIANTO.search(json.dumps(dati, ensure_ascii=False)):
                return True
    return False


def costruisci_fascicolo(progetto_id: int) -> dict:
    """Testo del fascicolo (deterministico, per il caching) + informazioni di supporto."""
    conn = get_conn()
    try:
        docs = conn.execute(
            """SELECT id, nome_file, tipo_ai, tipo_csp, pagine FROM progetto_documenti
               WHERE progetto_id = ? AND stato = 'completato' ORDER BY priorita, id""",
            (progetto_id,)).fetchall()
        documenti = []
        for d in docs:
            blocchi = conn.execute(
                "SELECT pagine_da, pagine_a, dati_json FROM progetto_estrazioni WHERE documento_id = ? ORDER BY blocco",
                (d["id"],)).fetchall()
            documenti.append({
                "nome": d["nome_file"], "tipo": d["tipo_csp"] or d["tipo_ai"] or "altro",
                "pagine": d["pagine"],
                "blocchi": [json.loads(b["dati_json"]) if b["dati_json"] else {} for b in blocchi],
                "intervalli": [(b["pagine_da"], b["pagine_a"]) for b in blocchi],
            })
        elenchi = conn.execute(
            "SELECT COUNT(*) AS n FROM elenchi_prezzi WHERE progetto_id = ? AND stato = 'pronto'",
            (progetto_id,)).fetchone()["n"]
    finally:
        conn.close()

    righe = ["FASCICOLO DI PROGETTO — dati estratti dai documenti caricati dal CSP", ""]
    for d in documenti:
        if d["tipo"] == "elenco_prezzi":
            continue
        righe.append(f"### Documento: {d['nome']} — tipo: {etichetta(d['tipo'])}"
                     + (f" — {d['pagine']} pagine" if d["pagine"] else ""))
        for (da, a), dati in zip(d["intervalli"], d["blocchi"]):
            if da:
                righe.append(f"[pagine {da}-{a}]")
            righe.append(json.dumps(dati, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        righe.append("")
    if elenchi:
        righe.append(f"(Nel progetto sono presenti {elenchi} elenchi prezzi: verranno usati per i costi.)")
    testo = "\n".join(righe)
    troncato = False
    if len(testo) > MAX_CARATTERI_FASCICOLO:
        testo = testo[:MAX_CARATTERI_FASCICOLO] + "\n[... fascicolo troncato per dimensione ...]"
        troncato = True
    return {
        "testo": testo,
        "n_documenti": len([d for d in documenti if d["tipo"] != "elenco_prezzi"]),
        "amianto": _indizi_amianto(documenti),
        "troncato": troncato,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Lettura / scrittura tappe
# ══════════════════════════════════════════════════════════════════════════════

def assicura_tappe(progetto_id: int):
    conn = get_conn()
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO progetto_tappe (progetto_id, numero) VALUES (?, ?)",
            [(progetto_id, t["numero"]) for t in td.TAPPE])
        conn.commit()
    finally:
        conn.close()


def leggi_tappe(progetto_id: int) -> list:
    assicura_tappe(progetto_id)
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM progetto_tappe WHERE progetto_id = ? ORDER BY numero",
                            (progetto_id,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _aggiorna(progetto_id: int, numero: int, **campi):
    assegnazioni = ", ".join(f"{k} = ?" for k in campi) + ", updated_at = CURRENT_TIMESTAMP"
    conn = get_conn()
    try:
        conn.execute(f"UPDATE progetto_tappe SET {assegnazioni} WHERE progetto_id = ? AND numero = ?",
                     (*campi.values(), progetto_id, numero))
        conn.commit()
    finally:
        conn.close()


def _aggiorna_progetto(progetto_id: int, **campi):
    assegnazioni = ", ".join(f"{k} = ?" for k in campi)
    conn = get_conn()
    try:
        conn.execute(f"UPDATE progetti SET {assegnazioni} WHERE id = ?", (*campi.values(), progetto_id))
        conn.commit()
    finally:
        conn.close()


def contenuto(tappa: dict):
    return json.loads(tappa["contenuto_json"]) if tappa.get("contenuto_json") else None


# ══════════════════════════════════════════════════════════════════════════════
# Accodamento e cascata
# ══════════════════════════════════════════════════════════════════════════════

def accoda_tappa(progetto_id: int, numero: int, nota: str = None):
    """Accoda una tappa su richiesta esplicita del CSP (anche se modificata a mano)."""
    campi = {"stato": "in_coda", "errore": None}
    if nota is not None:
        campi["nota_csp"] = nota.strip() or None
    _aggiorna(progetto_id, numero, **campi)


def cascata(progetto_id: int, da_numero: int) -> dict:
    """
    Dopo un cambiamento della tappa `da_numero`: le tappe successive GIÀ generate vengono
    rigenerate; quelle modificate a mano restano com'erano e diventano "da ricontrollare".
    Le tappe mai generate non vengono toccate.
    """
    rigenerate, da_ricontrollare = [], []
    for t in leggi_tappe(progetto_id):
        if t["numero"] <= da_numero or not t["contenuto_json"] or t["stato"] in STATI_ATTIVI:
            continue
        if t["modificata_a_mano"]:
            _aggiorna(progetto_id, t["numero"], da_ricontrollare=1)
            da_ricontrollare.append(t["numero"])
        else:
            _aggiorna(progetto_id, t["numero"], stato="in_coda", errore=None)
            rigenerate.append(t["numero"])
    return {"rigenerate": rigenerate, "da_ricontrollare": da_ricontrollare}


def avvia_bozza(progetto_id: int) -> dict:
    """Genera bozza completa: tutte le 12 tappe in ordine (le modificate a mano sono escluse)."""
    accodate, saltate = [], []
    for t in leggi_tappe(progetto_id):
        if t["stato"] in STATI_ATTIVI:
            continue
        if t["modificata_a_mano"] and t["contenuto_json"]:
            _aggiorna(progetto_id, t["numero"], da_ricontrollare=1)
            saltate.append(t["numero"])
        else:
            _aggiorna(progetto_id, t["numero"], stato="in_coda", errore=None)
            accodate.append(t["numero"])
    _aggiorna_progetto(progetto_id, bozza_stato="in_corso", bozza_messaggio=None)
    return {"accodate": accodate, "da_ricontrollare": saltate}


def _interrompi_catena(progetto_id: int, da_numero: int, messaggio: str):
    """Ferma la catena: le tappe ancora in coda tornano allo stato precedente, segnate da aggiornare."""
    for t in leggi_tappe(progetto_id):
        if t["numero"] >= da_numero and t["stato"] == "in_coda":
            if t["contenuto_json"]:
                _aggiorna(progetto_id, t["numero"], stato="generata", da_aggiornare=1)
            else:
                _aggiorna(progetto_id, t["numero"], stato="da_generare")
    _aggiorna_progetto(progetto_id, bozza_stato="interrotta", bozza_messaggio=messaggio)


def crea_tappe_vuote(progetto_id: int) -> list:
    """Tappe non ancora presenti → strutture vuote da compilare a mano (nessuna AI)."""
    create = []
    for t in leggi_tappe(progetto_id):
        if t["contenuto_json"] or t["stato"] in STATI_ATTIVI:
            continue
        vuoto = td.normalizza(t["numero"], {})
        _aggiorna(progetto_id, t["numero"], contenuto_json=json.dumps(vuoto, ensure_ascii=False),
                  stato="generata", modificata_a_mano=1, errore=None)
        create.append(t["numero"])
    return create


def e_manuale(progetto_id: int) -> bool:
    p = _progetto(progetto_id)
    return bool(p and (p.get("modalita") or "ai") == "manuale")


def salva_modifica_csp(progetto_id: int, numero: int, dati: dict) -> dict:
    nuovo = td.normalizza(numero, dati)
    _aggiorna(progetto_id, numero, contenuto_json=json.dumps(nuovo, ensure_ascii=False),
              modificata_a_mano=1, da_ricontrollare=0, da_aggiornare=0, stato="generata", errore=None)
    if numero == 11:
        from services import costi_sicurezza
        costi_sicurezza.sincronizza(progetto_id)
    if e_manuale(progetto_id):
        # Progetto manuale: tutte le tappe sono scritte dal CSP, nessuna cascata né segnalazione
        return {"rigenerate": [], "da_ricontrollare": []}
    return cascata(progetto_id, numero)


def segna_verificata(progetto_id: int, numero: int):
    _aggiorna(progetto_id, numero, da_ricontrollare=0, da_aggiornare=0)


# ══════════════════════════════════════════════════════════════════════════════
# Questionario del sopralluogo
# ══════════════════════════════════════════════════════════════════════════════

def _aggiorna_domande(progetto_id: int, numero: int, cont: dict):
    """Sostituisce le domande ancora aperte della tappa con quelle nuove (le risposte restano)."""
    conn = get_conn()
    try:
        risposte = {r["testo"].strip().lower() for r in conn.execute(
            "SELECT testo FROM progetto_domande WHERE progetto_id=? AND tappa=? AND stato != 'aperta'",
            (progetto_id, numero)).fetchall()}
        conn.execute("DELETE FROM progetto_domande WHERE progetto_id=? AND tappa=? AND stato='aperta'",
                     (progetto_id, numero))
        nuove = []
        for q in cont.get("domande_sopralluogo", []):
            nuove.append(("domanda", q))
        for d in cont.get("da_verificare", []):
            testo = d["campo"] + (f" — {d['motivo']}" if d.get("motivo") else "")
            nuove.append(("da_verificare", testo))
        visti = set()
        for origine, testo in nuove:
            chiave = testo.strip().lower()
            if not chiave or chiave in visti or chiave in risposte:
                continue
            visti.add(chiave)
            conn.execute("INSERT INTO progetto_domande (progetto_id, tappa, origine, testo) VALUES (?,?,?,?)",
                         (progetto_id, numero, origine, testo.strip()))
        conn.commit()
    finally:
        conn.close()


def _risposte_per_prompt(progetto_id: int) -> str:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT tappa, testo, risposta FROM progetto_domande
               WHERE progetto_id = ? AND stato IN ('risposta','applicata') AND risposta IS NOT NULL
               ORDER BY tappa, id""", (progetto_id,)).fetchall()
    finally:
        conn.close()
    if not rows:
        return "Nessuna risposta al questionario del sopralluogo."
    return "\n".join(f"- (tappa {r['tappa']}) {r['testo']}\n  RISPOSTA DEL CSP: {r['risposta']}" for r in rows)


def applica_risposte(progetto_id: int) -> dict:
    """Le risposte nuove entrano nel prompt: rigenero dalla prima tappa interessata in poi."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, tappa FROM progetto_domande WHERE progetto_id = ? AND stato = 'risposta'",
            (progetto_id,)).fetchall()
        if not rows:
            return {"applicate": 0, "rigenerate": [], "da_ricontrollare": []}
        conn.execute("UPDATE progetto_domande SET stato = 'applicata' WHERE progetto_id = ? AND stato = 'risposta'",
                     (progetto_id,))
        conn.commit()
    finally:
        conn.close()
    prima = min(r["tappa"] for r in rows)
    tappe = {t["numero"]: t for t in leggi_tappe(progetto_id)}
    rigenerate, da_ricontrollare = [], []
    t0 = tappe[prima]
    if t0["contenuto_json"] and t0["stato"] not in STATI_ATTIVI:
        if t0["modificata_a_mano"]:
            _aggiorna(progetto_id, prima, da_ricontrollare=1)
            da_ricontrollare.append(prima)
        else:
            _aggiorna(progetto_id, prima, stato="in_coda", errore=None)
            rigenerate.append(prima)
    esito = cascata(progetto_id, prima)
    return {"applicate": len(rows), "rigenerate": rigenerate + esito["rigenerate"],
            "da_ricontrollare": da_ricontrollare + esito["da_ricontrollare"]}


# ══════════════════════════════════════════════════════════════════════════════
# Generazione di una tappa
# ══════════════════════════════════════════════════════════════════════════════

def _tappe_precedenti_testo(tappe: list, numero: int) -> str:
    parti = []
    for t in tappe:
        if t["numero"] >= numero:
            break
        c = contenuto(t)
        d = td.definizione(t["numero"])
        if not c:
            parti.append(f"## Tappa {t['numero']} — {d['titolo']}: NON ANCORA GENERATA")
            continue
        origine = "modificata dal CSP" if t["modificata_a_mano"] else "generata"
        parti.append(f"## Tappa {t['numero']} — {d['titolo']} ({origine})\n"
                     + json.dumps({"sezioni": c["sezioni"]}, ensure_ascii=False, separators=(",", ":")))
    return "\n\n".join(parti) if parti else "Nessuna tappa precedente (questa è la prima)."


def costruisci_richiesta(progetto: dict, numero: int, tappe: list, fascicolo: dict, nota: str = None) -> dict:
    d = td.definizione(numero)
    data_inizio = progetto.get("data_inizio_lavori") or "DA VERIFICARE (non indicata dal CSP)"
    istruzioni = (
        f"TAPPA {numero} di {td.NUMERO_TAPPE}: {d['titolo']}\n\n"
        f"OBIETTIVO\n{d['obiettivo']}\n\n"
        + (f"NOTA DEL CSP PER QUESTA GENERAZIONE (seguila con priorità):\n{nota}\n\n" if nota else "")
        + "STRUTTURA DA RESTITUIRE (sostituisci i \"...\" con i contenuti; aggiungi tutte le righe "
          "necessarie alle tabelle; lascia le liste vuote se non servono):\n"
        + "<<SCHEMA>>\n" + json.dumps(td.scheletro(numero), ensure_ascii=False, indent=1) + "\n<<FINE_SCHEMA>>"
    )
    return {
        "system": costruisci_system(fascicolo["amianto"]),
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": fascicolo["testo"], "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"DATA DI INIZIO LAVORI (indicata dal CSP): {data_inizio}\n\n"
                                     f"RISPOSTE DEL CSP AL QUESTIONARIO DEL SOPRALLUOGO:\n{_risposte_per_prompt(progetto['id'])}"
                                     + (f"\n\n{_presidi_per_prompt(progetto['id'])}" if numero == 9 else "")},
            {"type": "text", "text": "TAPPE PRECEDENTI (versione corrente):\n\n" + _tappe_precedenti_testo(tappe, numero)},
            {"type": "text", "text": istruzioni},
        ]}],
        "max_tokens": d.get("max_tokens", MAX_TOKENS_DEFAULT),
    }


def _presidi_per_prompt(progetto_id: int) -> str:
    from services.presidi import testo_per_prompt
    return testo_per_prompt(progetto_id) or "Presidi di emergenza non ancora cercati: indicali come DA VERIFICARE."


def _conta_token_stimati(richiesta: dict) -> tuple:
    """(token in cache, token non in cache) stimati dai caratteri."""
    in_cache = len(richiesta["system"][0]["text"]) + len(richiesta["messages"][0]["content"][0]["text"])
    fuori = sum(len(b["text"]) for b in richiesta["messages"][0]["content"][1:])
    return int(in_cache / 3.5), int(fuori / 3.5)


def stima_tappa_eur(richiesta: dict, cache_calda: bool = True) -> float:
    in_cache, fuori = _conta_token_stimati(richiesta)
    fattore = 0.10 if cache_calda else 1.25
    input_equiv = int(in_cache * fattore) + fuori
    return stima_costo_eur(MODELLO, input_equiv, int(richiesta["max_tokens"] * 0.55))


def _progetto(progetto_id: int) -> dict:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM progetti WHERE id = ?", (progetto_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def stima_generazione(progetto_id: int, numeri: list) -> float:
    """Stima (euro) per generare le tappe indicate, usata dall'interfaccia prima di confermare."""
    if not numeri:
        return 0.0
    progetto = _progetto(progetto_id)
    fascicolo = costruisci_fascicolo(progetto_id)
    tappe = leggi_tappe(progetto_id)
    totale = 0.0
    for i, n in enumerate(sorted(numeri)):
        totale += stima_tappa_eur(costruisci_richiesta(progetto, n, tappe, fascicolo), cache_calda=i > 0)
    return round(totale, 3)


def esegui_tappa(tappa: dict):
    """Chiamata dal worker: genera UNA tappa in coda e, se va a buon fine, lancia la cascata."""
    progetto_id, numero = tappa["progetto_id"], tappa["numero"]
    progetto = _progetto(progetto_id)
    user = get_user_by_username(progetto["username"]) if progetto else None
    if not user:
        _aggiorna(progetto_id, numero, stato="errore", errore="Progetto o utente non trovato")
        return

    tappe = leggi_tappe(progetto_id)
    # Le tappe precedenti devono esistere: se una è ancora in coda, si aspetta il proprio turno
    fascicolo = costruisci_fascicolo(progetto_id)
    richiesta = costruisci_richiesta(progetto, numero, tappe, fascicolo, tappa.get("nota_csp"))
    stima = stima_tappa_eur(richiesta, cache_calda=numero > 1)

    motivo = verifica_disponibilita(user, stima)
    if motivo:
        msg = ("Versione demo limitata: il budget disponibile non basta per generare le tappe "
               f"dalla {numero} in poi. Le tappe già prodotte restano consultabili e modificabili; "
               "il progetto di esempio mostra un PSC completo.") if motivo == "budget" else (
               "Raggiunto il limite giornaliero di chiamate: potrai riprendere la generazione domani.")
        _interrompi_catena(progetto_id, numero, msg)
        return

    _aggiorna(progetto_id, numero, stato="in_generazione", errore=None)
    try:
        client = TrackedClient(user, "tappa_psc")
        risposta = client.messages.create(model=MODELLO, max_tokens=richiesta["max_tokens"],
                                          system=richiesta["system"], messages=richiesta["messages"])
    except Exception as e:
        log.exception(f"Errore generazione tappa {numero} del progetto {progetto_id}")
        _aggiorna(progetto_id, numero, stato="errore", errore=f"Errore AI: {getattr(e, 'message', str(e))}")
        _interrompi_catena(progetto_id, numero + 1,
                           f"Generazione interrotta alla tappa {numero} per un errore: puoi riprovare.")
        return

    costo = calcola_costo_usd(MODELLO, risposta.usage) * EUR_PER_USD
    testo = "".join(b.text for b in risposta.content if getattr(b, "type", "text") == "text")
    dati = pulisci_json(testo)
    troncata = getattr(risposta, "stop_reason", None) == "max_tokens"
    if dati is None:
        _aggiorna(progetto_id, numero, stato="errore", costo_eur=(tappa.get("costo_eur") or 0) + costo,
                  errore="Risposta AI non interpretabile" + (" (troppo lunga)" if troncata else "") + ": riprova")
        _interrompi_catena(progetto_id, numero + 1, f"Generazione interrotta alla tappa {numero}: riprova.")
        return

    nuovo = td.normalizza(numero, dati)
    # Il contenuto si salva mentre la tappa è ancora "in_generazione": lo stato "generata" arriva
    # solo DOPO aver accodato la cascata, così non esiste un istante in cui la catena sembra finita
    # (l'interfaccia smetterebbe di aggiornarsi prima che partano le tappe successive).
    _aggiorna(progetto_id, numero, contenuto_json=json.dumps(nuovo, ensure_ascii=False),
              modificata_a_mano=0, da_ricontrollare=0, da_aggiornare=0, nota_csp=None, errore=None,
              costo_eur=(tappa.get("costo_eur") or 0) + costo, generata_at=_ora())
    _aggiorna_domande(progetto_id, numero, nuovo)
    if numero == 9:
        # Blocco 5: la tabella dei presidi resta quella cercata/confermata dal CSP
        from services.presidi import aggiorna_tappa_9
        aggiorna_tappa_9(progetto_id)
    if numero == 11:
        # Blocco 4: la stima dei costi segue la tabella delle misure (abbinamento prezzi in background)
        from services import costi_sicurezza
        costi_sicurezza.sincronizza(progetto_id)

    # Cascata: le successive già generate si rigenerano (quelle in coda per la bozza lo sono già)
    cascata(progetto_id, numero)
    _aggiorna(progetto_id, numero, stato="generata")

    # Fine della catena?
    ancora = [t for t in leggi_tappe(progetto_id) if t["stato"] in STATI_ATTIVI]
    if not ancora and progetto.get("bozza_stato") == "in_corso":
        _aggiorna_progetto(progetto_id, bozza_stato="completata", bozza_messaggio=None)


def _ora():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def prossima_tappa_in_coda():
    """La tappa da eseguire: in ogni progetto la più bassa in coda, solo se nessuna è in generazione."""
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT t.* FROM progetto_tappe t
               WHERE t.stato = 'in_coda'
                 AND NOT EXISTS (SELECT 1 FROM progetto_tappe x WHERE x.progetto_id = t.progetto_id
                                 AND x.stato = 'in_generazione')
                 AND NOT EXISTS (SELECT 1 FROM progetto_documenti d WHERE d.progetto_id = t.progetto_id
                                 AND d.stato IN ('da_classificare','in_coda','in_elaborazione'))
               ORDER BY t.progetto_id, t.numero LIMIT 1""").fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def ripristina_dopo_riavvio():
    conn = get_conn()
    try:
        conn.execute("UPDATE progetto_tappe SET stato = 'in_coda' WHERE stato = 'in_generazione'")
        conn.commit()
    finally:
        conn.close()

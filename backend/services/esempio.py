"""
services/esempio.py — Progetto di esempio (blocco 6)

- L'amministratore pubblica un suo progetto completo come esempio.
- Ogni account riceve UNA copia personale al primo accesso ai progetti PSC (nuovi ed esistenti).
  La copia contiene tutti i dati (fascicolo, tappe, questionario, costi, presidi, schemi con
  sfondo, checklist) ma NON i file originali. Può essere modificata, esportata ed eliminata.
- Se l'esempio viene ripubblicato, le copie già distribuite restano com'erano.
"""
import logging
import shutil

from database import get_conn, cartella_schemi

log = logging.getLogger("esempio")

CAMPI_PROGETTO = ("data_inizio_lavori", "importo_lavori", "incidenza_manodopera", "costo_giornaliero",
                  "ug_scelta", "indirizzo_cantiere", "bozza_stato")


def pubblicato():
    conn = get_conn()
    try:
        r = conn.execute("SELECT * FROM esempio_pubblicato ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    return dict(r) if r else None


def pubblica(progetto_id: int, admin: dict):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO esempio_pubblicato (progetto_id, pubblicato_da) VALUES (?, ?)",
                     (progetto_id, admin["username"]))
        conn.commit()
    finally:
        conn.close()


def _copia_righe(conn, tabella, sorgente, nuovo, escludi=("id",), mappa=None):
    """Copia le righe di una tabella legata al progetto; restituisce {id_vecchio: id_nuovo}."""
    colonne = [r[1] for r in conn.execute(f"PRAGMA table_info({tabella})").fetchall() if r[1] not in escludi]
    ids = {}
    for r in conn.execute(f"SELECT * FROM {tabella} WHERE progetto_id = ?", (sorgente,)).fetchall():
        valori = {c: r[c] for c in colonne}
        valori["progetto_id"] = nuovo
        if mappa:
            valori.update(mappa(dict(r)))
        cur = conn.execute(f"INSERT INTO {tabella} ({', '.join(valori)}) VALUES ({', '.join('?' * len(valori))})",
                           tuple(valori.values()))
        if "id" in r.keys():
            ids[r["id"]] = cur.lastrowid
    return ids


def copia_per(user: dict, sorgente_id: int) -> int:
    conn = get_conn()
    try:
        src = conn.execute("SELECT * FROM progetti WHERE id = ?", (sorgente_id,)).fetchone()
        if not src:
            return None
        cur = conn.execute(
            f"""INSERT INTO progetti (username, nome, stato, is_esempio, esempio_sorgente, file_eliminati_at,
                       {', '.join(CAMPI_PROGETTO)})
                VALUES (?, ?, 'aperto', 1, ?, CURRENT_TIMESTAMP, {', '.join('?' * len(CAMPI_PROGETTO))})""",
            (user["username"], f"Esempio — {src['nome']}", sorgente_id, *[src[c] for c in CAMPI_PROGETTO]))
        nuovo = cur.lastrowid

        # Elenchi prezzi del progetto (con le voci), poi documenti ed estrazioni
        mappa_elenchi = {}
        for e in conn.execute("SELECT * FROM elenchi_prezzi WHERE progetto_id = ?", (sorgente_id,)).fetchall():
            c = conn.execute(
                """INSERT INTO elenchi_prezzi (username, livello, progetto_id, nome, nome_file, stato, n_voci)
                   VALUES (?, 'progetto', ?, ?, ?, ?, ?)""",
                (user["username"], nuovo, e["nome"], e["nome_file"], e["stato"], e["n_voci"]))
            mappa_elenchi[e["id"]] = c.lastrowid
            conn.execute(
                """INSERT INTO elenchi_prezzi_voci (elenco_id, codice, descrizione, um, prezzo, perc_manodopera, capitolo)
                   SELECT ?, codice, descrizione, um, prezzo, perc_manodopera, capitolo FROM elenchi_prezzi_voci
                   WHERE elenco_id = ?""", (c.lastrowid, e["id"]))
        mappa_doc = _copia_righe(conn, "progetto_documenti", sorgente_id, nuovo,
                                 mappa=lambda r: {"file_path": None,
                                                  "elenco_id": mappa_elenchi.get(r["elenco_id"])})
        for vecchio, nuovo_doc in mappa_doc.items():
            conn.execute(
                """INSERT INTO progetto_estrazioni (documento_id, blocco, pagine_da, pagine_a, dati_json)
                   SELECT ?, blocco, pagine_da, pagine_a, dati_json FROM progetto_estrazioni WHERE documento_id = ?""",
                (nuovo_doc, vecchio))

        for tabella in ("progetto_tappe", "progetto_domande", "progetto_costi", "progetto_presidi"):
            _copia_righe(conn, tabella, sorgente_id, nuovo)
        conn.execute(
            """INSERT INTO progetto_checklist (progetto_id, voce, esito, motivazione)
               SELECT ?, voce, esito, motivazione FROM progetto_checklist WHERE progetto_id = ?""", (nuovo, sorgente_id))
        # Le copie in coda di elaborazione non devono ripartire (nessun costo per l'utente)
        conn.execute("UPDATE progetto_tappe SET stato='generata' WHERE progetto_id=? AND stato IN ('in_coda','in_generazione')", (nuovo,))
        conn.execute("UPDATE progetti SET costi_da_abbinare=0 WHERE id=?", (nuovo,))

        def sfondo(r):
            if not r.get("sfondo_path"):
                return {}
            destinazione = f"{cartella_schemi(nuovo)}/copia_{r['id']}.png"
            try:
                shutil.copyfile(r["sfondo_path"], destinazione)
                return {"sfondo_path": destinazione}
            except OSError:
                return {"sfondo_path": None}
        _copia_righe(conn, "progetto_schemi", sorgente_id, nuovo, mappa=sfondo)

        conn.execute("INSERT OR REPLACE INTO esempio_copie (username, sorgente_id, copia_id) VALUES (?, ?, ?)",
                     (user["username"], sorgente_id, nuovo))
        conn.commit()
        return nuovo
    except Exception:
        conn.rollback()
        log.exception("Copia del progetto di esempio non riuscita")
        return None
    finally:
        conn.close()


def distribuisci(user: dict):
    """Chiamata all'apertura dell'elenco dei progetti: una sola copia per account, mai ripetuta."""
    e = pubblicato()
    if not e:
        return
    conn = get_conn()
    try:
        gia = conn.execute("SELECT 1 FROM esempio_copie WHERE username = ?", (user["username"],)).fetchone()
        src = conn.execute("SELECT username FROM progetti WHERE id = ?", (e["progetto_id"],)).fetchone()
    finally:
        conn.close()
    if gia or not src or src["username"] == user["username"]:
        return
    copia_per(user, e["progetto_id"])

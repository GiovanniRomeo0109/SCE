"""
services/gestione_elenchi.py — Salvataggio degli elenchi prezzi nel DB

Livelli: progetto (caricato tra i documenti di un progetto), account (pagina
"Elenchi prezzi"), sistema (caricato dall'admin, visibile a tutti).
Il file originale viene cancellato appena le voci sono salvate; resta su disco
solo finché il CSP deve completare la mappatura delle colonne.
"""
import json
import os
import uuid

from database import get_conn, cartella_elenchi
from services.elenchi_prezzi import leggi_elenco, MappaturaRichiesta, FormatoNonSupportato


def _salva_voci(conn, elenco_id: int, voci: list):
    conn.execute("DELETE FROM elenchi_prezzi_voci WHERE elenco_id = ?", (elenco_id,))
    conn.executemany(
        """INSERT INTO elenchi_prezzi_voci
           (elenco_id, codice, descrizione, um, prezzo, perc_manodopera, capitolo)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [(elenco_id, v["codice"], v["descrizione"], v["um"], v["prezzo"],
          v.get("perc_manodopera"), v.get("capitolo")) for v in voci],
    )


def crea_elenco(username, livello: str, nome: str, nome_file: str, contenuto: bytes,
                progetto_id: int = None) -> dict:
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO elenchi_prezzi (username, livello, progetto_id, nome, nome_file, stato)
               VALUES (?, ?, ?, ?, ?, 'in_lettura')""",
            (username, livello, progetto_id, nome, nome_file),
        )
        elenco_id = cur.lastrowid
        try:
            voci = leggi_elenco(contenuto, nome_file)
            _salva_voci(conn, elenco_id, voci)
            conn.execute("UPDATE elenchi_prezzi SET stato='pronto', n_voci=? WHERE id=?",
                         (len(voci), elenco_id))
        except MappaturaRichiesta as m:
            # Conservo il file finché il CSP non indica le colonne
            est = nome_file.lower().rsplit(".", 1)[-1]
            path = os.path.join(cartella_elenchi(), f"{elenco_id}_{uuid.uuid4().hex[:8]}.{est}")
            with open(path, "wb") as f:
                f.write(contenuto)
            conn.execute(
                "UPDATE elenchi_prezzi SET stato='mappatura_richiesta', file_path=?, anteprima=? WHERE id=?",
                (path, json.dumps({"righe": m.anteprima, "n_colonne": m.n_colonne}, ensure_ascii=False),
                 elenco_id),
            )
        except (FormatoNonSupportato, Exception) as e:
            conn.execute("UPDATE elenchi_prezzi SET stato='errore', errore=? WHERE id=?",
                         (str(e), elenco_id))
        conn.commit()
        return leggi_scheda_elenco(conn, elenco_id)
    finally:
        conn.close()


def applica_mappatura(elenco_id: int, mappatura: dict) -> dict:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM elenchi_prezzi WHERE id = ?", (elenco_id,)).fetchone()
        if not row or not row["file_path"] or not os.path.exists(row["file_path"]):
            raise FormatoNonSupportato("File originale non più disponibile: ricarica l'elenco")
        with open(row["file_path"], "rb") as f:
            contenuto = f.read()
        voci = leggi_elenco(contenuto, row["nome_file"], mappatura)
        if not voci:
            raise FormatoNonSupportato(
                "Con questa associazione non è stata trovata nessuna voce con un prezzo numerico")
        _salva_voci(conn, elenco_id, voci)
        conn.execute(
            """UPDATE elenchi_prezzi SET stato='pronto', n_voci=?, file_path=NULL,
               anteprima=NULL, errore=NULL WHERE id=?""",
            (len(voci), elenco_id),
        )
        conn.commit()
        os.remove(row["file_path"])
        return leggi_scheda_elenco(conn, elenco_id)
    finally:
        conn.close()


def elimina_elenco(elenco_id: int):
    conn = get_conn()
    try:
        row = conn.execute("SELECT file_path FROM elenchi_prezzi WHERE id = ?", (elenco_id,)).fetchone()
        if row and row["file_path"] and os.path.exists(row["file_path"]):
            os.remove(row["file_path"])
        conn.execute("DELETE FROM elenchi_prezzi_voci WHERE elenco_id = ?", (elenco_id,))
        conn.execute("DELETE FROM elenchi_prezzi WHERE id = ?", (elenco_id,))
        conn.commit()
    finally:
        conn.close()


def leggi_scheda_elenco(conn, elenco_id: int) -> dict:
    row = conn.execute(
        """SELECT id, username, livello, progetto_id, nome, nome_file, stato, anteprima,
                  errore, n_voci, created_at FROM elenchi_prezzi WHERE id = ?""",
        (elenco_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["anteprima"] = json.loads(d["anteprima"]) if d["anteprima"] else None
    return d

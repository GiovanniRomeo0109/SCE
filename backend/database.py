import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "cantieri.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.executescript("""
        -- ─── COMMITTENTI ───────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS committenti (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo                TEXT    NOT NULL DEFAULT 'persona_fisica',
            nome                TEXT,
            cognome             TEXT,
            ragione_sociale     TEXT,
            codice_fiscale      TEXT,
            piva                TEXT,
            indirizzo           TEXT,
            citta               TEXT,
            cap                 TEXT,
            provincia           TEXT,
            telefono            TEXT,
            email               TEXT,
            pec                 TEXT,
            created_at          TEXT    DEFAULT (datetime('now')),
            updated_at          TEXT    DEFAULT (datetime('now'))
        );

        -- ─── IMPRESE ───────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS imprese (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            ragione_sociale     TEXT    NOT NULL,
            codice_fiscale      TEXT,
            piva                TEXT    NOT NULL,
            indirizzo           TEXT,
            citta               TEXT,
            cap                 TEXT,
            provincia           TEXT,
            telefono            TEXT,
            email               TEXT,
            pec                 TEXT,
            cciaa               TEXT,
            numero_cciaa        TEXT,
            inail_pat           TEXT,
            inps                TEXT,
            cassa_edile         TEXT,
            ccnl                TEXT    DEFAULT 'CCNL Edilizia Industria',
            -- Datore di Lavoro
            nome_dl             TEXT,
            cognome_dl          TEXT,
            -- RSPP
            nome_rspp           TEXT,
            cognome_rspp        TEXT,
            -- Medico Competente
            nome_mc             TEXT,
            cognome_mc          TEXT,
            -- RLS
            nome_rls            TEXT,
            cognome_rls         TEXT,
            created_at          TEXT    DEFAULT (datetime('now')),
            updated_at          TEXT    DEFAULT (datetime('now'))
        );

        -- ─── COORDINATORI ──────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS coordinatori (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            nome                TEXT    NOT NULL,
            cognome             TEXT    NOT NULL,
            codice_fiscale      TEXT,
            ordine_professionale TEXT,
            numero_ordine       TEXT,
            provincia_ordine    TEXT,
            titolo_studio       TEXT,
            anni_esperienza     INTEGER,
            attestato_corso     TEXT,
            data_corso          TEXT,
            data_aggiornamento  TEXT,
            indirizzo           TEXT,
            citta               TEXT,
            cap                 TEXT,
            provincia           TEXT,
            telefono            TEXT,
            email               TEXT,
            pec                 TEXT,
            created_at          TEXT    DEFAULT (datetime('now')),
            updated_at          TEXT    DEFAULT (datetime('now'))
        );

        -- ─── DOCUMENTI GENERATI ────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS documenti_generati (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_documento      TEXT    NOT NULL,
            nome_cantiere       TEXT,
            impresa_nome        TEXT,
            file_path           TEXT,
            versione            TEXT    DEFAULT '1.0',
            created_at          TEXT    DEFAULT (datetime('now'))
        );
    """)

    conn.commit()
    conn.close()
    print("✅ Database inizializzato correttamente")

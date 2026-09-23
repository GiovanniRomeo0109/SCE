import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "/data/cantieri.db")

def get_conn():
    # timeout: attende fino a 30 s se il worker in background sta scrivendo
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_usage_log_schema(cursor):
    """Ricrea usage_log con schema corretto se ha il vecchio schema (colonna giorno)."""
    try:
        cols = [row[1] for row in cursor.execute("PRAGMA table_info(usage_log)").fetchall()]
        if "giorno" in cols:
            # Schema vecchio — rinomina e ricrea
            cursor.execute("ALTER TABLE usage_log RENAME TO usage_log_old")
            cursor.execute("""
                CREATE TABLE usage_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    username     TEXT NOT NULL,
                    endpoint     TEXT NOT NULL DEFAULT '',
                    credits_used INTEGER DEFAULT 1,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Migra i dati vecchi preservando username e data
            cursor.execute("""
                INSERT INTO usage_log (username, endpoint, credits_used, created_at)
                SELECT username,
                       COALESCE(tipo_operazione, 'legacy'),
                       1,
                       giorno || ' 00:00:00'
                FROM usage_log_old
            """)
            cursor.execute("DROP TABLE usage_log_old")
            print("✅ Migrazione: usage_log ricreato con schema corretto")
        elif "endpoint" not in cols:
            cursor.execute("ALTER TABLE usage_log ADD COLUMN endpoint TEXT NOT NULL DEFAULT ''" )
            print("✅ Migrazione: aggiunta colonna endpoint a usage_log")
    except Exception as e:
        print(f"⚠️ Migrazione usage_log: {e}")

def _aggiungi_colonna(cursor, tabella: str, colonna: str, definizione: str):
    """Aggiunge una colonna solo se non esiste già."""
    cols = [r[1] for r in cursor.execute(f"PRAGMA table_info({tabella})").fetchall()]
    if colonna not in cols:
        cursor.execute(f"ALTER TABLE {tabella} ADD COLUMN {colonna} {definizione}")
        print(f"✅ Migrazione: aggiunta colonna {tabella}.{colonna}")


def _admin_emails():
    raw = os.environ.get("ADMIN_EMAILS", "giovromeo@gmail.com")
    return [e.strip().lower() for e in raw.split(",") if e.strip()]


def cartella_documenti() -> str:
    """Cartella dei DOCX generati, dentro il Volume Railway (accanto al DB)."""
    base = os.path.dirname(os.path.abspath(DB_PATH))
    path = os.path.join(base, "documenti_generati")
    os.makedirs(path, exist_ok=True)
    return path


def _crea_tabelle_anagrafica(c):
    """Tabelle usate da routers/anagrafica.py (schema originale del progetto)."""
    c.execute("""
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
        )
    """)
    c.execute("""
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
        )
    """)
    c.execute("""
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
        )
    """)


def _crea_tabelle_progetti(c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS progetti (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            username          TEXT NOT NULL,
            nome              TEXT NOT NULL,
            stato             TEXT DEFAULT 'aperto',        -- aperto | chiuso
            is_esempio        INTEGER DEFAULT 0,
            file_eliminati_at TIMESTAMP,
            ultima_attivita   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS progetto_documenti (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            progetto_id        INTEGER NOT NULL,
            nome_file          TEXT NOT NULL,
            estensione         TEXT,
            dimensione         INTEGER DEFAULT 0,
            file_path          TEXT,
            pagine             INTEGER,
            ha_testo           INTEGER,
            tipo_ai            TEXT,                 -- tipo riconosciuto dall'AI
            tipo_csp           TEXT,                 -- correzione del CSP (prevale)
            priorita           INTEGER DEFAULT 99,
            stato              TEXT DEFAULT 'da_classificare',
            -- da_classificare | in_coda | in_elaborazione | completato | in_attesa
            -- | mappatura_richiesta | errore | non_supportato
            motivo_attesa      TEXT,                 -- budget | limite_giornaliero
            errore             TEXT,
            n_blocchi          INTEGER DEFAULT 0,
            blocchi_completati INTEGER DEFAULT 0,
            elenco_id          INTEGER,              -- se il documento è un elenco prezzi
            costo_eur          REAL DEFAULT 0,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_pdoc_prog ON progetto_documenti(progetto_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pdoc_stato ON progetto_documenti(stato, priorita)")
    c.execute("""
        CREATE TABLE IF NOT EXISTS progetto_estrazioni (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            documento_id INTEGER NOT NULL,
            blocco       INTEGER NOT NULL,
            pagine_da    INTEGER,
            pagine_a     INTEGER,
            dati_json    TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(documento_id, blocco)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS elenchi_prezzi (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT,                       -- NULL per gli elenchi di sistema
            livello      TEXT NOT NULL,              -- progetto | account | sistema
            progetto_id  INTEGER,
            nome         TEXT NOT NULL,
            nome_file    TEXT,
            file_path    TEXT,                       -- conservato solo finché serve la mappatura
            stato        TEXT DEFAULT 'pronto',      -- pronto | mappatura_richiesta | errore
            anteprima    TEXT,                       -- JSON per la schermata di mappatura
            errore       TEXT,
            n_voci       INTEGER DEFAULT 0,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS elenchi_prezzi_voci (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            elenco_id       INTEGER NOT NULL,
            codice          TEXT,
            descrizione     TEXT,
            um              TEXT,
            prezzo          REAL,
            perc_manodopera REAL,
            capitolo        TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_voci_elenco ON elenchi_prezzi_voci(elenco_id)")

    # ── Blocco 3: tappe del PSC e questionario del sopralluogo ──────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS progetto_tappe (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            progetto_id       INTEGER NOT NULL,
            numero            INTEGER NOT NULL,              -- 1..12
            stato             TEXT DEFAULT 'da_generare',
            -- da_generare | in_coda | in_generazione | generata | errore
            contenuto_json    TEXT,                          -- versione corrente (AI o CSP)
            modificata_a_mano INTEGER DEFAULT 0,             -- esclusa dalla cascata
            da_ricontrollare  INTEGER DEFAULT 0,             -- saltata dalla cascata: il CSP deve verificarla
            da_aggiornare     INTEGER DEFAULT 0,             -- una tappa precedente è cambiata ma questa non è stata rigenerata
            nota_csp          TEXT,                          -- nota per la prossima (ri)generazione
            errore            TEXT,
            costo_eur         REAL DEFAULT 0,
            generata_at       TIMESTAMP,
            updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(progetto_id, numero)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS progetto_domande (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            progetto_id  INTEGER NOT NULL,
            tappa        INTEGER NOT NULL,
            origine      TEXT DEFAULT 'domanda',             -- domanda | da_verificare
            testo        TEXT NOT NULL,
            risposta     TEXT,
            stato        TEXT DEFAULT 'aperta',              -- aperta | risposta | applicata
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            risposta_at  TIMESTAMP
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_domande_prog ON progetto_domande(progetto_id, tappa)")
    _aggiungi_colonna(c, "progetti", "data_inizio_lavori", "TEXT")
    _aggiungi_colonna(c, "progetti", "bozza_stato", "TEXT")          # in_corso | completata | interrotta
    _aggiungi_colonna(c, "progetti", "bozza_messaggio", "TEXT")

    # ── Blocco 4: costi della sicurezza e uomini-giorno ─────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS progetto_costi (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            progetto_id      INTEGER NOT NULL,
            chiave           TEXT NOT NULL,              -- misura normalizzata (identifica la riga tra le rigenerazioni)
            ordine           INTEGER DEFAULT 0,
            attiva           INTEGER DEFAULT 1,          -- 0 = misura non più presente nella tappa 11
            categoria        TEXT,
            misura           TEXT,
            um_misura        TEXT,
            quantita_tappa   REAL,                       -- quantità proposta dalla tappa 11
            quantita         REAL,                       -- quantità usata nel calcolo (modificabile)
            quantita_csp     INTEGER DEFAULT 0,
            stato            TEXT DEFAULT 'da_abbinare', -- da_abbinare | abbinata | da_definire | manuale
            livello          TEXT,                       -- progetto | account | sistema | manuale
            elenco_id        INTEGER,
            elenco_nome      TEXT,
            codice           TEXT,
            descrizione_voce TEXT,
            um_voce          TEXT,
            prezzo           REAL,
            nota             TEXT,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(progetto_id, chiave)
        )
    """)
    _aggiungi_colonna(c, "progetti", "costi_da_abbinare", "INTEGER DEFAULT 0")
    _aggiungi_colonna(c, "progetti", "costi_messaggio", "TEXT")
    _aggiungi_colonna(c, "progetti", "importo_lavori", "REAL")
    _aggiungi_colonna(c, "progetti", "incidenza_manodopera", "REAL")      # percentuale indicata dal CSP
    _aggiungi_colonna(c, "progetti", "costo_giornaliero", "REAL")         # euro/giorno per lavoratore
    _aggiungi_colonna(c, "progetti", "ug_scelta", "TEXT")                 # cronoprogramma | incidenza

    # ── Blocco 5: presidi di emergenza e schemi di cantiere ─────────────────────
    _aggiungi_colonna(c, "progetti", "indirizzo_cantiere", "TEXT")
    c.execute("""
        CREATE TABLE IF NOT EXISTS progetto_presidi (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            progetto_id  INTEGER NOT NULL,
            ordine       INTEGER DEFAULT 0,
            tipo         TEXT,                    -- pronto_soccorso | vigili_fuoco | carabinieri | polizia_locale
                                                  -- | guardia_medica | farmacia | numero_emergenza | altro
            nome         TEXT,
            indirizzo    TEXT,
            telefono     TEXT,
            distanza     TEXT,
            percorso     TEXT,
            fonte_url    TEXT,
            fonte_titolo TEXT,
            confermato   INTEGER DEFAULT 0,
            manuale      INTEGER DEFAULT 0,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS progetto_schemi (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            progetto_id   INTEGER NOT NULL,
            nome          TEXT NOT NULL,
            includi_psc   INTEGER DEFAULT 0,
            sfondo_path   TEXT,                   -- PNG conservato finché esiste il progetto
            sfondo_w      INTEGER,
            sfondo_h      INTEGER,
            sfondo_origine TEXT,
            scala_json    TEXT,                   -- {"m_per_px", "punti", "distanza_m"}
            elementi_json TEXT DEFAULT '[]',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def cartella_progetto(progetto_id: int) -> str:
    base = os.path.dirname(os.path.abspath(DB_PATH))
    path = os.path.join(base, "progetti", str(progetto_id))
    os.makedirs(path, exist_ok=True)
    return path


def cartella_schemi(progetto_id: int) -> str:
    """Sfondi degli schemi di cantiere: fuori dalla cartella dei documenti, così la pulizia
    dei file originali (chiusura o 30 giorni di inattività) non li cancella."""
    base = os.path.dirname(os.path.abspath(DB_PATH))
    path = os.path.join(base, "schemi", str(progetto_id))
    os.makedirs(path, exist_ok=True)
    return path


def cartella_elenchi() -> str:
    base = os.path.dirname(os.path.abspath(DB_PATH))
    path = os.path.join(base, "elenchi_prezzi")
    os.makedirs(path, exist_ok=True)
    return path


def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = get_conn()
    c = conn.cursor()
    # WAL: letture e scritture contemporanee (richieste web + worker in background)
    c.execute("PRAGMA journal_mode=WAL")

    # Tabella utenti (sostituisce DEMO_USERS)
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT UNIQUE NOT NULL,
            email           TEXT UNIQUE NOT NULL,
            nome_cognome    TEXT,
            password_hash   TEXT NOT NULL,
            max_calls_giorno INTEGER DEFAULT 20,
            is_active       INTEGER DEFAULT 1,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabella documenti
    c.execute("""
        CREATE TABLE IF NOT EXISTS documenti (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo          TEXT,
            nome_cantiere TEXT,
            contenuto     TEXT,
            form_data     TEXT,
            stato         TEXT DEFAULT 'completato',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabella sessioni
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessioni (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            documento_id  INTEGER,
            tipo_verifica TEXT,
            risposta      TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabella log utilizzo crediti
    c.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT NOT NULL,
            endpoint     TEXT NOT NULL,
            credits_used INTEGER DEFAULT 1,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # Migrazione schema: aggiunge colonne mancanti in usage_log se DB creato con schema vecchio
    _migrate_usage_log_schema(c)
    conn.commit()

    # Migrazione: importa DEMO_USERS nell'env nella tabella users (solo se tabella vuota)
    row = c.execute("SELECT COUNT(*) FROM users").fetchone()
    if row[0] == 0:
        _migrate_demo_users(c)
        conn.commit()

    # Tabella costi API (blocco 1 — tracciamento costi e tetto demo)
    c.execute("""
        CREATE TABLE IF NOT EXISTS api_costi (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            username           TEXT NOT NULL,
            endpoint           TEXT NOT NULL,
            operazione_id      TEXT,
            model              TEXT,
            input_tokens       INTEGER DEFAULT 0,
            output_tokens      INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            cache_read_tokens  INTEGER DEFAULT 0,
            costo_usd          REAL DEFAULT 0,
            costo_eur          REAL DEFAULT 0,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_api_costi_user ON api_costi(username, created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_api_costi_op ON api_costi(endpoint, operazione_id)")

    # Nuove colonne (idempotente)
    _aggiungi_colonna(c, "users", "is_admin", "INTEGER DEFAULT 0")
    _aggiungi_colonna(c, "documenti", "impresa_nome", "TEXT")
    _aggiungi_colonna(c, "documenti", "file_path", "TEXT")
    _aggiungi_colonna(c, "documenti", "username", "TEXT")

    # Anagrafica: committenti, imprese, coordinatori (tabelle mancanti dopo la riscrittura del DB)
    _crea_tabelle_anagrafica(c)

    # Tabelle progetti PSC ed elenchi prezzi (blocco 2)
    _crea_tabelle_progetti(c)

    # Amministratori: email separate da virgola in ADMIN_EMAILS
    for email in _admin_emails():
        c.execute("UPDATE users SET is_admin = 1 WHERE LOWER(email) = ? OR LOWER(username) = ?",
                  (email, email))
    conn.commit()

    conn.close()
    print("✅ Database inizializzato correttamente")

def _migrate_demo_users(cursor):
    """Importa gli utenti da DEMO_USERS env var nella tabella users."""
    import json
    raw = os.environ.get("DEMO_USERS", "[]")
    try:
        users = json.loads(raw)
        for u in users:
            username = u.get("username", "")
            password_hash = u.get("password_hash", "")
            nome = u.get("nome", username)
            max_calls = u.get("max_calls_giorno", 20)
            if username and password_hash:
                cursor.execute("""
                    INSERT OR IGNORE INTO users (username, email, nome_cognome, password_hash, max_calls_giorno)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, f"{username}@demo.local", nome, password_hash, max_calls))
        print(f"✅ Migrati {len(users)} utenti da DEMO_USERS")
    except Exception as e:
        print(f"⚠️ Migrazione DEMO_USERS fallita: {e}")

# ── Helpers utenti ─────────────────────────────────────────────────────────────
def get_user_by_username(username: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_email(email: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(username: str, email: str, nome_cognome: str, password_hash: str):
    conn = get_conn()
    try:
        admin = 1 if email.strip().lower() in _admin_emails() else 0
        conn.execute("""
            INSERT INTO users (username, email, nome_cognome, password_hash, is_admin)
            VALUES (?, ?, ?, ?, ?)
        """, (username, email, nome_cognome, password_hash, admin))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# ── Helpers crediti ────────────────────────────────────────────────────────────
def get_usage_count(username: str) -> int:
    conn = get_conn()
    today = __import__('datetime').date.today().isoformat()
    row = conn.execute("""
        SELECT COALESCE(SUM(credits_used), 0)
        FROM usage_log
        WHERE username = ? AND DATE(created_at) = ?
    """, (username, today)).fetchone()
    conn.close()
    return row[0] if row else 0

def log_usage(username: str, endpoint: str, credits: int = 1):
    conn = get_conn()
    conn.execute("""
        INSERT INTO usage_log (username, endpoint, credits_used)
        VALUES (?, ?, ?)
    """, (username, endpoint, credits))
    conn.commit()
    conn.close()

# Alias per compatibilità con i router esistenti
get_db = get_conn

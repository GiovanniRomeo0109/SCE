import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "/data/cantieri.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
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


def init_db():
    conn = get_conn()
    c = conn.cursor()

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

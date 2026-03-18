import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "/data/cantieri.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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

    # Migrazione: importa DEMO_USERS nell'env nella tabella users (solo se tabella vuota)
    row = c.execute("SELECT COUNT(*) FROM users").fetchone()
    if row[0] == 0:
        _migrate_demo_users(c)
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
        conn.execute("""
            INSERT INTO users (username, email, nome_cognome, password_hash)
            VALUES (?, ?, ?, ?)
        """, (username, email, nome_cognome, password_hash))
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
get_db = get_conn  # alias per compatibilità con i router esistenti
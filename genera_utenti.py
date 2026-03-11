"""
Script da eseguire UNA VOLTA in locale per generare il valore
della variabile d'ambiente DEMO_USERS da incollare su Railway.

Uso:
    python genera_utenti.py

Modifica la lista UTENTI prima di eseguire.
"""
import hashlib, json

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ── Definisci qui gli utenti demo ─────────────────────────────────────────────
UTENTI = [
    {
        "username": "studio_rossi",
        "password": "SCE2025!rossi",        # cambia con password sicura
        "nome": "Studio Tecnico Rossi",
        "max_calls_giorno": 20,
    },
    {
        "username": "studio_bianchi",
        "password": "SCE2025!bianchi",       # cambia con password sicura
        "nome": "Studio Ing. Bianchi",
        "max_calls_giorno": 20,
    },
    {
        "username": "admin",
        "password": "SCE_admin_2025!",       # cambia con password sicura
        "nome": "Amministratore",
        "max_calls_giorno": 100,
    },
]

# ── Genera JSON con password hashate ─────────────────────────────────────────
output = []
for u in UTENTI:
    output.append({
        "username": u["username"],
        "password_hash": hash_password(u["password"]),
        "nome": u["nome"],
        "max_calls_giorno": u["max_calls_giorno"],
    })

json_str = json.dumps(output, ensure_ascii=False)

print("=" * 70)
print("Copia questo valore come variabile d'ambiente DEMO_USERS su Railway:")
print("=" * 70)
print(json_str)
print("=" * 70)
print("\nVariabili da impostare su Railway:")
print(f"  DEMO_USERS = {json_str}")
print(f"  JWT_SECRET = <stringa casuale lunga — es. genera con: python -c \"import secrets; print(secrets.token_hex(32))\" >")
print(f"  ANTHROPIC_API_KEY = sk-ant-...")
print(f"  DB_PATH = /data/cantieri.db")
print(f"  ALLOWED_ORIGINS = https://tuo-progetto.up.railway.app")

"""
services/ai_costi.py — Tracciamento costi API e limiti demo

Tutte le chiamate a Claude passano da TrackedClient, che:
  1. calcola il costo reale di ogni risposta (token effettivi x prezzo del modello)
  2. lo registra nella tabella api_costi, raggruppato per operazione
  3. applica il tetto demo in euro (DEMO_LIMIT_EUR, default 1.00) una sola volta per account
  4. applica il limite giornaliero di chiamate (users.max_calls_giorno)
Gli amministratori (users.is_admin = 1) sono esclusi da entrambi i limiti.

Uso nei router:
    user = Depends(require_credits("verifica_psc"))   # controllo limiti a inizio operazione
    client = TrackedClient(user, "verifica_psc")      # stesso interfaccia di anthropic.Anthropic()
    client.messages.create(model=..., ...)
"""
import os
import uuid
import logging
from datetime import date

import anthropic
from fastapi import HTTPException

from database import get_conn

log = logging.getLogger("ai_costi")

# ── Parametri (modificabili da variabili d'ambiente Railway) ──────────────────
DEMO_LIMIT_EUR = float(os.environ.get("DEMO_LIMIT_EUR", "1.00"))
EUR_PER_USD    = float(os.environ.get("EUR_PER_USD", "0.92"))

# Prezzi in USD per milione di token: (input, output). Verificare sul listino Anthropic.
PREZZI_USD = {
    "claude-sonnet-4-6":         (3.00, 15.00),
    "claude-sonnet-4-5":         (3.00, 15.00),
    "claude-sonnet-4-20250514":  (3.00, 15.00),
    "claude-haiku-4-5":          (1.00, 5.00),
    "claude-opus-4":             (15.00, 75.00),
}
CACHE_WRITE_MULT = 1.25   # scrittura in cache: +25% sul prezzo di input
CACHE_READ_MULT  = 0.10   # lettura dalla cache: 10% del prezzo di input
WEB_SEARCH_USD   = 0.01   # per singola ricerca web

# Stima prudenziale in euro di un'operazione, usata prima di avviarla.
# Viene sostituita dalla media reale delle ultime operazioni quando disponibile.
STIME_DEFAULT_EUR = {
    "verifica_psc":        0.15,
    "verifica_pos":        0.15,   # per ogni POS
    "verifica_congruita":  0.15,   # per ogni POS (PSC incluso nella prima)
    "genera_contenuto":    0.06,
    "analisi_rischi":      0.15,
    "estrazione":          0.08,
}
STIMA_GENERICA_EUR = 0.10

MSG_DEMO_TERMINATA = (
    "La demo è terminata: hai utilizzato tutto il budget disponibile. "
    "Puoi continuare a consultare, modificare ed esportare tutti i risultati già prodotti."
)


# ══════════════════════════════════════════════════════════════════════════════
# Calcolo costi
# ══════════════════════════════════════════════════════════════════════════════

def _prezzi_modello(model: str):
    for prefisso, prezzi in PREZZI_USD.items():
        if model.startswith(prefisso):
            return prezzi
    log.warning(f"Modello senza prezzo in tabella: {model} — uso prezzi Sonnet")
    return PREZZI_USD["claude-sonnet-4-6"]


def calcola_costo_usd(model: str, usage) -> float:
    p_in, p_out = _prezzi_modello(model)
    inp        = getattr(usage, "input_tokens", 0) or 0
    out        = getattr(usage, "output_tokens", 0) or 0
    cache_w    = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_r    = getattr(usage, "cache_read_input_tokens", 0) or 0
    server     = getattr(usage, "server_tool_use", None)
    ricerche   = (getattr(server, "web_search_requests", 0) or 0) if server else 0
    costo = (
        inp * p_in
        + cache_w * p_in * CACHE_WRITE_MULT
        + cache_r * p_in * CACHE_READ_MULT
        + out * p_out
    ) / 1_000_000
    return costo + ricerche * WEB_SEARCH_USD


# ══════════════════════════════════════════════════════════════════════════════
# Letture dal DB
# ══════════════════════════════════════════════════════════════════════════════

def is_admin(user: dict) -> bool:
    return bool(user.get("is_admin"))


def speso_eur(username: str) -> float:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(costo_eur), 0) AS tot FROM api_costi WHERE username = ?",
            (username,),
        ).fetchone()
        return float(row["tot"] or 0)
    finally:
        conn.close()


def chiamate_oggi(username: str) -> int:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM api_costi WHERE username = ? AND DATE(created_at) = ?",
            (username, date.today().isoformat()),
        ).fetchone()
        return int(row["n"] or 0)
    finally:
        conn.close()


def stima_operazione_eur(tipo: str) -> float:
    """Media reale delle ultime 20 operazioni dello stesso tipo, altrimenti la stima di default."""
    default = STIME_DEFAULT_EUR.get(tipo, STIMA_GENERICA_EUR)
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT AVG(tot) AS media FROM (
                SELECT SUM(costo_eur) AS tot FROM api_costi
                WHERE endpoint = ? AND operazione_id IS NOT NULL
                GROUP BY operazione_id
                ORDER BY MAX(created_at) DESC
                LIMIT 20
            )
            """,
            (tipo,),
        ).fetchone()
        media = row["media"] if row else None
        return float(media) if media else default
    except Exception:
        return default
    finally:
        conn.close()


def stato_budget(user: dict) -> dict:
    """Situazione completa, usata dall'endpoint /api/auth/budget e dalla barra laterale."""
    speso = speso_eur(user["username"])
    admin = is_admin(user)
    return {
        "is_admin":        admin,
        "limite_eur":      None if admin else DEMO_LIMIT_EUR,
        "speso_eur":       round(speso, 4),
        "residuo_eur":     None if admin else round(max(DEMO_LIMIT_EUR - speso, 0), 4),
        "demo_terminata":  False if admin else speso >= DEMO_LIMIT_EUR,
        "chiamate_oggi":   chiamate_oggi(user["username"]),
        "max_chiamate_giorno": None if admin else user.get("max_calls_giorno", 20),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Controllo limiti
# ══════════════════════════════════════════════════════════════════════════════

def _errore_demo_terminata():
    raise HTTPException(
        status_code=402,
        detail={"code": "demo_terminata", "message": MSG_DEMO_TERMINATA},
    )


def assicura_budget(user: dict, stima_eur: float):
    """
    Blocca l'operazione se il budget residuo non basta a coprirne la stima,
    oppure se il limite giornaliero di chiamate è raggiunto. Gli admin passano sempre.
    """
    if is_admin(user):
        return
    speso = speso_eur(user["username"])
    if speso >= DEMO_LIMIT_EUR or speso + stima_eur > DEMO_LIMIT_EUR:
        _errore_demo_terminata()
    max_calls = user.get("max_calls_giorno", 20) or 20
    if chiamate_oggi(user["username"]) >= max_calls:
        raise HTTPException(
            status_code=429,
            detail=f"Limite giornaliero raggiunto ({max_calls} chiamate). "
                   f"Il contatore si azzera a mezzanotte.",
        )


def stima_costo_eur(model: str, input_tokens: int, output_tokens: int) -> float:
    p_in, p_out = _prezzi_modello(model)
    return (input_tokens * p_in + output_tokens * p_out) / 1_000_000 * EUR_PER_USD


def verifica_disponibilita(user: dict, stima_eur: float):
    """
    Come assicura_budget ma senza eccezioni: restituisce None se si può procedere,
    altrimenti il motivo ('budget' o 'limite_giornaliero'). Usata dal worker in background.
    """
    if is_admin(user):
        return None
    if speso_eur(user["username"]) + stima_eur > DEMO_LIMIT_EUR:
        return "budget"
    if chiamate_oggi(user["username"]) >= (user.get("max_calls_giorno", 20) or 20):
        return "limite_giornaliero"
    return None


def registra_costo(username: str, endpoint: str, operazione_id: str, model: str, usage):
    costo_usd = calcola_costo_usd(model, usage)
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO api_costi
                (username, endpoint, operazione_id, model,
                 input_tokens, output_tokens, cache_write_tokens, cache_read_tokens,
                 costo_usd, costo_eur)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username, endpoint, operazione_id, model,
                getattr(usage, "input_tokens", 0) or 0,
                getattr(usage, "output_tokens", 0) or 0,
                getattr(usage, "cache_creation_input_tokens", 0) or 0,
                getattr(usage, "cache_read_input_tokens", 0) or 0,
                costo_usd,
                costo_usd * EUR_PER_USD,
            ),
        )
        conn.commit()
    except Exception as e:
        # Il tracciamento non deve mai far fallire la risposta all'utente
        log.error(f"Registrazione costo fallita: {e}")
    finally:
        conn.close()
    return costo_usd


# ══════════════════════════════════════════════════════════════════════════════
# Client tracciato — stessa interfaccia di anthropic.Anthropic().messages.create
# ══════════════════════════════════════════════════════════════════════════════

class _TrackedMessages:
    def __init__(self, parent: "TrackedClient"):
        self._p = parent

    def create(self, **kwargs):
        risposta = self._p._client.messages.create(**kwargs)
        registra_costo(
            self._p.user["username"], self._p.endpoint, self._p.operazione_id,
            kwargs.get("model", ""), risposta.usage,
        )
        return risposta


class TrackedClient:
    """
    Un'istanza = un'operazione (es. una verifica). Tutte le chiamate fatte con la
    stessa istanza condividono operazione_id, così la media dei costi per tipo di
    operazione è calcolata correttamente.

    Le chiamate dentro un'operazione già autorizzata non vengono bloccate:
    il controllo si fa all'inizio (require_credits / assicura_budget), così
    un'operazione non si interrompe mai a metà.
    """
    def __init__(self, user: dict, endpoint: str):
        self.user = user
        self.endpoint = endpoint
        self.operazione_id = uuid.uuid4().hex
        self._client = anthropic.Anthropic()
        self.messages = _TrackedMessages(self)

    def assicura_budget(self, stima_eur: float):
        assicura_budget(self.user, stima_eur)

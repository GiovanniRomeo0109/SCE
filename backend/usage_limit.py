"""
usage_limit.py — Dependency FastAPI per il controllo dei limiti a inizio operazione.

Il conteggio reale dei costi e delle chiamate è fatto da services/ai_costi.py
(tabella api_costi). Qui si verifica solo, PRIMA di avviare un'operazione, che:
  - il budget demo residuo copra la stima dell'operazione
  - il limite giornaliero di chiamate non sia raggiunto
Gli amministratori sono esclusi.
"""
from fastapi import Depends
from auth import get_current_user
from services.ai_costi import assicura_budget, stima_operazione_eur


def check_and_log(user: dict, tipo_operazione: str):
    """Compatibilità con il codice esistente: controlla i limiti (non registra più nulla qui)."""
    assicura_budget(user, stima_operazione_eur(tipo_operazione))


def require_credits(tipo: str):
    """Uso: user: dict = Depends(require_credits("verifica_psc"))"""
    def _check(user: dict = Depends(get_current_user)):
        check_and_log(user, tipo)
        return user
    return _check

import time, logging
from .cost import calculate_cost
from .burn import calculate_burn_rate
from .killswitch import enforce_burn_rate, enforce_daily_budget
from .alerts import alert_killswitch_triggered, alert_daily_budget_exceeded
from .storage import storage
from .providers import route_call, NormalizedResponse
from .pricing import FALLBACK_CHAIN
from .exceptions import BudgetExceededException, DailyBudgetExceededException, AllModelsExhaustedException
from .config import (MAX_BURN_RATE_PER_MIN,BURN_RATE_WINDOW_SECONDS,USER_BUDGETS, DEFAULT_DAILY_BUDGET)
logger = logging.getLogger(__name__)

def _check_limits(user_id: str) -> None:
    recent = storage.get_recent(user_id, BURN_RATE_WINDOW_SECONDS)
    br = calculate_burn_rate(recent)
    try:
        enforce_burn_rate(user_id, br, MAX_BURN_RATE_PER_MIN)
    except BudgetExceededException:
        alert_killswitch_triggered(user_id, br, MAX_BURN_RATE_PER_MIN)
        raise

    total = storage.get_total_today(user_id)
    limit = USER_BUDGETS.get(user_id, DEFAULT_DAILY_BUDGET)
    try:
        enforce_daily_budget(user_id, total)
    except DailyBudgetExceededException:
        alert_daily_budget_exceeded(user_id, total, limit)   
        raise

def call_llm(user_id: str, model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
    _check_limits(user_id)
    resp = route_call(model, messages, temperature, max_tokens)   # ← updated call
    cost = calculate_cost(model, resp.input_tokens, resp.output_tokens)
    storage.save({"user_id": user_id, "model": model, "input_tokens": resp.input_tokens, "output_tokens": resp.output_tokens, "cost": cost, "timestamp": time.time()})
    return resp

def call_llm_with_fallback(user_id: str, messages: list, preferred_model: str = "gpt-4o", temperature: float = 0.7, max_tokens: int = 1024) -> NormalizedResponse:
    start = FALLBACK_CHAIN.index(preferred_model) if preferred_model in FALLBACK_CHAIN else 0
    for model in FALLBACK_CHAIN[start:]:
        try:
            return call_llm(user_id, model, messages, temperature, max_tokens)   # ← pass down
        except (BudgetExceededException, DailyBudgetExceededException):
            continue
    raise AllModelsExhaustedException("All models exhausted")

'''
def safe_call(user_id: str, model: str, messages: list, retries: int = MAX_RETRIES) -> NormalizedResponse:
    for _ in range(retries):
        try: return call_llm(user_id, model, messages)
        except (BudgetExceededException, DailyBudgetExceededException): raise
        except Exception: pass
    raise Exception("Retries exceeded")
    '''
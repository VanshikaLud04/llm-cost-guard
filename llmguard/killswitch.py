import logging
from .exceptions import BudgetExceededException, DailyBudgetExceededException
from .config import settings
logger = logging.getLogger(__name__)

def enforce_burn_rate(user_id: str, burn_rate: float, max_per_min: float) -> None:
    if burn_rate > max_per_min:
        raise BudgetExceededException(f"[killswitch] Burn rate exceeded for '{user_id}': ${burn_rate:.6f} > limit ${max_per_min:.6f}/min")

def enforce_daily_budget(user_id: str, total_spent: float) -> None:
    limit = settings.USER_BUDGETS.get(user_id, settings.DEFAULT_DAILY_BUDGET)
    if total_spent >= limit:
        raise DailyBudgetExceededException(f"[killswitch] Daily budget exceeded for '{user_id}': ${total_spent:.6f} >= limit ${limit:.6f}")
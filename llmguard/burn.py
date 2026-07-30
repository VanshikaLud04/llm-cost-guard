from .config import settings

def calculate_burn_rate(records: list[tuple]) -> float:
    """Returns true burn rate in $/minute (cost in last 60 seconds)."""
    if not records:
        return 0.0
    
    total_cost = sum(r[0] for r in records)
    return round(total_cost / (settings.BURN_RATE_WINDOW_SECONDS / 60), 8)
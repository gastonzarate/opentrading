"""
Dynamic cadence: the agent decides when it should run again, the code enforces
sane bounds. The agent ends its response with a machine-readable directive:

    NEXT_RUN_MINUTES: <int>

This replaces a dumb fixed interval that re-ran the identical prompt regardless of
state. The agent acts as its own controller: run sooner when managing an open
position or waiting on an imminent event, later when flat with no setups.
"""
import re

from apps.genflows.trading_futures.strategy_config import STRATEGY

_NEXT_RUN_RE = re.compile(r"NEXT_RUN_MINUTES:\s*(\d+)", re.IGNORECASE)


def parse_next_run_minutes(text: str):
    """Extract the agent's requested next-run interval in minutes, or None."""
    if not text:
        return None
    match = _NEXT_RUN_RE.search(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (ValueError, TypeError):
        return None


def decide_next_run_minutes(parsed, has_open_positions: bool, config=STRATEGY) -> int:
    """
    Turn the agent's (possibly missing/out-of-range) request into a bounded delay.
    While a position is open the ceiling is tighter so the bot never goes dark on it.
    """
    value = parsed if parsed is not None else config.default_run_minutes
    ceiling = config.max_run_minutes
    if has_open_positions:
        ceiling = min(ceiling, config.max_run_minutes_with_position)
    return max(config.min_run_minutes, min(value, ceiling))

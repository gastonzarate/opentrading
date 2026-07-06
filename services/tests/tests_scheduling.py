"""
Tests for the dynamic-cadence parse/clamp logic (pure).
"""
from apps.genflows.trading_futures.scheduling import decide_next_run_minutes, parse_next_run_minutes
from apps.genflows.trading_futures.strategy_config import STRATEGY


def test_parse_extracts_minutes():
    assert parse_next_run_minutes("blah\nNEXT_RUN_MINUTES: 30\nmore") == 30
    assert parse_next_run_minutes("next_run_minutes:  5") == 5


def test_parse_returns_none_when_absent_or_bad():
    assert parse_next_run_minutes("no directive here") is None
    assert parse_next_run_minutes("") is None
    assert parse_next_run_minutes(None) is None


def test_decide_passes_through_within_bounds():
    assert decide_next_run_minutes(20, has_open_positions=False) == 20


def test_decide_clamps_to_min_and_max():
    assert decide_next_run_minutes(0, has_open_positions=False) == STRATEGY.min_run_minutes
    assert decide_next_run_minutes(9999, has_open_positions=False) == STRATEGY.max_run_minutes


def test_decide_tightens_ceiling_when_position_open():
    # a long interval is capped tighter while a position is open
    assert decide_next_run_minutes(60, has_open_positions=True) == STRATEGY.max_run_minutes_with_position


def test_decide_uses_default_when_missing():
    assert decide_next_run_minutes(None, has_open_positions=False) == STRATEGY.default_run_minutes

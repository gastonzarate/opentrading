"""
Tests for BacktestService — focused on the datetime handling that breaks under
pandas 3.0 (audit follow-up). Uses a mocked binance client, no network.
"""
import time
from unittest.mock import MagicMock

import pandas as pd

from services.backtest_service import BacktestService
from services.binance_client import BinanceClient


def _recent_klines(n=180):
    """Synthetic hourly klines ending ~now, in Binance kline format."""
    now_ms = int(time.time() * 1000)
    hour = 3_600_000
    rows = []
    price = 100.0
    for i in range(n):
        ts = now_ms - (n - 1 - i) * hour
        price *= 1 + (0.004 if i % 2 else -0.0035)
        rows.append([ts, price, price * 1.01, price * 0.99, price, 1000 + i, 0, 0, 0, 0, 0, 0])
    return rows


def _service():
    raw = MagicMock()
    raw.get_klines.return_value = _recent_klines()
    return BacktestService(BinanceClient(client=raw))


def test_load_historical_data_retains_recent_rows():
    bt = _service()
    df = bt._load_historical_data("BTC", lookback_days=7)
    # The tz-aware/naive cutoff comparison must not blow up and drop everything.
    assert not df.empty
    assert len(df) > 50


def test_backtest_strategy_simulates_trades_on_matching_conditions():
    bt = _service()
    df = bt._load_historical_data("BTC", lookback_days=7)
    # Anchor current conditions to a real historical row so matches are found.
    ref = df.iloc[len(df) // 2]
    conditions = {
        "rsi": float(ref["rsi_7"]),
        "macd": float(ref["macd"]),
        "price": float(ref["close"]),
        "ema_9": float(ref["ema_9"]),
        "funding_rate": 0.0,
    }
    result = bt.backtest_strategy("BTC", "LONG", conditions, lookback_days=7)

    assert "error" not in result
    assert result["similar_setups_found"] > 0
    assert result["trades_simulated"] >= 1


def test_apply_costs_subtracts_round_trip():
    bt = BacktestService(MagicMock())
    cost = BacktestService.ROUND_TRIP_COST_PCT
    assert cost > 0
    assert bt._apply_costs(4.0) == 4.0 - cost
    assert bt._apply_costs(-2.0) == -2.0 - cost


def test_find_similar_conditions_dedupes_overlapping_setups():
    n = 60
    df = pd.DataFrame({
        "close": [100.0] * n,
        "rsi_7": [50.0] * n,
        "macd": [1.0] * n,
        "atr_14": [100.0] * n,
        "price_above_ema9": [True] * n,
        "datetime": pd.date_range("2026-01-01", periods=n, freq="h"),
    })
    conditions = {"rsi": 50.0, "macd": 1.0, "price": 110.0, "ema_9": 100.0, "funding_rate": 0.0, "atr": 100.0}
    similar = bt_find(df, conditions)
    idxs = [s["index"] for s in similar]
    # Every candidate row matches; without dedup that's ~36. Cooldown must collapse them.
    assert len(idxs) < 12
    for a, b in zip(idxs, idxs[1:]):
        assert b - a >= BacktestService.MIN_BARS_BETWEEN_ENTRIES


def bt_find(df, conditions):
    return BacktestService(MagicMock())._find_similar_conditions(df, conditions)


def test_metrics_flags_insufficient_sample():
    bt = BacktestService(MagicMock())
    trades = [{"pnl_pct": 1.0, "outcome": "TAKE_PROFIT", "holding_hours": 2}]
    metrics = bt._calculate_metrics(trades, similar_conditions=[{}], direction="LONG")
    assert metrics["sufficient_sample"] is False

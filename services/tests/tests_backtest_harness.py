"""
Tests for the offline backtest harness (pure, no network).
"""
import pandas as pd

from services.backtest_harness import BacktestParams, RegimeBacktester


def _bt():
    return RegimeBacktester()


def _row(**kw):
    base = {"adx": 30, "close": 100, "ema_9": 100, "ema_21": 100, "macd": 0, "macd_signal": 0, "rsi_7": 50}
    base.update(kw)
    return pd.Series(base)


# --- regime entry rules ----------------------------------------------------

def test_trend_regime_long_and_short():
    bt = _bt()
    assert bt.entry_signal(_row(adx=30, close=110, ema_9=100, ema_21=95, macd=1, macd_signal=0.5)) == "LONG"
    assert bt.entry_signal(_row(adx=30, close=90, ema_9=100, ema_21=105, macd=-1, macd_signal=-0.5)) == "SHORT"


def test_trend_regime_no_signal_when_mixed():
    bt = _bt()
    # price above EMAs but MACD below signal -> not a clean momentum long
    assert bt.entry_signal(_row(adx=30, close=110, ema_9=100, ema_21=95, macd=-1, macd_signal=0.5)) is None


def test_range_regime_mean_reversion():
    bt = _bt()
    assert bt.entry_signal(_row(adx=15, rsi_7=25)) == "LONG"
    assert bt.entry_signal(_row(adx=15, rsi_7=75)) == "SHORT"


def test_undefined_regime_no_trade():
    bt = _bt()
    assert bt.entry_signal(_row(adx=22, close=110, ema_9=100, ema_21=95, macd=1, macd_signal=0.5)) is None


# --- single-trade simulation ----------------------------------------------

def _trade_df(entry=100.0, atr=10.0, next_high=None, next_low=None):
    dt = pd.date_range("2026-01-01", periods=3, freq="h")
    return pd.DataFrame({
        "close": [entry, entry, entry],
        "high": [entry, next_high if next_high is not None else entry, entry],
        "low": [entry, next_low if next_low is not None else entry, entry],
        "atr_14": [atr, atr, atr],
        "datetime": dt,
    })


def test_simulate_long_hits_take_profit():
    bt = _bt()
    # stop_dist=15, tp_dist=30 -> tp=130; next bar high 131 triggers TP
    df = _trade_df(entry=100, atr=10, next_high=131)
    t = bt.simulate_trade(df, 0, "LONG")
    assert t["exit"] == 130
    assert t["r_multiple"] > 0


def test_trailing_stop_locks_in_profit():
    # entry 100, atr 10, trail 3xATR=30. Bar1 spikes to 150 -> stop trails to 120.
    # Bar2 pulls back to 118 -> exit at the trailed stop 120 (profit locked).
    dt = pd.date_range("2026-01-01", periods=3, freq="h")
    df = pd.DataFrame({
        "close": [100, 150, 118],
        "high": [100, 150, 130],
        "low": [100, 100, 118],
        "atr_14": [10, 10, 10],
        "datetime": dt,
    })
    bt = RegimeBacktester(BacktestParams(exit_mode="trailing", trail_atr_mult=3.0, atr_stop_mult=1.5))
    t = bt.simulate_trade(df, 0, "LONG")
    assert t["exit"] == 120
    assert t["r_multiple"] > 0


def test_simulate_long_hits_stop():
    bt = _bt()
    # stop=85; next bar low 80 triggers stop
    df = _trade_df(entry=100, atr=10, next_low=80)
    t = bt.simulate_trade(df, 0, "LONG")
    assert t["exit"] == 85
    assert t["r_multiple"] < 0


def test_costs_reduce_r_multiple():
    df = _trade_df(entry=100, atr=10, next_high=131)
    no_cost = RegimeBacktester(BacktestParams(fee_pct_per_side=0, slippage_pct_per_side=0, funding_pct_per_8h=0))
    with_cost = RegimeBacktester()
    assert with_cost.simulate_trade(df, 0, "LONG")["r_multiple"] < no_cost.simulate_trade(df, 0, "LONG")["r_multiple"]


# --- full run --------------------------------------------------------------

def test_run_returns_metrics_and_equity_curve():
    n = 300
    price = 100.0
    rows = []
    dt = pd.date_range("2026-01-01", periods=n, freq="h")
    for i in range(n):
        price *= 1 + (0.01 if (i // 20) % 2 == 0 else -0.008)  # alternating trends
        rows.append({"open": price, "high": price * 1.02, "low": price * 0.98, "close": price,
                     "volume": 1000, "datetime": dt[i]})
    df = pd.DataFrame(rows)
    result = _bt().run(df)
    assert "metrics" in result and "equity_curve" in result and isinstance(result["trades"], list)
    assert len(result["equity_curve"]) == len(result["trades"]) + 1

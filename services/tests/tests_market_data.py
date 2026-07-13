"""
Tests for the market-data indicators added in phase 2 so the prompt's signals
are actually computable: MACD signal line and ADX (for regime). Mocked, no net.
"""
from unittest.mock import MagicMock

from services.binance_client import BinanceClient


def _df(n=120):
    raw = MagicMock()
    rows = []
    price = 100.0
    for i in range(n):
        price *= 1 + (0.006 if i % 3 else -0.005)
        rows.append([i * 3_600_000, price, price * 1.01, price * 0.99, price, 1000 + i, 0, 0, 0, 0, 0, 0])
    raw.futures_klines.return_value = rows
    c = BinanceClient(client=raw)
    return c, c._get_klines("BTCUSDT", "1h", n)


def test_calculate_indicators_adds_macd_signal_and_adx():
    c, df = _df()
    out = c._calculate_indicators(df)
    # MACD signal line is required to evaluate MACD/signal crossovers.
    assert "macd_signal" in out.columns
    # ADX is required for the regime filter (momentum vs mean-reversion).
    assert "adx" in out.columns
    # both should produce finite values near the end of the series
    assert out["macd_signal"].notna().iloc[-1]
    assert out["adx"].notna().iloc[-1]


def _metrics_client():
    raw = MagicMock()
    raw.futures_funding_rate.return_value = [{"fundingRate": "0.00010000"}]
    return BinanceClient(client=raw), raw


def test_open_interest_uses_history_when_available():
    c, raw = _metrics_client()
    raw.futures_open_interest_hist.return_value = [
        {"sumOpenInterest": "100"},
        {"sumOpenInterest": "300"},
    ]
    m = c._get_futures_metrics("BTCUSDT")
    assert m["oi_latest"] == 300.0
    assert m["oi_average"] == 200.0  # (100 + 300) / 2
    assert m["funding_rate"] == 0.01  # 0.0001 * 100


def test_open_interest_falls_back_to_snapshot_on_testnet():
    """History endpoint errors on the demo -> snapshot fallback, no crash, real OI."""
    c, raw = _metrics_client()
    raw.futures_open_interest_hist.side_effect = Exception("Invalid Response: ok")
    raw.futures_open_interest.return_value = {"openInterest": "323872726.9327"}
    m = c._get_futures_metrics("BTCUSDT")
    assert m["oi_latest"] == 323872726.9327
    assert m["oi_average"] == 323872726.9327  # no history -> latest == average
    assert m["funding_rate"] == 0.01


def test_open_interest_defaults_to_zero_when_both_endpoints_fail():
    c, raw = _metrics_client()
    raw.futures_open_interest_hist.side_effect = Exception("nope")
    raw.futures_open_interest.side_effect = Exception("nope")
    m = c._get_futures_metrics("BTCUSDT")
    assert m["oi_latest"] == 0
    assert m["oi_average"] == 0

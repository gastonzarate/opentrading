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

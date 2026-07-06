"""
Live integration tests against the Binance USDⓈ-M **demo** (fake money).

These hit the real demo API (demo-fapi.binance.com) to catch breakage the mocked
unit tests can't: Binance API changes, dependency upgrades, precision/param
rejections, the closePosition->algoId behavior, etc.

Opt-in: only run when RUN_DEMO_INTEGRATION=1 and demo keys are present. They are
self-cleaning (always flatten + cancel). They deliberately avoid the aggregate
account/balance endpoints, which can return -1109 on a demo whose COIN-M side is
in a broken state; the USDⓈ-M order endpoints are what the bot uses.
"""
import math
import os

import pytest

from apps.genflows.trading_futures.macro_tools import MacroTools
from apps.genflows.trading_futures.strategy_config import REGIME_RANGE, REGIME_TREND, REGIME_UNDEFINED
from services.binance_client import BinanceClient

_ENABLED = os.getenv("RUN_DEMO_INTEGRATION") == "1" and bool(os.getenv("BINANCE_DEMO_API_KEY"))
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _ENABLED, reason="set RUN_DEMO_INTEGRATION=1 and BINANCE_DEMO_API_KEY to run"),
]

REGIMES = (REGIME_TREND, REGIME_RANGE, REGIME_UNDEFINED)


@pytest.fixture
def demo():
    # No balance-dependent caps: this demo account's balance endpoint returns -1109.
    return BinanceClient(testnet=True, max_leverage=5)


def test_mark_price_and_filters(demo):
    assert demo.get_mark_price("BTC") > 0
    filt = demo._get_symbol_filters("BTCUSDT")
    assert filt["step_size"] and filt["tick_size"]


def test_market_data_and_regime(demo):
    # Uses futures klines now, so it works on the demo too.
    md = demo.get_market_data("BTC")
    assert md["current_price"] > 0
    assert md["regime"] in REGIMES
    assert "macd_signal_series" in md and "current_adx" in md
    assert demo.get_regime("BTC") in REGIMES


def test_economic_calendar_reachable():
    result = MacroTools()._economic_calendar(hours_ahead=168)
    assert "error" not in result
    assert "events" in result


def test_leverage_cap_blocks_over_limit(demo):
    mark = demo.get_mark_price("BTC")
    res = demo.open_long_position("BTC", quantity=0.002, stop_loss_price=round(mark * 0.98, 1), leverage=20)
    assert res.get("blocked") is True


def test_min_notional_blocks_tiny_order(demo):
    mark = demo.get_mark_price("BTC")
    res = demo.open_long_position("BTC", quantity=0.0001, stop_loss_price=round(mark * 0.98, 1), leverage=3)
    assert res.get("blocked") is True


def test_order_lifecycle_open_sl_tp_close(demo):
    """The real thing: open a long with reduce-only SL+TP, then flatten + cancel."""
    mark = demo.get_mark_price("BTC")
    step = 0.001
    qty = max(0.002, math.ceil((150 / mark) / step) * step)  # ~>=150 notional, above min
    sl = round(mark * 0.98, 1)
    tp = round(mark * 1.04, 1)

    res = demo.open_long_position("BTC", quantity=qty, stop_loss_price=sl, take_profit_price=tp, leverage=3)
    try:
        assert res.get("main_order_id"), f"no main order: {res}"
        assert res.get("stop_loss_order_id"), f"no stop loss id: {res}"      # orderId OR algoId
        assert res.get("take_profit_order_id"), f"no take profit id: {res}"
    finally:
        # Always leave the account flat and order-free.
        try:
            demo.client.futures_create_order(
                symbol="BTCUSDT", side="SELL", type="MARKET", quantity=qty, reduceOnly=True
            )
        except Exception:
            pass
        try:
            demo.client.futures_cancel_all_open_orders(symbol="BTCUSDT")
        except Exception:
            pass

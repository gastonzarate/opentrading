"""
Tests for the Binance event filter + debounce (pure, no websocket).
"""
from apps.tradings.binance_events import EventDebouncer, should_wake_on_event


def _order_evt(status, otype="STOP_MARKET", side="SELL", symbol="BTCUSDT"):
    return {"e": "ORDER_TRADE_UPDATE", "o": {"s": symbol, "S": side, "o": otype, "X": status, "x": "TRADE"}}


def test_wakes_on_stop_loss_fill():
    assert should_wake_on_event(_order_evt("FILLED", otype="STOP_MARKET")) is True


def test_wakes_on_take_profit_and_entry_fills():
    assert should_wake_on_event(_order_evt("FILLED", otype="TAKE_PROFIT_MARKET", side="BUY")) is True
    assert should_wake_on_event(_order_evt("PARTIALLY_FILLED", otype="MARKET", side="BUY")) is True


def test_does_not_wake_on_new_or_canceled_orders():
    assert should_wake_on_event(_order_evt("NEW")) is False
    assert should_wake_on_event(_order_evt("CANCELED")) is False


def test_does_not_wake_on_non_order_events():
    assert should_wake_on_event({"e": "ACCOUNT_UPDATE", "a": {}}) is False
    assert should_wake_on_event({}) is False
    assert should_wake_on_event(None) is False


def test_debouncer_allows_first_then_blocks_within_window():
    d = EventDebouncer(min_seconds=10)
    assert d.should_fire(1000.0) is True     # first always fires
    assert d.should_fire(1005.0) is False    # within 10s window -> blocked
    assert d.should_fire(1011.0) is True     # window elapsed -> fires again

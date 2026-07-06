"""
Safety-focused unit tests for BinanceClient (audit fixes #1-#5, #18).

These tests use a mocked binance Client injected into BinanceClient, so they
never touch a real account or the network.
"""
from unittest.mock import MagicMock

import pytest
from binance.exceptions import BinanceAPIException

from services.binance_client import BinanceClient


# --- helpers ---------------------------------------------------------------

def _api_exc(msg="boom"):
    """Build a BinanceAPIException without needing a real HTTP response."""
    resp = MagicMock()
    resp.text = '{"code": -1, "msg": "%s"}' % msg
    resp.status_code = 400
    return BinanceAPIException(resp, 400, resp.text)


def make_client(**overrides):
    """BinanceClient with a fully mocked underlying binance Client."""
    raw = MagicMock()

    # Sensible defaults for the exchange-info / filters lookups.
    raw.futures_exchange_info.return_value = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "contractType": "PERPETUAL",
                "status": "TRADING",
                "pricePrecision": 1,
                "quantityPrecision": 3,
                "filters": [
                    {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
                    {"filterType": "MIN_NOTIONAL", "notional": "100"},
                ],
            }
        ]
    }
    # main order fills fine by default
    raw.futures_create_order.return_value = {"orderId": 111, "status": "NEW"}
    raw.futures_mark_price.return_value = {"markPrice": "100000"}
    raw.futures_change_leverage.return_value = {"leverage": 5}
    raw.futures_change_margin_type.return_value = {"code": 200, "msg": "success"}
    raw.futures_position_information.return_value = [
        {"symbol": "BTCUSDT", "positionAmt": "0.002"}
    ]

    for k, v in overrides.items():
        setattr(raw, k, v)

    return BinanceClient(client=raw), raw


# --- Fix #5: leverage abort + isolated margin ------------------------------

def test_open_long_aborts_when_leverage_fails():
    client, raw = make_client()
    raw.futures_change_leverage.side_effect = _api_exc("leverage fail")

    result = client.open_long_position(
        currency="BTC", quantity=0.002, stop_loss_price=98000, leverage=5
    )

    assert result.get("error")
    # Must NOT have placed any order if leverage could not be set.
    raw.futures_create_order.assert_not_called()


def test_open_long_sets_isolated_margin_before_ordering():
    client, raw = make_client()
    client.open_long_position(
        currency="BTC", quantity=0.002, stop_loss_price=98000, leverage=5
    )
    raw.futures_change_margin_type.assert_called_once()
    _, kwargs = raw.futures_change_margin_type.call_args
    assert kwargs.get("marginType") == "ISOLATED"


# --- Fix #2: SL/TP must be reduce-only (closePosition) ---------------------

def test_stop_loss_is_close_position_only():
    client, raw = make_client()
    client.open_long_position(
        currency="BTC", quantity=0.002, stop_loss_price=98000,
        take_profit_price=104000, leverage=5,
    )
    stop_calls = [
        c for c in raw.futures_create_order.call_args_list
        if c.kwargs.get("type") == "STOP_MARKET"
    ]
    assert stop_calls, "no STOP_MARKET order placed"
    for c in stop_calls:
        assert c.kwargs.get("closePosition") is True
        # closePosition orders must not carry an explicit quantity
        assert "quantity" not in c.kwargs


def test_take_profit_is_close_position_only():
    client, raw = make_client()
    client.open_long_position(
        currency="BTC", quantity=0.002, stop_loss_price=98000,
        take_profit_price=104000, leverage=5,
    )
    tp_calls = [
        c for c in raw.futures_create_order.call_args_list
        if c.kwargs.get("type") == "TAKE_PROFIT_MARKET"
    ]
    assert tp_calls, "no TAKE_PROFIT_MARKET order placed"
    for c in tp_calls:
        assert c.kwargs.get("closePosition") is True


# --- Fix #1: no naked position if SL fails ---------------------------------

def test_naked_position_rolled_back_when_stop_loss_fails():
    client, raw = make_client()

    calls = {"n": 0}

    def create_order(**kwargs):
        calls["n"] += 1
        # main market entry succeeds; the STOP_MARKET fails
        if kwargs.get("type") == "STOP_MARKET":
            raise _api_exc("stop rejected")
        return {"orderId": 111, "status": "NEW"}

    raw.futures_create_order.side_effect = create_order

    result = client.open_long_position(
        currency="BTC", quantity=0.002, stop_loss_price=98000, leverage=5
    )

    assert result.get("error")
    # A closing/rollback market order must have been sent (SELL to flatten long).
    closing = [
        c for c in raw.futures_create_order.call_args_list
        if c.kwargs.get("type") == "MARKET" and c.kwargs.get("side") == "SELL"
    ]
    assert closing, "expected a rollback market order to flatten the naked long"


# --- Fix #3: close_position cancels associated SL/TP -----------------------

def test_close_position_cancels_open_orders():
    client, raw = make_client()
    raw.futures_position_information.return_value = [
        {"symbol": "BTCUSDT", "positionAmt": "0.002"}
    ]
    client.close_position("BTC")
    raw.futures_cancel_all_open_orders.assert_called_once_with(symbol="BTCUSDT")


# --- Fix #4: daily loss kill-switch ----------------------------------------

def test_open_blocked_when_daily_loss_limit_breached():
    client, raw = make_client()
    client.max_daily_loss_pct = 5.0  # block after -5% of wallet
    # wallet 1000, realized -60 => -6% => breached
    raw.futures_account.return_value = {
        "totalWalletBalance": "1000",
        "availableBalance": "900",
        "totalUnrealizedProfit": "0",
        "totalMarginBalance": "1000",
        "assets": [],
    }
    raw.futures_income_history.return_value = [
        {"income": "-60", "time": 9_999_999_999_999}
    ]

    result = client.open_long_position(
        currency="BTC", quantity=0.002, stop_loss_price=98000, leverage=5
    )

    assert result.get("blocked") is True
    raw.futures_create_order.assert_not_called()


# --- Fix #18: exchange precision rounding ----------------------------------

def test_quantity_rounded_down_to_step_size():
    client, raw = make_client()
    client.open_long_position(
        currency="BTC", quantity=0.0025, stop_loss_price=98000, leverage=5
    )
    main = [
        c for c in raw.futures_create_order.call_args_list
        if c.kwargs.get("type") == "MARKET"
    ][0]
    # 0.0025 floored to step 0.001 => 0.002
    assert main.kwargs["quantity"] == pytest.approx(0.002)


def test_stop_price_rounded_to_tick_size():
    client, raw = make_client()
    client.open_long_position(
        currency="BTC", quantity=0.002, stop_loss_price=98000.07, leverage=5
    )
    stop = [
        c for c in raw.futures_create_order.call_args_list
        if c.kwargs.get("type") == "STOP_MARKET"
    ][0]
    price = stop.kwargs["stopPrice"]
    # tick 0.1 => price must be a multiple of 0.1
    assert round(price * 10) == pytest.approx(price * 10)


# --- Fix #17: daily PnL must capture the whole day ------------------------

def test_daily_pnl_queries_from_start_of_day():
    client, raw = make_client()
    raw.futures_income_history.return_value = [{"income": "10", "time": 9_999_999_999_999}]
    raw.futures_account.return_value = {
        "totalWalletBalance": "1000", "availableBalance": "1000",
        "totalUnrealizedProfit": "0", "totalMarginBalance": "1000", "assets": [],
    }

    client.get_daily_pnl()

    _, kwargs = raw.futures_income_history.call_args
    # Must scope the query to today's start (so a high-volume day is not truncated)
    assert kwargs.get("startTime") is not None
    assert kwargs.get("limit", 0) >= 1000


# --- Fix #16: entry price captured from the filled order ------------------

def test_entry_price_captured_from_filled_order():
    client, raw = make_client()
    raw.futures_create_order.return_value = {
        "orderId": 111, "status": "FILLED", "avgPrice": "100000.5"
    }

    result = client.open_long_position(
        currency="BTC", quantity=0.002, stop_loss_price=98000, leverage=5
    )

    assert result.get("entry_price") == pytest.approx(100000.5)
    # main market order should request a filled response so avgPrice is populated
    main = [
        c for c in raw.futures_create_order.call_args_list
        if c.kwargs.get("type") == "MARKET"
    ][0]
    assert main.kwargs.get("newOrderRespType") == "RESULT"

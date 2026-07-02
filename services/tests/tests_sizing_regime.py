"""
Phase-2 #2 guardrails: code computes position size (LLM does not), regime gate
blocks UNDEFINED regimes, and min-notional is enforced. Mocked client, no net.
"""
from unittest.mock import MagicMock

from services.binance_client import BinanceClient


def make_client(mark="100000", wallet="10000", min_notional="100", **kw):
    raw = MagicMock()
    raw.futures_exchange_info.return_value = {
        "symbols": [{
            "symbol": "BTCUSDT", "quoteAsset": "USDT", "contractType": "PERPETUAL",
            "status": "TRADING", "pricePrecision": 1, "quantityPrecision": 3,
            "filters": [
                {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
                {"filterType": "MIN_NOTIONAL", "notional": min_notional},
            ],
        }]
    }
    raw.futures_create_order.return_value = {"orderId": 1, "status": "NEW", "avgPrice": mark}
    raw.futures_change_leverage.return_value = {"leverage": 3}
    raw.futures_change_margin_type.return_value = {"code": 200}
    raw.futures_mark_price.return_value = {"markPrice": mark}
    raw.futures_account.return_value = {
        "totalWalletBalance": wallet, "availableBalance": wallet,
        "totalUnrealizedProfit": "0", "totalMarginBalance": wallet, "assets": [],
    }
    return BinanceClient(client=raw, **kw), raw


# --- deterministic sizing (LLM omits quantity) -----------------------------

def test_quantity_computed_from_risk_when_omitted():
    # risk 1% of 10000 = $100; stop 1000 away from mark => qty = 100/1000 = 0.1
    client, raw = make_client(risk_per_trade_pct=1.0)
    result = client.open_long_position("BTC", quantity=None, stop_loss_price=99000, leverage=3)
    assert "blocked" not in result
    main = [c for c in raw.futures_create_order.call_args_list if c.kwargs.get("type") == "MARKET"][0]
    assert abs(main.kwargs["quantity"] - 0.1) < 1e-9
    assert abs(result["quantity"] - 0.1) < 1e-9


# --- min-notional guardrail ------------------------------------------------

def test_min_notional_blocks_tiny_order():
    # explicit tiny quantity: 0.0001 * 100000 = $10 < $100 min notional
    client, raw = make_client(min_notional="100")
    result = client.open_long_position("BTC", quantity=0.0001, stop_loss_price=99000, leverage=3)
    assert result.get("blocked") is True
    raw.futures_create_order.assert_not_called()


# --- regime gate -----------------------------------------------------------

def test_undefined_regime_blocks_open_when_enforced():
    client, raw = make_client(risk_per_trade_pct=1.0, enforce_regime=True)
    client.get_regime = lambda currency: "UNDEFINED"
    result = client.open_long_position("BTC", quantity=None, stop_loss_price=99000, leverage=3)
    assert result.get("blocked") is True
    raw.futures_create_order.assert_not_called()


def test_trend_regime_allows_open_when_enforced():
    client, raw = make_client(risk_per_trade_pct=1.0, enforce_regime=True)
    client.get_regime = lambda currency: "TREND"
    result = client.open_long_position("BTC", quantity=None, stop_loss_price=99000, leverage=3)
    assert "blocked" not in result
    assert result.get("main_order_id") == 1

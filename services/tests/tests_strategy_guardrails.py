"""
Tests for the phase-2 deterministic guardrails: leverage cap and risk-per-trade
cap enforced in code, plus the ADX regime classifier. Mocked client, no network.
"""
from unittest.mock import MagicMock

from binance.exceptions import BinanceAPIException

from apps.genflows.trading_futures.strategy_config import (
    REGIME_RANGE,
    REGIME_TREND,
    REGIME_UNDEFINED,
    classify_regime,
)
from services.binance_client import BinanceClient


def _api_exc(msg="boom"):
    resp = MagicMock()
    resp.text = '{"code": -1, "msg": "%s"}' % msg
    return BinanceAPIException(resp, 400, resp.text)


def make_client(max_leverage=5, risk_per_trade_pct=1.0, mark="100000", wallet="1000"):
    raw = MagicMock()
    raw.futures_exchange_info.return_value = {
        "symbols": [{
            "symbol": "BTCUSDT", "quoteAsset": "USDT", "contractType": "PERPETUAL",
            "status": "TRADING", "pricePrecision": 1, "quantityPrecision": 3,
            "filters": [
                {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
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
    client = BinanceClient(client=raw, max_leverage=max_leverage, risk_per_trade_pct=risk_per_trade_pct)
    return client, raw


# --- regime classifier -----------------------------------------------------

def test_classify_regime_trend_range_undefined():
    assert classify_regime(30) == REGIME_TREND
    assert classify_regime(15) == REGIME_RANGE
    assert classify_regime(22) == REGIME_UNDEFINED
    assert classify_regime(None) == REGIME_UNDEFINED


# --- leverage cap ----------------------------------------------------------

def test_leverage_above_cap_is_blocked():
    client, raw = make_client(max_leverage=5)
    result = client.open_long_position("BTC", 0.002, stop_loss_price=99000, leverage=20)
    assert result.get("blocked") is True
    raw.futures_create_order.assert_not_called()


def test_leverage_within_cap_allowed():
    client, raw = make_client(max_leverage=5)
    result = client.open_long_position("BTC", 0.002, stop_loss_price=99000, leverage=3)
    assert "blocked" not in result
    assert result.get("main_order_id") == 1


# --- risk-per-trade cap ----------------------------------------------------

def test_risk_per_trade_above_cap_is_blocked():
    # mark 100000, stop 90000 => $10k move/coin; qty 0.01 => $100 risk on $1000 wallet = 10% >> 1%
    client, raw = make_client(risk_per_trade_pct=1.0, mark="100000", wallet="1000")
    result = client.open_long_position("BTC", 0.01, stop_loss_price=90000, leverage=3)
    assert result.get("blocked") is True
    raw.futures_create_order.assert_not_called()


def test_risk_per_trade_within_cap_allowed():
    # mark 100000, stop 99000 => $1000 move/coin; qty 0.002 => $2 risk on $1000 = 0.2% < 1%
    client, raw = make_client(risk_per_trade_pct=1.0, mark="100000", wallet="1000")
    result = client.open_long_position("BTC", 0.002, stop_loss_price=99000, leverage=3)
    assert "blocked" not in result
    assert result.get("main_order_id") == 1


# --- portfolio risk + max concurrent positions -----------------------------

def _open_pos(symbol, amt, mark, stop):
    """(position_information item, open stop order) pair for get_all_open_positions."""
    pos = {
        "symbol": symbol, "positionAmt": str(amt), "entryPrice": str(mark), "markPrice": str(mark),
        "liquidationPrice": "0", "unRealizedProfit": "0", "leverage": "3", "marginType": "isolated",
        "isolatedWallet": "0", "positionInitialMargin": "0",
    }
    order = {
        "symbol": symbol, "orderId": 9, "type": "STOP_MARKET", "side": "SELL", "price": "0",
        "stopPrice": str(stop), "origQty": str(amt), "status": "NEW", "time": 1,
    }
    return pos, order


def make_portfolio_client(positions, wallet="10000", max_portfolio_risk_pct=3.0, max_concurrent_positions=3):
    client, raw = make_client(max_leverage=5, risk_per_trade_pct=None, mark="100000", wallet=wallet)
    pos_items, orders = [], []
    for sym, amt, mark, stop in positions:
        p, o = _open_pos(sym, amt, mark, stop)
        pos_items.append(p)
        orders.append(o)
    raw.futures_position_information.return_value = pos_items
    raw.futures_get_open_orders.return_value = orders
    client.max_portfolio_risk_pct = max_portfolio_risk_pct
    client.max_concurrent_positions = max_concurrent_positions
    return client, raw


def test_portfolio_risk_over_cap_is_blocked():
    # existing ETH position: 0.07 * |100000-96000| = $280 = 2.8% of 10000
    client, raw = make_portfolio_client([("ETHUSDT", 0.07, 100000, 96000)], wallet="10000")
    # new BTC trade: 0.01 * |100000-95000| = $50 = 0.5% -> total 3.3% > 3%
    result = client.open_long_position("BTC", 0.01, stop_loss_price=95000, leverage=3)
    assert result.get("blocked") is True
    raw.futures_create_order.assert_not_called()


def test_max_concurrent_positions_is_blocked():
    client, raw = make_portfolio_client(
        [("ETHUSDT", 0.01, 100000, 99000), ("BNBUSDT", 0.01, 100000, 99000), ("SOLUSDT", 0.01, 100000, 99000)],
        max_concurrent_positions=3,
    )
    result = client.open_long_position("BTC", 0.001, stop_loss_price=99900, leverage=3)
    assert result.get("blocked") is True
    raw.futures_create_order.assert_not_called()


def test_within_portfolio_cap_allowed():
    # existing 0.05*|100000-98000| = $100 = 1%; new 0.01*|100000-90000| = $100 = 1% -> 2% <= 3%
    client, raw = make_portfolio_client([("ETHUSDT", 0.05, 100000, 98000)], wallet="10000")
    result = client.open_long_position("BTC", 0.01, stop_loss_price=90000, leverage=3)
    assert "blocked" not in result
    assert result.get("main_order_id") == 1

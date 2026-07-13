"""
Tests for annotate_recorded_protection — surfacing the SL/TP recorded at entry
onto demo positions whose conditional orders the open-orders endpoint can't list
(so the agent doesn't wrongly see a naked position and churn close/re-open).
"""
import pytest

from apps.genflows.trading_futures.workflow import annotate_recorded_protection
from tradings.models import TradingOperation


@pytest.mark.django_db
def test_recorded_sl_tp_is_surfaced_when_position_reports_none():
    TradingOperation.objects.create(
        operation_type=TradingOperation.OperationType.OPEN_LONG,
        status=TradingOperation.Status.SUCCESS,
        currency="BTC",
        stop_loss_price=60000.0,
        take_profit_price=68000.0,
        stop_loss_order_id="1000000134219754",
        take_profit_order_id="1000000134219758",
    )
    positions = [{"symbol": "BTCUSDT", "side": "LONG", "stop_loss_orders": [], "take_profit_orders": []}]

    out = annotate_recorded_protection(positions)

    assert out[0]["stop_loss_orders"], "recorded stop loss was not surfaced"
    assert out[0]["stop_loss_orders"][0]["stop_price"] == 60000.0
    assert out[0]["take_profit_orders"][0]["stop_price"] == 68000.0


@pytest.mark.django_db
def test_existing_visible_stop_is_left_untouched():
    TradingOperation.objects.create(
        operation_type=TradingOperation.OperationType.OPEN_LONG,
        status=TradingOperation.Status.SUCCESS,
        currency="BTC",
        stop_loss_price=60000.0,
        stop_loss_order_id="999",
    )
    real = {"order_id": 555, "type": "STOP_MARKET", "stop_price": 61000.0}
    positions = [{"symbol": "BTCUSDT", "side": "LONG", "stop_loss_orders": [real], "take_profit_orders": []}]

    out = annotate_recorded_protection(positions)

    # A position that already reports a stop must not be overwritten.
    assert out[0]["stop_loss_orders"] == [real]


@pytest.mark.django_db
def test_no_recorded_op_leaves_position_unprotected():
    positions = [{"symbol": "ETHUSDT", "side": "LONG", "stop_loss_orders": [], "take_profit_orders": []}]
    out = annotate_recorded_protection(positions)
    # No matching operation -> genuinely reported as unprotected (no masking).
    assert out[0]["stop_loss_orders"] == []


@pytest.mark.django_db
def test_annotate_open_time_attaches_opened_at():
    from apps.genflows.trading_futures.workflow import annotate_open_time
    op = TradingOperation.objects.create(
        operation_type=TradingOperation.OperationType.OPEN_LONG,
        status=TradingOperation.Status.SUCCESS,
        currency="BTC",
    )
    positions = [{"symbol": "BTCUSDT", "side": "LONG"}]
    out = annotate_open_time(positions)
    assert out[0]["opened_at"] == op.created_at.isoformat()


@pytest.mark.django_db
def test_annotate_open_time_no_op_leaves_absent():
    from apps.genflows.trading_futures.workflow import annotate_open_time
    out = annotate_open_time([{"symbol": "ETHUSDT", "side": "SHORT"}])
    assert "opened_at" not in out[0]

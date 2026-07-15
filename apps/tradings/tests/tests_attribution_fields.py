import pytest
from tradings.models import TradingOperation, TradingWorkflowExecution


@pytest.mark.django_db
def test_operation_source_defaults_to_agent():
    op = TradingOperation.objects.create(
        operation_type=TradingOperation.OperationType.OPEN_SHORT, currency="BTC"
    )
    assert op.source == "agent"


@pytest.mark.django_db
def test_operation_source_can_be_tagged():
    op = TradingOperation.objects.create(
        operation_type=TradingOperation.OperationType.OPEN_SHORT, currency="BTC", source="exploit_6"
    )
    assert TradingOperation.objects.filter(source="exploit_6").count() == 1


@pytest.mark.django_db
def test_execution_workflow_type_default():
    ex = TradingWorkflowExecution.objects.create(
        currencies=["BTC"], balance_info={}, market_data={}, daily_pnl={}
    )
    assert ex.workflow_type == "trading_futures"

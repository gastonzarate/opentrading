import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import nest_asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from langfuse import get_client
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from tradings.models import TradingWorkflowExecution

from apps.genflows.trading_futures.strategy_config import STRATEGY
from apps.genflows.trading_futures.workflow import TradingFuturesWorkflow

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

logger = logging.getLogger(__name__)

JOB_ID = "trading_futures_workflow"

# Dynamic cadence: there is no fixed interval. Each run self-schedules the next
# one at the agent-chosen (clamped) delay. This module owns the scheduler so the
# job can re-arm itself.
scheduler = BackgroundScheduler()


def schedule_next_run(minutes: int):
    """(Re)arm a single one-shot run `minutes` from now."""
    run_date = datetime.now(timezone.utc) + timedelta(minutes=max(0, minutes))
    scheduler.add_job(
        run_trading_workflow,
        "date",
        run_date=run_date,
        id=JOB_ID,
        name="Trading Futures Workflow",
        replace_existing=True,
        misfire_grace_time=120,
        coalesce=True,
        max_instances=1,
    )
    logger.info(f"🗓️  Next trading run scheduled at {run_date.isoformat()} (in {minutes} min)")


def start_scheduler():
    """Start the scheduler and fire the first run immediately."""
    if scheduler.running:
        return
    scheduler.start()
    schedule_next_run(0)


async def execute_workflow():
    """
    Run the trading workflow inside an active event loop.
    The workflow's .run() method is synchronous and schedules tasks using
    asyncio.create_task(), so it must be invoked from within a running loop.
    """
    LlamaIndexInstrumentor().instrument()
    langfuse = get_client()
    trace_id = langfuse.create_trace_id()
    # pylint: disable=not-context-manager
    with langfuse.start_as_current_span(
        name="trading-futures-workflow-scheduled", trace_context={"trace_id": trace_id}
    ):
        langfuse.update_current_trace(user_id="scheduler", session_id=f"scheduled-{trace_id}")

        workflow = TradingFuturesWorkflow(timeout=480)
        logger.info("✅ Trading workflow initialized")

        # Only liquid, volatile perpetuals. Stablecoins (USDC/BFUSD) were removed:
        # trading a perp on a ~$1 asset has no edge and just wastes cycles/API calls.
        handler = workflow.run(currencies=["BTC", "ETH", "BNB", "SOL"])
    langfuse.flush()

    return await handler


def run_trading_workflow():
    """
    Execute the trading futures workflow once, then self-schedule the next run at
    the agent-chosen (clamped) delay. There is no fixed interval.
    """

    start_time = time.time()
    result = None
    error = None

    try:
        # Create and run the workflow within a running event loop
        result = asyncio.run(execute_workflow())

    except Exception as e:
        error = e
        logger.error(f"❌ Error executing trading workflow: {e}", exc_info=True)

    finally:
        # Calculate execution duration
        execution_duration = time.time() - start_time

        # Save to database
        try:
            if result:
                execution = TradingWorkflowExecution.save_from_workflow_result(
                    result=result, execution_duration=execution_duration, error=error
                )
                logger.info(
                    f"💾 Execution saved to database: {execution.id} - "
                    f"Status: {execution.status} - Duration: {execution_duration:.2f}s"
                )
            elif error:
                # Save error-only execution
                execution = TradingWorkflowExecution(
                    status=TradingWorkflowExecution.Status.ERROR,
                    execution_duration=execution_duration,
                    currencies=[],
                    balance_info={},
                    market_data={},
                    open_positions=[],
                    daily_pnl={},
                    system_prompt="",
                    error_message=str(error),
                )
                execution.save()
                logger.error(f"💾 Error execution saved to database: {execution.id}")
        except Exception as db_error:
            logger.error(f"❌ Failed to save execution to database: {db_error}", exc_info=True)

        # Self-schedule the next run. Always re-arm (even on error) so the loop
        # never dies; on success use the agent's clamped choice.
        next_minutes = STRATEGY.default_run_minutes
        if result is not None:
            next_minutes = getattr(result, "next_run_minutes", None) or STRATEGY.default_run_minutes
        try:
            schedule_next_run(next_minutes)
        except Exception as sched_error:
            logger.error(f"❌ Failed to schedule next run: {sched_error}", exc_info=True)

        logger.info("✅ Trading workflow execution finished")

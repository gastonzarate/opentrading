"""Trading Workflow Execution Model"""

import traceback
import uuid

from django.db import models

from core.models import TimeStampedModel


class TradingWorkflowExecution(TimeStampedModel):
    """
    Stores complete results from each trading workflow execution.

    This model captures all data from the TradingFuturesWorkflow including:
    - Balance information
    - Market data for all currencies
    - Open positions with associated orders
    - Daily performance metrics
    - AI agent analysis and actions
    """

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        ERROR = "ERROR", "Error"
        TIMEOUT = "TIMEOUT", "Timeout"
        RUNNING = "RUNNING", "Running"

    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Execution Metadata
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING, db_index=True)
    workflow_type = models.CharField(
        max_length=32,
        default="trading_futures",
        db_index=True,
        help_text="Which workflow produced this execution: 'trading_futures' or an exploit id e.g. 'exploit_6'.",
    )
    execution_duration = models.FloatField(null=True, blank=True, help_text="Execution time in seconds")

    # Workflow Input
    currencies = models.JSONField(help_text="List of currencies analyzed (e.g., ['BTC', 'ETH'])")

    # Balance Information
    balance_info = models.JSONField(
        help_text="Complete balance snapshot including total, available, and unrealized PnL"
    )

    # Market Data
    market_data = models.JSONField(
        help_text="Market data for each currency including price, indicators, OI, and funding rate"
    )

    # Open Positions
    open_positions = models.JSONField(
        default=list, help_text="All open positions with associated orders and risk metrics"
    )

    # Daily Performance
    daily_pnl = models.JSONField(help_text="Daily performance metrics: PnL, trade count, win rate")

    # Agent Response
    system_prompt = models.TextField(
        blank=True, default="", help_text="Complete system prompt provided to the agent with all context"
    )
    agent_response = models.TextField(blank=True, help_text="Full AI agent analysis and decision rationale")
    agent_streaming_output = models.TextField(
        blank=True, help_text="Complete streaming output from the agent during execution"
    )
    agent_actions_taken = models.JSONField(
        default=list, blank=True, help_text="Structured list of actions taken by the agent"
    )

    strategy_for_next_execution = models.TextField(
        blank=True,
        help_text="Agent's strategic plan and context for the next execution (agent memory)",
    )

    next_run_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Minutes until the next run, chosen by the agent and clamped to config bounds",
    )

    # Error Handling
    error_message = models.TextField(blank=True, help_text="Error message if execution failed")
    error_traceback = models.TextField(blank=True, help_text="Full stack trace for debugging")

    class Meta:
        app_label = "tradings"
        ordering = ["-created_at"]
        verbose_name = "Trading Workflow Execution"
        verbose_name_plural = "Trading Workflow Executions"
        indexes = [
            models.Index(fields=["-created_at", "status"]),
        ]

    def __str__(self):
        currencies_str = ", ".join(self.currencies) if self.currencies else "N/A"
        return f"{self.created_at.strftime('%Y-%m-%d %H:%M')} - {currencies_str} - {self.status}"

    @classmethod
    def save_from_workflow_result(cls, result, execution_duration: float = None, error: Exception = None):
        """
        Create and save a TradingWorkflowExecution from a TradingResult dataclass.

        Args:
            result: TradingResult dataclass or dict with workflow results
            execution_duration: Time taken to execute workflow in seconds
            error: Exception if workflow failed

        Returns:
            TradingWorkflowExecution instance
        """

        execution = cls(
            status=cls.Status.ERROR if error else cls.Status.SUCCESS,
            execution_duration=execution_duration,
            currencies=result.currencies,
            balance_info=result.balance_info,
            market_data=result.market_data,
            open_positions=result.open_positions,
            daily_pnl=result.daily_pnl,
            system_prompt=result.system_prompt,
            agent_response=result.agent_response,
            agent_streaming_output=result.agent_streaming_output,
            strategy_for_next_execution=result.strategy_for_next_execution,
            next_run_minutes=getattr(result, "next_run_minutes", None),
        )

        if error:
            execution.error_message = str(error)
            execution.error_traceback = traceback.format_exc()

        execution.save()
        return execution

    def get_summary(self) -> dict:
        """
        Get a human-readable summary of the execution.

        Returns:
            dict: Summary with key metrics
        """
        return {
            "execution_id": str(self.id),
            "timestamp": self.created_at.isoformat(),
            "status": self.status,
            "duration": f"{self.execution_duration:.2f}s" if self.execution_duration else "N/A",
            "currencies": self.currencies,
            "total_balance": self.balance_info.get("total_wallet_balance", 0),
            "available_balance": self.balance_info.get("available_balance", 0),
            "daily_pnl": self.daily_pnl.get("total_daily_pnl", 0),
            "trade_count": self.daily_pnl.get("trade_count", 0),
            "win_rate": self.daily_pnl.get("win_rate", 0),
            "open_positions_count": len(self.open_positions),
            "has_error": bool(self.error_message),
        }

    def get_balance_summary(self) -> str:
        """Get formatted balance summary."""
        total = self.balance_info.get("total_wallet_balance", 0)
        available = self.balance_info.get("available_balance", 0)
        unrealized = self.balance_info.get("total_unrealized_pnl", 0)

        return f"Total: ${total:.2f} | " f"Available: ${available:.2f} | " f"Unrealized PnL: ${unrealized:.2f}"

    def get_performance_summary(self) -> str:
        """Get formatted performance summary."""
        pnl = self.daily_pnl.get("total_daily_pnl", 0)
        trades = self.daily_pnl.get("trade_count", 0)
        win_rate = self.daily_pnl.get("win_rate", 0)

        return f"Daily PnL: ${pnl:.2f} | " f"Trades: {trades} | " f"Win Rate: {win_rate:.1f}%"

import uuid

from django.db import models

from core.models import TimeStampedModel


class TradingOperation(TimeStampedModel):
    """
    Tracks individual trading operations (Open Long, Open Short, Close Position).
    """

    class OperationType(models.TextChoices):
        OPEN_LONG = "OPEN_LONG", "Open Long"
        OPEN_SHORT = "OPEN_SHORT", "Open Short"
        CLOSE_POSITION = "CLOSE_POSITION", "Close Position"

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        ERROR = "ERROR", "Error"
        PENDING = "PENDING", "Pending"

    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    workflow_execution = models.ForeignKey(
        "tradings.TradingWorkflowExecution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operations",
        help_text="The workflow execution that triggered this operation",
    )

    # Operation Details
    operation_type = models.CharField(max_length=20, choices=OperationType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    currency = models.CharField(max_length=20, help_text="Base currency symbol (e.g., BTC)")

    # Trading Parameters (for Open operations)
    quantity = models.FloatField(null=True, blank=True)
    leverage = models.IntegerField(null=True, blank=True)
    entry_price = models.FloatField(null=True, blank=True, help_text="Price at which the position was opened")
    stop_loss_price = models.FloatField(null=True, blank=True)
    take_profit_price = models.FloatField(null=True, blank=True)

    # Order IDs (from Binance)
    main_order_id = models.CharField(max_length=100, null=True, blank=True)
    stop_loss_order_id = models.CharField(max_length=100, null=True, blank=True)
    take_profit_order_id = models.CharField(max_length=100, null=True, blank=True)

    # Results
    realized_pnl = models.FloatField(
        null=True,
        blank=True,
        help_text="Realized PnL in USDT for a close (from Binance account trades). Null for opens.",
    )
    result_data = models.JSONField(default=dict, blank=True, help_text="Full response from Binance API")
    error_message = models.TextField(blank=True)

    class Meta:
        app_label = "tradings"
        ordering = ["-created_at"]
        verbose_name = "Trading Operation"
        verbose_name_plural = "Trading Operations"
        indexes = [
            models.Index(fields=["-created_at", "operation_type"]),
            models.Index(fields=["currency", "status"]),
        ]

    def __str__(self):
        return f"{self.operation_type} - {self.currency} - {self.status}"

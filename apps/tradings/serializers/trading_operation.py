"""Trading Operation Serializers"""

from rest_framework import serializers
from tradings.models import TradingOperation


class TradingOperationSerializer(serializers.ModelSerializer):
    """
    Serializer for TradingOperation model.

    Provides comprehensive serialization of trading operations including
    operation details, parameters, order IDs, and results.
    """

    # Read-only fields for better display
    operation_type_display = serializers.CharField(source="get_operation_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    workflow_execution_id = serializers.UUIDField(source="workflow_execution.id", read_only=True, allow_null=True)

    class Meta:
        model = TradingOperation
        fields = [
            # Primary key
            "id",
            # Timestamps (from TimeStampedModel)
            "created_at",
            "updated_at",
            # Relationships
            "workflow_execution",
            "workflow_execution_id",
            # Operation details
            "operation_type",
            "operation_type_display",
            "status",
            "status_display",
            "currency",
            # Trading parameters
            "quantity",
            "leverage",
            "entry_price",
            "stop_loss_price",
            "take_profit_price",
            # Order IDs
            "main_order_id",
            "stop_loss_order_id",
            "take_profit_order_id",
            # Results
            "realized_pnl",
            "result_data",
            "error_message",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "operation_type_display",
            "status_display",
            "workflow_execution_id",
        ]


class TradingOperationListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views.

    Excludes heavy fields like result_data for better performance.
    """

    operation_type_display = serializers.CharField(source="get_operation_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    workflow_execution_id = serializers.UUIDField(source="workflow_execution.id", read_only=True, allow_null=True)

    class Meta:
        model = TradingOperation
        fields = [
            "id",
            "created_at",
            "updated_at",
            "workflow_execution_id",
            "operation_type",
            "operation_type_display",
            "status",
            "status_display",
            "currency",
            "quantity",
            "entry_price",
            "realized_pnl",
            "error_message",
        ]
        read_only_fields = fields

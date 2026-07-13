"""Trading Workflow Execution Serializers"""

from rest_framework import serializers
from tradings.models import TradingWorkflowExecution


class TradingWorkflowExecutionSerializer(serializers.ModelSerializer):
    """
    Serializer for TradingWorkflowExecution model.

    Provides comprehensive serialization of workflow execution data including
    balance, market data, positions, and agent responses.
    """

    # Read-only computed fields
    summary = serializers.SerializerMethodField()
    balance_summary = serializers.SerializerMethodField()
    performance_summary = serializers.SerializerMethodField()

    class Meta:
        model = TradingWorkflowExecution
        fields = [
            # Primary key
            "id",
            # Timestamps (from TimeStampedModel)
            "created_at",
            "updated_at",
            # Execution metadata
            "status",
            "execution_duration",
            # Workflow data
            "currencies",
            "balance_info",
            "market_data",
            "open_positions",
            "daily_pnl",
            # Agent data
            "system_prompt",
            "agent_response",
            "agent_streaming_output",
            "agent_actions_taken",
            # Temporal context
            "strategy_for_next_execution",
            "next_run_minutes",
            # Error handling
            "error_message",
            "error_traceback",
            # Computed fields
            "summary",
            "balance_summary",
            "performance_summary",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "summary",
            "balance_summary",
            "performance_summary",
        ]

    def get_summary(self, obj):
        """Get execution summary."""
        return obj.get_summary()

    def get_balance_summary(self, obj):
        """Get formatted balance summary."""
        return obj.get_balance_summary()

    def get_performance_summary(self, obj):
        """Get formatted performance summary."""
        return obj.get_performance_summary()


class TradingWorkflowExecutionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views.

    Excludes heavy fields like streaming output and tracebacks
    for better performance in list endpoints.
    """

    summary = serializers.SerializerMethodField()

    class Meta:
        model = TradingWorkflowExecution
        fields = [
            "id",
            "created_at",
            "updated_at",
            "status",
            "execution_duration",
            "currencies",
            "summary",
        ]
        read_only_fields = fields

    def get_summary(self, obj):
        """Get execution summary."""
        return obj.get_summary()

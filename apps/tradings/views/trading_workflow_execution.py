"""Trading Workflow Execution Views"""

from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from tradings.models import TradingWorkflowExecution
from tradings.serializers import TradingWorkflowExecutionListSerializer, TradingWorkflowExecutionSerializer


class TradingWorkflowExecutionFilter(filters.FilterSet):
    """
    FilterSet for TradingWorkflowExecution.

    Provides filtering by:
    - Date range (created_at)
    - Status
    - Currencies
    """

    # Date range filters
    start_date = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    end_date = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    # Date filters (for day-level filtering)
    date = filters.DateFilter(field_name="created_at", lookup_expr="date")
    date_gte = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_lte = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    # Status filter
    status = filters.ChoiceFilter(choices=TradingWorkflowExecution.Status.choices)

    # Currency filter (contains)
    currency = filters.CharFilter(field_name="currencies", lookup_expr="contains")

    # Strategy filter ('trading_futures' for the general bot, 'exploit_6', ...)
    workflow_type = filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = TradingWorkflowExecution
        fields = ["status", "start_date", "end_date", "date", "date_gte", "date_lte", "currency", "workflow_type"]


class TradingWorkflowExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for TradingWorkflowExecution.

    Provides:
    - List endpoint with filtering and pagination
    - Detail endpoint for individual executions
    - Custom actions for statistics

    Query Parameters:
    - start_date: Filter executions after this datetime (ISO 8601)
    - end_date: Filter executions before this datetime (ISO 8601)
    - date: Filter executions on specific date (YYYY-MM-DD)
    - date_gte: Filter executions on or after date (YYYY-MM-DD)
    - date_lte: Filter executions on or before date (YYYY-MM-DD)
    - status: Filter by execution status (SUCCESS, ERROR, TIMEOUT, RUNNING)
    - currency: Filter by currency (e.g., BTC, ETH)

    Examples:
    - GET /api/tradings/executions/?start_date=2025-11-01T00:00:00Z&end_date=2025-11-30T23:59:59Z
    - GET /api/tradings/executions/?date=2025-11-27
    - GET /api/tradings/executions/?date_gte=2025-11-01&date_lte=2025-11-30
    - GET /api/tradings/executions/?status=SUCCESS
    - GET /api/tradings/executions/?currency=BTC
    """

    queryset = TradingWorkflowExecution.objects.all()
    permission_classes = [AllowAny]
    filterset_class = TradingWorkflowExecutionFilter
    ordering_fields = ["created_at", "execution_duration", "status"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Use lightweight serializer for list, full serializer for detail."""
        if self.action == "list":
            return TradingWorkflowExecutionListSerializer
        return TradingWorkflowExecutionSerializer

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """
        Get statistics for filtered executions.

        Returns aggregated statistics including:
        - Total executions
        - Success/error counts
        - Average execution duration
        - Total PnL
        """
        queryset = self.filter_queryset(self.get_queryset())

        total_count = queryset.count()
        success_count = queryset.filter(status=TradingWorkflowExecution.Status.SUCCESS).count()
        error_count = queryset.filter(status=TradingWorkflowExecution.Status.ERROR).count()

        # Calculate average execution duration
        executions_with_duration = queryset.exclude(execution_duration__isnull=True)
        avg_duration = None
        if executions_with_duration.exists():
            total_duration = sum(e.execution_duration for e in executions_with_duration)
            avg_duration = total_duration / executions_with_duration.count()

        # Calculate total daily PnL
        total_pnl = 0.0
        for execution in queryset.filter(status=TradingWorkflowExecution.Status.SUCCESS):
            total_pnl += execution.daily_pnl.get("total_daily_pnl", 0)

        return Response(
            {
                "total_executions": total_count,
                "success_count": success_count,
                "error_count": error_count,
                "success_rate": (success_count / total_count * 100) if total_count > 0 else 0,
                "average_execution_duration": round(avg_duration, 2) if avg_duration else None,
                "total_daily_pnl": round(total_pnl, 2),
            }
        )

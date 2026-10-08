"""Trading Operation Views"""

from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from tradings.models import TradingOperation
from tradings.serializers import TradingOperationListSerializer, TradingOperationSerializer


class TradingOperationFilter(filters.FilterSet):
    """
    FilterSet for TradingOperation.

    Provides filtering by:
    - Date range (created_at)
    - Operation type
    - Status
    - Currency
    - Workflow execution
    """

    # Date range filters
    start_date = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    end_date = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    # Date filters (for day-level filtering)
    date = filters.DateFilter(field_name="created_at", lookup_expr="date")
    date_gte = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_lte = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    # Operation type filter
    operation_type = filters.ChoiceFilter(choices=TradingOperation.OperationType.choices)

    # Status filter
    status = filters.ChoiceFilter(choices=TradingOperation.Status.choices)

    # Currency filter
    currency = filters.CharFilter(lookup_expr="iexact")

    # Strategy source filter ('agent' for the general bot, 'exploit_6', ...)
    source = filters.CharFilter(lookup_expr="iexact")

    # Workflow execution filter
    workflow_execution = filters.UUIDFilter(field_name="workflow_execution__id")

    class Meta:
        model = TradingOperation
        fields = [
            "operation_type",
            "status",
            "currency",
            "source",
            "workflow_execution",
            "start_date",
            "end_date",
            "date",
            "date_gte",
            "date_lte",
        ]


class TradingOperationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for TradingOperation.

    Provides:
    - List endpoint with filtering and pagination
    - Detail endpoint for individual operations
    - Custom actions for statistics

    Query Parameters:
    - start_date: Filter operations after this datetime (ISO 8601)
    - end_date: Filter operations before this datetime (ISO 8601)
    - date: Filter operations on specific date (YYYY-MM-DD)
    - date_gte: Filter operations on or after date (YYYY-MM-DD)
    - date_lte: Filter operations on or before date (YYYY-MM-DD)
    - operation_type: Filter by operation type (OPEN_LONG, OPEN_SHORT, CLOSE_POSITION)
    - status: Filter by status (SUCCESS, ERROR, PENDING)
    - currency: Filter by currency (e.g., BTC, ETH)
    - workflow_execution: Filter by workflow execution ID (UUID)

    Examples:
    - GET /api/tradings/operations/?operation_type=OPEN_LONG
    - GET /api/tradings/operations/?status=SUCCESS&currency=BTC
    - GET /api/tradings/operations/?date=2025-11-28
    - GET /api/tradings/operations/?workflow_execution=550e8400-e29b-41d4-a716-446655440000
    """

    queryset = TradingOperation.objects.select_related("workflow_execution").all()
    permission_classes = [AllowAny]
    filterset_class = TradingOperationFilter
    ordering_fields = ["created_at", "operation_type", "status", "currency"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Use lightweight serializer for list, full serializer for detail."""
        if self.action == "list":
            return TradingOperationListSerializer
        return TradingOperationSerializer

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """
        Get statistics for filtered operations.

        Returns aggregated statistics including:
        - Total operations
        - Success/error counts by operation type
        - Average quantities
        - Most traded currencies
        """
        queryset = self.filter_queryset(self.get_queryset())

        total_count = queryset.count()
        success_count = queryset.filter(status=TradingOperation.Status.SUCCESS).count()
        error_count = queryset.filter(status=TradingOperation.Status.ERROR).count()
        pending_count = queryset.filter(status=TradingOperation.Status.PENDING).count()

        # Count by operation type
        open_long_count = queryset.filter(operation_type=TradingOperation.OperationType.OPEN_LONG).count()
        open_short_count = queryset.filter(operation_type=TradingOperation.OperationType.OPEN_SHORT).count()
        close_position_count = queryset.filter(operation_type=TradingOperation.OperationType.CLOSE_POSITION).count()

        # Most traded currencies
        from django.db.models import Count, Sum

        top_currencies = list(queryset.values("currency").annotate(count=Count("currency")).order_by("-count")[:5])

        # Realized-PnL aggregates over CLOSED trades (realized_pnl is set).
        # This is the fair per-strategy performance metric: the two live bots
        # share ONE testnet account, so account balance is not attributable per
        # strategy — the sum of a strategy's own closed-trade PnL is.
        closed = queryset.exclude(realized_pnl__isnull=True)
        closed_count = closed.count()
        wins = closed.filter(realized_pnl__gt=0).count()
        losses = closed.filter(realized_pnl__lt=0).count()
        realized_total = closed.aggregate(s=Sum("realized_pnl"))["s"] or 0.0

        return Response(
            {
                "total_operations": total_count,
                "success_count": success_count,
                "error_count": error_count,
                "pending_count": pending_count,
                "success_rate": (success_count / total_count * 100) if total_count > 0 else 0,
                "operations_by_type": {
                    "open_long": open_long_count,
                    "open_short": open_short_count,
                    "close_position": close_position_count,
                },
                "top_currencies": top_currencies,
                # Per-strategy realized performance (combine with ?source=...)
                "realized_pnl_total": round(realized_total, 2),
                "closed_trades": closed_count,
                "wins": wins,
                "losses": losses,
                "win_rate_realized": round(wins / closed_count * 100, 1) if closed_count else 0,
                "avg_realized_pnl": round(realized_total / closed_count, 2) if closed_count else 0,
            }
        )

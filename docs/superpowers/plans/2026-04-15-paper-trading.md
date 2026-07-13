# Paper Trading Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent paper trading mode that runs in parallel with the live bot, using a virtual USDT balance, real market data, and realistic fill simulation (order-book slippage, taker fees, intra-minute SL/TP via 1m klines, liquidation heuristic).

**Architecture:** A new `PaperBinanceClient` implements the same public contract as `BinanceClient` — reads delegate to the live client, writes operate on new `PaperAccount` / `PaperPosition` / `PaperOperation` Django models. A `PaperFillEngine` scans 1m klines each cycle to trigger stop-loss / take-profit / liquidation before the workflow runs. The scheduler registers a second job (`paper_trading_job`) behind a feature flag that runs the same `TradingFuturesWorkflow` class with the paper client injected.

**Tech Stack:** Python 3.12, Django 5.2, APScheduler, LlamaIndex workflows, pytest, python-binance, ta (technical indicators), pandas, PostgreSQL.

---

## Reference: Spec

The full design is at `docs/superpowers/specs/2026-04-15-paper-trading-design.md`. This plan implements that spec.

## File Structure

**Create:**
- `apps/tradings/models/paper_account.py` — `PaperAccount` model
- `apps/tradings/models/paper_position.py` — `PaperPosition` model
- `apps/tradings/models/paper_operation.py` — `PaperOperation` model
- `apps/tradings/migrations/<auto>_paper_trading.py` — migrations
- `services/paper_binance_client.py` — `PaperBinanceClient`
- `services/paper_fill_engine.py` — `PaperFillEngine`
- `services/tests/test_paper_fill_engine.py` — unit tests for fill engine
- `services/tests/test_paper_binance_client.py` — unit tests for paper client
- `services/tests/test_paper_client_contract.py` — contract parity tests
- `apps/tradings/tests/__init__.py` — test package
- `apps/tradings/tests/test_paper_workflow.py` — integration test

**Modify:**
- `apps/tradings/models/__init__.py` — export new models
- `apps/tradings/models/trading_workflow_execution.py` — add `mode` field
- `apps/tradings/admin.py` — register paper admins, add mode filter, add reset action
- `apps/tradings/scheduler.py` — register `paper_trading_job` behind feature flag
- `apps/tradings/views/trading_workflow_execution.py` — accept `mode` query param
- `apps/genflows/trading_futures/workflow.py` — accept client via DI
- `apps/genflows/trading_futures/binance_tools.py` — accept client via DI, use `PaperOperation` when in paper mode
- `index.html` — add mode selector

---

## Task 1: Refactor workflow and tools to accept client via dependency injection

Today `TradingFuturesWorkflow` and `BinanceTools` both instantiate `BinanceClient()` themselves. We need both to accept an injected client so the scheduler can swap in `PaperBinanceClient`.

**Files:**
- Modify: `apps/genflows/trading_futures/workflow.py:69-78`
- Modify: `apps/genflows/trading_futures/binance_tools.py:13-21`
- Modify: `apps/tradings/scheduler.py:33`

- [ ] **Step 1: Change `TradingFuturesWorkflow.__init__` to accept a client**

Open `apps/genflows/trading_futures/workflow.py` and replace lines 69-78:

```python
def __init__(self, *args, binance_client=None, mode: str = "LIVE", **kwargs):
    """
    Initialize the trading workflow.

    Args:
        binance_client: Optional client with the BinanceClient interface.
                        If None, creates a real BinanceClient.
        mode: "LIVE" or "PAPER". Passed through to persisted executions.
    """
    super().__init__(*args, **kwargs)
    self.binance_client = binance_client if binance_client is not None else BinanceClient()
    self.mode = mode
```

- [ ] **Step 2: Change `BinanceTools.__init__` signature (no behavior change yet)**

Open `apps/genflows/trading_futures/binance_tools.py` and confirm `__init__` already takes `binance_client` (it does on line 13). Add a `mode` parameter so the tool can decide whether to write to `TradingOperation` (live) or `PaperOperation` (paper) — this will be used in Task 9. Replace lines 13-21:

```python
def __init__(self, binance_client, mode: str = "LIVE"):
    """
    Initialize BinanceTools with a client and mode.

    Args:
        binance_client: Any client implementing the BinanceClient interface
                        (real or paper).
        mode: "LIVE" or "PAPER". Determines which Operation model to record to.
    """
    self.binance_client = binance_client
    self.mode = mode
    self.backtest_service = BacktestService(binance_client)
```

- [ ] **Step 3: Pass `mode` from workflow into `BinanceTools`**

In `apps/genflows/trading_futures/workflow.py`, find the line `binance_tools = BinanceTools(self.binance_client)` (near line 257) and replace with:

```python
binance_tools = BinanceTools(self.binance_client, mode=self.mode)
```

- [ ] **Step 4: Run existing workflow in the scheduler to confirm live path still works**

Run:
```bash
cd /Users/gastonzarate/Documents/Code/opentrading
python -c "from apps.genflows.trading_futures.workflow import TradingFuturesWorkflow; w = TradingFuturesWorkflow(timeout=10); print('OK', w.mode, type(w.binance_client).__name__)"
```
Expected output contains: `OK LIVE BinanceClient`

- [ ] **Step 5: Commit**

```bash
git add apps/genflows/trading_futures/workflow.py apps/genflows/trading_futures/binance_tools.py
git commit -m "refactor: accept binance_client via DI in workflow and tools"
```

---

## Task 2: Add `mode` field to `TradingWorkflowExecution`

So the same table stores both live and paper executions, distinguishable by `mode`. This enables the dashboard filter later.

**Files:**
- Modify: `apps/tradings/models/trading_workflow_execution.py:23-37, 105-116`
- Create: auto-generated migration

- [ ] **Step 1: Add `Mode` choices and `mode` field**

Open `apps/tradings/models/trading_workflow_execution.py`. After the `Status` TextChoices class (ending at line 27), add a `Mode` class:

```python
    class Mode(models.TextChoices):
        LIVE = "LIVE", "Live"
        PAPER = "PAPER", "Paper"
```

Then, after the `status` field (line 33), add a `mode` field:

```python
    mode = models.CharField(
        max_length=10,
        choices=Mode.choices,
        default=Mode.LIVE,
        db_index=True,
        help_text="Whether this execution belongs to live or paper trading",
    )
```

- [ ] **Step 2: Update `save_from_workflow_result` to accept mode**

In the same file, replace the `save_from_workflow_result` signature and body (starting at line 92) with:

```python
    @classmethod
    def save_from_workflow_result(cls, result, execution_duration: float = None,
                                  error: Exception = None, mode: str = "LIVE"):
        """
        Create and save a TradingWorkflowExecution from a TradingResult dataclass.
        """
        execution = cls(
            status=cls.Status.ERROR if error else cls.Status.SUCCESS,
            mode=mode,
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
        )
        if error:
            execution.error_message = str(error)
            execution.error_traceback = traceback.format_exc()
        execution.save()
        return execution
```

- [ ] **Step 3: Update scheduler callsite to pass mode**

Open `apps/tradings/scheduler.py`. Find the call `TradingWorkflowExecution.save_from_workflow_result(result=result, execution_duration=execution_duration, error=error)` (around line 67) and change to:

```python
execution = TradingWorkflowExecution.save_from_workflow_result(
    result=result, execution_duration=execution_duration, error=error, mode="LIVE"
)
```

Also find the error-only `TradingWorkflowExecution(...)` instantiation (around line 76) and add `mode="LIVE"` to its kwargs.

- [ ] **Step 4: Generate and apply migration**

Run:
```bash
cd /Users/gastonzarate/Documents/Code/opentrading
python manage.py makemigrations tradings --name add_execution_mode
python manage.py migrate
```
Expected: `Migrations for 'tradings': ... Create model ... Add field mode ...` then `Applying tradings.<name>... OK`.

- [ ] **Step 5: Commit**

```bash
git add apps/tradings/models/trading_workflow_execution.py apps/tradings/scheduler.py apps/tradings/migrations/
git commit -m "feat: add mode field to TradingWorkflowExecution"
```

---

## Task 3: Create `PaperAccount` model

**Files:**
- Create: `apps/tradings/models/paper_account.py`
- Modify: `apps/tradings/models/__init__.py`
- Create: migration

- [ ] **Step 1: Create the model file**

Create `apps/tradings/models/paper_account.py`:

```python
"""Paper trading account model."""

import uuid
from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel


class PaperAccount(TimeStampedModel):
    """
    Virtual trading account used by the paper-trading simulator.

    Holds a virtual USDT balance, fee configuration, and a watermark
    used by PaperFillEngine for idempotent scans.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Human-readable account name")
    initial_balance = models.DecimalField(
        max_digits=20, decimal_places=8,
        help_text="Starting wallet balance in USDT",
    )
    current_balance = models.DecimalField(
        max_digits=20, decimal_places=8,
        help_text="Current wallet balance in USDT (excludes unrealized PnL)",
    )
    is_active = models.BooleanField(
        default=False,
        help_text="If false, the paper scheduler job is not registered for this account",
    )
    taker_fee_pct = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal("0.0400"),
        help_text="Taker fee as a percentage (e.g. 0.0400 means 0.04%)",
    )
    maker_fee_pct = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal("0.0200"),
        help_text="Maker fee as a percentage; reserved for future limit-order support",
    )
    last_scan_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Watermark timestamp for PaperFillEngine idempotency",
    )

    class Meta:
        app_label = "tradings"
        ordering = ["-created_at"]
        verbose_name = "Paper Account"
        verbose_name_plural = "Paper Accounts"

    def __str__(self):
        return f"{self.name} (${self.current_balance:.2f})"
```

- [ ] **Step 2: Export from the models package**

Open `apps/tradings/models/__init__.py` and add below the existing imports:

```python
from .paper_account import *  # NOQA
```

- [ ] **Step 3: Generate and apply migration**

```bash
cd /Users/gastonzarate/Documents/Code/opentrading
python manage.py makemigrations tradings --name add_paper_account
python manage.py migrate
```
Expected: successful `Create model PaperAccount`.

- [ ] **Step 4: Commit**

```bash
git add apps/tradings/models/paper_account.py apps/tradings/models/__init__.py apps/tradings/migrations/
git commit -m "feat: add PaperAccount model"
```

---

## Task 4: Create `PaperPosition` model

**Files:**
- Create: `apps/tradings/models/paper_position.py`
- Modify: `apps/tradings/models/__init__.py`
- Create: migration

- [ ] **Step 1: Create the model file**

Create `apps/tradings/models/paper_position.py`:

```python
"""Paper trading position model."""

import uuid

from django.db import models

from core.models import TimeStampedModel


class PaperPosition(TimeStampedModel):
    """
    A virtual position opened by the paper-trading bot against a PaperAccount.

    While OPEN, the mark price and unrealized PnL are computed on demand by
    PaperBinanceClient using live Binance market data. When closed, the
    realized PnL (net of fees) is settled into the account balance.
    """

    class Side(models.TextChoices):
        LONG = "LONG", "Long"
        SHORT = "SHORT", "Short"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"

    class CloseReason(models.TextChoices):
        STOP_LOSS = "STOP_LOSS", "Stop Loss"
        TAKE_PROFIT = "TAKE_PROFIT", "Take Profit"
        MANUAL = "MANUAL", "Manual"
        LIQUIDATION = "LIQUIDATION", "Liquidation"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        "tradings.PaperAccount", on_delete=models.CASCADE,
        related_name="positions",
    )
    symbol = models.CharField(max_length=20, help_text="Full symbol, e.g. BTCUSDT")
    side = models.CharField(max_length=10, choices=Side.choices)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    leverage = models.IntegerField(default=1)
    stop_loss_price = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True,
    )
    take_profit_price = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True,
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_price = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True,
    )
    close_reason = models.CharField(
        max_length=20, choices=CloseReason.choices, null=True, blank=True,
    )
    realized_pnl = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True,
        help_text="Net of fees",
    )
    fees_paid = models.DecimalField(max_digits=20, decimal_places=8, default=0)

    class Meta:
        app_label = "tradings"
        ordering = ["-opened_at"]
        verbose_name = "Paper Position"
        verbose_name_plural = "Paper Positions"
        indexes = [
            models.Index(fields=["account", "status"]),
            models.Index(fields=["symbol", "status"]),
        ]

    def __str__(self):
        return f"{self.symbol} {self.side} x{self.quantity} @ {self.entry_price} ({self.status})"
```

- [ ] **Step 2: Export from the models package**

Open `apps/tradings/models/__init__.py` and add:

```python
from .paper_position import *  # NOQA
```

- [ ] **Step 3: Generate and apply migration**

```bash
cd /Users/gastonzarate/Documents/Code/opentrading
python manage.py makemigrations tradings --name add_paper_position
python manage.py migrate
```
Expected: `Create model PaperPosition`.

- [ ] **Step 4: Commit**

```bash
git add apps/tradings/models/paper_position.py apps/tradings/models/__init__.py apps/tradings/migrations/
git commit -m "feat: add PaperPosition model"
```

---

## Task 5: Create `PaperOperation` model

Mirror of `TradingOperation` but owned by a `PaperAccount`. Recorded by `BinanceTools` when in `PAPER` mode.

**Files:**
- Create: `apps/tradings/models/paper_operation.py`
- Modify: `apps/tradings/models/__init__.py`
- Create: migration

- [ ] **Step 1: Create the model file**

Create `apps/tradings/models/paper_operation.py`:

```python
"""Paper trading operation model (mirror of TradingOperation)."""

import uuid

from django.db import models

from core.models import TimeStampedModel


class PaperOperation(TimeStampedModel):
    """
    Mirror of TradingOperation for paper trading.

    Records each OPEN_LONG / OPEN_SHORT / CLOSE_POSITION call initiated
    by the AI agent in paper mode, together with its success/error outcome.
    """

    class OperationType(models.TextChoices):
        OPEN_LONG = "OPEN_LONG", "Open Long"
        OPEN_SHORT = "OPEN_SHORT", "Open Short"
        CLOSE_POSITION = "CLOSE_POSITION", "Close Position"

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        ERROR = "ERROR", "Error"
        PENDING = "PENDING", "Pending"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        "tradings.PaperAccount", on_delete=models.CASCADE,
        related_name="operations",
    )
    workflow_execution = models.ForeignKey(
        "tradings.TradingWorkflowExecution",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="paper_operations",
    )
    operation_type = models.CharField(max_length=20, choices=OperationType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    currency = models.CharField(max_length=20)
    quantity = models.FloatField(null=True, blank=True)
    leverage = models.IntegerField(null=True, blank=True)
    entry_price = models.FloatField(null=True, blank=True)
    stop_loss_price = models.FloatField(null=True, blank=True)
    take_profit_price = models.FloatField(null=True, blank=True)
    main_order_id = models.CharField(max_length=100, null=True, blank=True)
    stop_loss_order_id = models.CharField(max_length=100, null=True, blank=True)
    take_profit_order_id = models.CharField(max_length=100, null=True, blank=True)
    result_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        app_label = "tradings"
        ordering = ["-created_at"]
        verbose_name = "Paper Operation"
        verbose_name_plural = "Paper Operations"
        indexes = [
            models.Index(fields=["-created_at", "operation_type"]),
            models.Index(fields=["currency", "status"]),
        ]

    def __str__(self):
        return f"{self.operation_type} - {self.currency} - {self.status} (paper)"
```

- [ ] **Step 2: Export from the models package**

Open `apps/tradings/models/__init__.py` and add:

```python
from .paper_operation import *  # NOQA
```

- [ ] **Step 3: Generate and apply migration**

```bash
cd /Users/gastonzarate/Documents/Code/opentrading
python manage.py makemigrations tradings --name add_paper_operation
python manage.py migrate
```
Expected: `Create model PaperOperation`.

- [ ] **Step 4: Commit**

```bash
git add apps/tradings/models/paper_operation.py apps/tradings/models/__init__.py apps/tradings/migrations/
git commit -m "feat: add PaperOperation model"
```

---

## Task 6: `PaperFillEngine` — slippage and fee helpers

Build the stateless helper class with two first methods: `simulate_market_fill` (VWAP across the order book) and `compute_fee`. Other fill-engine methods follow in Task 7.

**Files:**
- Create: `services/paper_fill_engine.py`
- Create: `services/tests/test_paper_fill_engine.py`

- [ ] **Step 1: Write the failing test for `simulate_market_fill`**

Create `services/tests/test_paper_fill_engine.py`:

```python
"""Unit tests for PaperFillEngine."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from services.paper_fill_engine import PaperFillEngine


class TestSimulateMarketFill:
    """Tests for VWAP slippage via order book walking."""

    def _mock_client(self, bids, asks):
        client = MagicMock()
        client.get_order_book_depth.return_value = {
            "top_bids": bids,
            "top_asks": asks,
        }
        return client

    def test_buy_single_level_sufficient(self):
        """Fill fits entirely in best ask → price is best ask."""
        live = self._mock_client(
            bids=[(99.0, 10.0)],
            asks=[(100.0, 5.0), (101.0, 10.0)],
        )
        engine = PaperFillEngine()
        price = engine.simulate_market_fill(live, currency="BTC", side="BUY", quantity=2.0)
        assert price == pytest.approx(100.0)

    def test_buy_walks_multiple_levels_vwap(self):
        """Fill exceeds best ask → VWAP across asks."""
        live = self._mock_client(
            bids=[(99.0, 10.0)],
            asks=[(100.0, 1.0), (101.0, 1.0), (102.0, 10.0)],
        )
        engine = PaperFillEngine()
        # Need 2.5: 1.0 at 100, 1.0 at 101, 0.5 at 102
        # VWAP = (100*1 + 101*1 + 102*0.5) / 2.5 = 252/2.5 = 100.8
        price = engine.simulate_market_fill(live, currency="BTC", side="BUY", quantity=2.5)
        assert price == pytest.approx(100.8)

    def test_sell_walks_bids(self):
        """SELL consumes bids from best downward."""
        live = self._mock_client(
            bids=[(100.0, 1.0), (99.0, 10.0)],
            asks=[(101.0, 10.0)],
        )
        engine = PaperFillEngine()
        # Need 2.0: 1.0 at 100, 1.0 at 99 → VWAP = 99.5
        price = engine.simulate_market_fill(live, currency="BTC", side="SELL", quantity=2.0)
        assert price == pytest.approx(99.5)

    def test_empty_book_returns_zero(self):
        """If there is no liquidity at all, return 0.0 (caller handles)."""
        live = self._mock_client(bids=[], asks=[])
        engine = PaperFillEngine()
        price = engine.simulate_market_fill(live, currency="BTC", side="BUY", quantity=1.0)
        assert price == 0.0

    def test_insufficient_depth_uses_last_level(self):
        """If depth cannot cover the size, use worst price and log warning."""
        live = self._mock_client(
            bids=[(99.0, 10.0)],
            asks=[(100.0, 1.0)],  # only 1.0 available but we want 5.0
        )
        engine = PaperFillEngine()
        # Fill: 1.0 at 100, remaining 4.0 at 100 (worst known). VWAP = 100.
        price = engine.simulate_market_fill(live, currency="BTC", side="BUY", quantity=5.0)
        assert price == pytest.approx(100.0)


class TestComputeFee:
    """Tests for taker fee computation."""

    def test_basic_fee(self):
        engine = PaperFillEngine()
        # price=100, qty=2, pct=0.04 → notional=200, fee=0.08
        fee = engine.compute_fee(price=Decimal("100"), quantity=Decimal("2"),
                                 fee_pct=Decimal("0.04"))
        assert fee == Decimal("0.08")

    def test_fee_with_fractional_qty(self):
        engine = PaperFillEngine()
        fee = engine.compute_fee(price=Decimal("50000"), quantity=Decimal("0.01"),
                                 fee_pct=Decimal("0.04"))
        # notional=500, fee=0.2
        assert fee == Decimal("0.2000")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
cd /Users/gastonzarate/Documents/Code/opentrading
pytest services/tests/test_paper_fill_engine.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'services.paper_fill_engine'`.

- [ ] **Step 3: Implement `PaperFillEngine` with `simulate_market_fill` and `compute_fee`**

Create `services/paper_fill_engine.py`:

```python
"""Paper-trading fill engine.

Stateless helper that simulates order fills, fees, and stop-loss / take-profit
triggers against an in-database PaperAccount using live Binance market data.
"""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class PaperFillEngine:
    """Simulates fills, fees, and SL/TP triggers for paper trading."""

    def simulate_market_fill(self, live_client, currency: str, side: str,
                             quantity: float) -> float:
        """
        Compute the VWAP a market order would receive by walking the order book.

        Args:
            live_client: A BinanceClient instance used only for order-book reads.
            currency: Base currency symbol (e.g. "BTC").
            side: "BUY" or "SELL".
            quantity: Size to fill (in base asset).

        Returns:
            VWAP of the fill. If the book is empty, returns 0.0.
            If book depth is insufficient, consumes what's available and
            backfills the remainder at the worst known price (logged warning).
        """
        book = live_client.get_order_book_depth(currency, limit=50)
        levels = book["top_asks"] if side == "BUY" else book["top_bids"]

        if not levels:
            logger.warning("Empty order book for %s %s — returning 0 price", currency, side)
            return 0.0

        remaining = float(quantity)
        total_cost = 0.0
        filled = 0.0
        worst_price = 0.0

        for price, qty in levels:
            price = float(price)
            qty = float(qty)
            take = min(remaining, qty)
            total_cost += take * price
            filled += take
            remaining -= take
            worst_price = price
            if remaining <= 0:
                break

        if remaining > 0:
            logger.warning(
                "Insufficient book depth for %s %s qty=%s — backfilling %.6f "
                "at worst known price %.2f",
                currency, side, quantity, remaining, worst_price,
            )
            total_cost += remaining * worst_price
            filled += remaining

        if filled == 0:
            return 0.0
        return total_cost / filled

    def compute_fee(self, price: Decimal, quantity: Decimal,
                    fee_pct: Decimal) -> Decimal:
        """
        Compute a taker (or maker) fee as Decimal.

        fee = price * quantity * fee_pct / 100

        `fee_pct` is expressed as a percentage (e.g. Decimal("0.04") for 0.04%).
        """
        return (Decimal(price) * Decimal(quantity) * Decimal(fee_pct)) / Decimal("100")
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:
```bash
pytest services/tests/test_paper_fill_engine.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/paper_fill_engine.py services/tests/test_paper_fill_engine.py
git commit -m "feat: add PaperFillEngine with slippage and fee helpers"
```

---

## Task 7: `PaperFillEngine` — SL/TP detection, liquidation, `scan_and_close_triggered`

Extends the engine with the intra-minute SL/TP scan. Uses 1m klines from `live_client.client.get_klines` (note: the python-binance client exposes this at `.client.get_klines`, not `.get_klines`; we pass the raw `Client` through a helper).

**Files:**
- Modify: `services/paper_fill_engine.py`
- Modify: `services/tests/test_paper_fill_engine.py`

- [ ] **Step 1: Write failing tests for SL/TP and liquidation logic**

Append to `services/tests/test_paper_fill_engine.py` (before the final blank line):

```python
class TestDetermineTrigger:
    """Tests for resolving which of SL/TP triggers first in a single candle."""

    def test_long_sl_hit_only(self):
        engine = PaperFillEngine()
        # LONG: sl=95, tp=110. Candle: open=100, high=105, low=94, close=95.
        trigger = engine.determine_trigger(
            side="LONG", sl=95.0, tp=110.0,
            kline_open=100.0, kline_high=105.0, kline_low=94.0,
        )
        assert trigger == ("STOP_LOSS", 95.0)

    def test_long_tp_hit_only(self):
        engine = PaperFillEngine()
        trigger = engine.determine_trigger(
            side="LONG", sl=95.0, tp=110.0,
            kline_open=100.0, kline_high=112.0, kline_low=99.0,
        )
        assert trigger == ("TAKE_PROFIT", 110.0)

    def test_long_both_hit_sl_closer_to_open(self):
        engine = PaperFillEngine()
        # open=100, sl=95 (dist 5), tp=110 (dist 10) → sl first
        trigger = engine.determine_trigger(
            side="LONG", sl=95.0, tp=110.0,
            kline_open=100.0, kline_high=112.0, kline_low=94.0,
        )
        assert trigger == ("STOP_LOSS", 95.0)

    def test_long_both_hit_tp_closer_to_open(self):
        engine = PaperFillEngine()
        # open=108, sl=95 (dist 13), tp=110 (dist 2) → tp first
        trigger = engine.determine_trigger(
            side="LONG", sl=95.0, tp=110.0,
            kline_open=108.0, kline_high=112.0, kline_low=94.0,
        )
        assert trigger == ("TAKE_PROFIT", 110.0)

    def test_short_sl_hit(self):
        engine = PaperFillEngine()
        # SHORT: sl=105 (above), tp=90 (below). Candle high reaches 106.
        trigger = engine.determine_trigger(
            side="SHORT", sl=105.0, tp=90.0,
            kline_open=100.0, kline_high=106.0, kline_low=95.0,
        )
        assert trigger == ("STOP_LOSS", 105.0)

    def test_short_tp_hit(self):
        engine = PaperFillEngine()
        trigger = engine.determine_trigger(
            side="SHORT", sl=105.0, tp=90.0,
            kline_open=100.0, kline_high=101.0, kline_low=89.0,
        )
        assert trigger == ("TAKE_PROFIT", 90.0)

    def test_neither_hit(self):
        engine = PaperFillEngine()
        trigger = engine.determine_trigger(
            side="LONG", sl=95.0, tp=110.0,
            kline_open=100.0, kline_high=104.0, kline_low=96.0,
        )
        assert trigger is None

    def test_missing_sl_only_tp(self):
        engine = PaperFillEngine()
        trigger = engine.determine_trigger(
            side="LONG", sl=None, tp=110.0,
            kline_open=100.0, kline_high=112.0, kline_low=80.0,
        )
        assert trigger == ("TAKE_PROFIT", 110.0)


class TestLiquidationThreshold:
    """Tests for the -95% margin liquidation heuristic."""

    def test_long_at_liquidation(self):
        engine = PaperFillEngine()
        # entry=100, qty=1, lev=10 → margin=10. 95% of margin = 9.5.
        # unrealized <= -9.5 when mark <= 90.5.
        assert engine.is_liquidated(
            side="LONG", entry_price=100.0, quantity=1.0,
            leverage=10, mark_price=90.5,
        )
        assert not engine.is_liquidated(
            side="LONG", entry_price=100.0, quantity=1.0,
            leverage=10, mark_price=90.6,
        )

    def test_short_at_liquidation(self):
        engine = PaperFillEngine()
        # entry=100, qty=1, lev=10, margin=10.
        # SHORT loses when price goes up. unrealized = (entry-mark)*qty.
        # -9.5 when mark = 109.5.
        assert engine.is_liquidated(
            side="SHORT", entry_price=100.0, quantity=1.0,
            leverage=10, mark_price=109.5,
        )
        assert not engine.is_liquidated(
            side="SHORT", entry_price=100.0, quantity=1.0,
            leverage=10, mark_price=109.4,
        )
```

- [ ] **Step 2: Run tests and verify failures**

```bash
pytest services/tests/test_paper_fill_engine.py::TestDetermineTrigger services/tests/test_paper_fill_engine.py::TestLiquidationThreshold -v
```
Expected: FAIL with `AttributeError: 'PaperFillEngine' object has no attribute 'determine_trigger'`.

- [ ] **Step 3: Add `determine_trigger` and `is_liquidated` methods**

Append to `services/paper_fill_engine.py`, inside the `PaperFillEngine` class:

```python
    def determine_trigger(self, side: str, sl, tp,
                          kline_open: float, kline_high: float,
                          kline_low: float):
        """
        Given a 1m candle's OHLC, decide which of SL/TP (if any) triggered.

        Returns:
            Tuple (reason, price) where reason is "STOP_LOSS" or "TAKE_PROFIT",
            and price is the trigger price used as fill price.
            Returns None if neither triggered.
        """
        sl = float(sl) if sl is not None else None
        tp = float(tp) if tp is not None else None

        if side == "LONG":
            sl_hit = sl is not None and kline_low <= sl
            tp_hit = tp is not None and kline_high >= tp
        else:  # SHORT
            sl_hit = sl is not None and kline_high >= sl
            tp_hit = tp is not None and kline_low <= tp

        if sl_hit and tp_hit:
            # Heuristic: whichever is closer to the candle open triggers first.
            if abs(kline_open - sl) <= abs(kline_open - tp):
                return ("STOP_LOSS", sl)
            return ("TAKE_PROFIT", tp)
        if sl_hit:
            return ("STOP_LOSS", sl)
        if tp_hit:
            return ("TAKE_PROFIT", tp)
        return None

    def is_liquidated(self, side: str, entry_price: float, quantity: float,
                      leverage: int, mark_price: float) -> bool:
        """
        Return True if the position's unrealized loss has reached 95% of its
        initial margin — our liquidation heuristic.
        """
        if leverage <= 0 or quantity == 0:
            return False
        sign = 1 if side == "LONG" else -1
        unrealized = (mark_price - entry_price) * quantity * sign
        initial_margin = (entry_price * quantity) / leverage
        return unrealized <= -0.95 * initial_margin
```

- [ ] **Step 4: Run all fill-engine tests, verify they pass**

```bash
pytest services/tests/test_paper_fill_engine.py -v
```
Expected: all tests PASS (original 7 + new tests).

- [ ] **Step 5: Add `scan_and_close_triggered` method**

Still in `services/paper_fill_engine.py`, add:

```python
    def scan_and_close_triggered(self, paper_client, account):
        """
        For every open PaperPosition in the account:
          1. Check liquidation against current mark price.
          2. Fetch 1m klines newer than account.last_scan_at and check SL/TP.
          3. If triggered, close the position via paper_client._force_close.
        Updates account.last_scan_at to the newest kline close time processed.
        """
        from datetime import datetime, timezone
        from tradings.models import PaperPosition

        open_positions = PaperPosition.objects.filter(
            account=account, status=PaperPosition.Status.OPEN,
        )
        newest_close_ms = None

        for position in open_positions:
            base_currency = position.symbol.replace("USDT", "")

            # 1. Liquidation check against current price
            market = paper_client.live.get_market_data(base_currency)
            mark_price = float(market["current_price"])
            if self.is_liquidated(
                side=position.side,
                entry_price=float(position.entry_price),
                quantity=float(position.quantity),
                leverage=position.leverage,
                mark_price=mark_price,
            ):
                paper_client._force_close(position, close_price=mark_price,
                                          reason="LIQUIDATION")
                continue

            # 2. SL/TP via 1m klines
            since_ms = None
            if account.last_scan_at is not None:
                since_ms = int(account.last_scan_at.timestamp() * 1000)

            klines = paper_client.live.client.get_klines(
                symbol=position.symbol, interval="1m", limit=30,
            )
            # kline shape: [openTime, open, high, low, close, volume, closeTime, ...]
            for kline in klines:
                close_time_ms = int(kline[6])
                if since_ms is not None and close_time_ms <= since_ms:
                    continue
                trigger = self.determine_trigger(
                    side=position.side,
                    sl=position.stop_loss_price,
                    tp=position.take_profit_price,
                    kline_open=float(kline[1]),
                    kline_high=float(kline[2]),
                    kline_low=float(kline[3]),
                )
                if trigger is not None:
                    reason, price = trigger
                    paper_client._force_close(position, close_price=price,
                                              reason=reason)
                    break
                if newest_close_ms is None or close_time_ms > newest_close_ms:
                    newest_close_ms = close_time_ms

        if newest_close_ms is not None:
            account.last_scan_at = datetime.fromtimestamp(
                newest_close_ms / 1000, tz=timezone.utc,
            )
            account.save(update_fields=["last_scan_at", "updated_at"])
```

Note: `paper_client._force_close` is defined in Task 10. Its job is to settle a position to the account: deduct close fee, compute realized PnL, update balance, mark the `PaperPosition` as CLOSED with the given reason.

- [ ] **Step 6: Commit**

```bash
git add services/paper_fill_engine.py services/tests/test_paper_fill_engine.py
git commit -m "feat: add SL/TP trigger detection and scan loop to PaperFillEngine"
```

---

## Task 8: `PaperBinanceClient` — constructor, read delegation, balance, positions

**Files:**
- Create: `services/paper_binance_client.py`
- Create: `services/tests/test_paper_binance_client.py`

- [ ] **Step 1: Write the failing tests**

Create `services/tests/test_paper_binance_client.py`:

```python
"""Unit tests for PaperBinanceClient.

These tests use Django's TestCase because they touch the ORM.
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.test import TestCase

from services.paper_binance_client import PaperBinanceClient
from tradings.models import PaperAccount, PaperPosition


class PaperBinanceClientTestBase(TestCase):
    def setUp(self):
        self.account = PaperAccount.objects.create(
            name="test",
            initial_balance=Decimal("1000"),
            current_balance=Decimal("1000"),
            is_active=True,
        )
        self.live = MagicMock()
        self.live.get_order_book_depth.return_value = {
            "top_bids": [(99.0, 100.0)],
            "top_asks": [(100.0, 100.0)],
        }
        self.live.get_market_data.return_value = {"current_price": 100.0}
        self.client = PaperBinanceClient(self.account, self.live)


class TestReadDelegation(PaperBinanceClientTestBase):
    def test_get_order_book_depth_delegates(self):
        result = self.client.get_order_book_depth("BTC", limit=10)
        self.live.get_order_book_depth.assert_called_with("BTC", limit=10)
        assert result == self.live.get_order_book_depth.return_value

    def test_get_market_data_delegates(self):
        result = self.client.get_market_data("BTC")
        self.live.get_market_data.assert_called_with("BTC")
        assert result == self.live.get_market_data.return_value


class TestBalance(PaperBinanceClientTestBase):
    def test_balance_no_positions(self):
        info = self.client.get_futures_balance()
        assert info["total_wallet_balance"] == pytest.approx(1000.0)
        assert info["total_unrealized_pnl"] == pytest.approx(0.0)
        assert info["available_balance"] == pytest.approx(1000.0)

    def test_balance_with_open_long_in_profit(self):
        PaperPosition.objects.create(
            account=self.account, symbol="BTCUSDT", side="LONG",
            quantity=Decimal("1"), entry_price=Decimal("90"),
            leverage=10, status="OPEN",
        )
        # mark=100 → unrealized = (100-90)*1 = 10
        # used_margin = 90*1/10 = 9
        info = self.client.get_futures_balance()
        assert info["total_unrealized_pnl"] == pytest.approx(10.0)
        assert info["available_balance"] == pytest.approx(1000.0 - 9.0)


class TestGetOpenPosition(PaperBinanceClientTestBase):
    def test_no_position_returns_zero(self):
        assert self.client.get_open_position("BTC") == 0.0

    def test_long_returns_positive(self):
        PaperPosition.objects.create(
            account=self.account, symbol="BTCUSDT", side="LONG",
            quantity=Decimal("0.5"), entry_price=Decimal("100"),
            leverage=1, status="OPEN",
        )
        assert self.client.get_open_position("BTC") == pytest.approx(0.5)

    def test_short_returns_negative(self):
        PaperPosition.objects.create(
            account=self.account, symbol="BTCUSDT", side="SHORT",
            quantity=Decimal("0.5"), entry_price=Decimal("100"),
            leverage=1, status="OPEN",
        )
        assert self.client.get_open_position("BTC") == pytest.approx(-0.5)


class TestGetAllOpenPositions(PaperBinanceClientTestBase):
    def test_shape_matches_live_keys(self):
        PaperPosition.objects.create(
            account=self.account, symbol="BTCUSDT", side="LONG",
            quantity=Decimal("1"), entry_price=Decimal("90"),
            leverage=10, status="OPEN",
            stop_loss_price=Decimal("85"),
            take_profit_price=Decimal("110"),
        )
        result = self.client.get_all_open_positions()
        assert len(result) == 1
        pos = result[0]
        required_keys = {
            "symbol", "position_amount", "entry_price", "mark_price",
            "liquidation_price", "unrealized_pnl", "leverage", "side",
            "margin_type", "isolated_wallet", "position_initial_margin",
            "stop_loss_orders", "take_profit_orders", "limit_orders",
            "total_orders",
        }
        assert required_keys.issubset(pos.keys())
        assert pos["side"] == "LONG"
        assert pos["position_amount"] == pytest.approx(1.0)
        assert pos["mark_price"] == pytest.approx(100.0)
        assert pos["unrealized_pnl"] == pytest.approx(10.0)
        # SL/TP synthesized as "orders"
        assert len(pos["stop_loss_orders"]) == 1
        assert pos["stop_loss_orders"][0]["stop_price"] == pytest.approx(85.0)
        assert len(pos["take_profit_orders"]) == 1
        assert pos["take_profit_orders"][0]["stop_price"] == pytest.approx(110.0)
```

- [ ] **Step 2: Run tests and verify failures**

```bash
cd /Users/gastonzarate/Documents/Code/opentrading
pytest services/tests/test_paper_binance_client.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'services.paper_binance_client'`.

- [ ] **Step 3: Implement `PaperBinanceClient` with constructor and read methods**

Create `services/paper_binance_client.py`:

```python
"""Paper-trading client with the same public contract as BinanceClient."""

import logging
import uuid
from decimal import Decimal

logger = logging.getLogger(__name__)


class PaperBinanceClient:
    """
    Drop-in replacement for BinanceClient that simulates trading against a
    PaperAccount while delegating market-data reads to a real BinanceClient.
    """

    def __init__(self, account, live_client):
        self.account = account
        self.live = live_client
        # In-memory per-symbol leverage (mirrors Binance's stateful leverage).
        self._pending_leverage: dict[str, int] = {}

    # ---- read delegation ----------------------------------------------------

    def get_market_data(self, currency: str) -> dict:
        return self.live.get_market_data(currency)

    def get_order_book_depth(self, currency: str, limit: int = 10) -> dict:
        return self.live.get_order_book_depth(currency, limit=limit)

    def get_available_futures_symbols(self, quote_asset: str = "USDT") -> list:
        return self.live.get_available_futures_symbols(quote_asset=quote_asset)

    # ---- state reads --------------------------------------------------------

    def get_open_position(self, currency: str) -> float:
        """Return the signed position amount (+long / -short / 0)."""
        from tradings.models import PaperPosition
        symbol = f"{currency.upper()}USDT"
        pos = PaperPosition.objects.filter(
            account=self.account, symbol=symbol,
            status=PaperPosition.Status.OPEN,
        ).first()
        if pos is None:
            return 0.0
        amount = float(pos.quantity)
        return amount if pos.side == PaperPosition.Side.LONG else -amount

    def get_all_open_positions(self) -> list:
        """Return live-shaped dicts for all open PaperPositions."""
        from tradings.models import PaperPosition
        out = []
        positions = PaperPosition.objects.filter(
            account=self.account, status=PaperPosition.Status.OPEN,
        )
        for p in positions:
            base = p.symbol.replace("USDT", "")
            mark_price = float(self.live.get_market_data(base)["current_price"])
            sign = 1 if p.side == PaperPosition.Side.LONG else -1
            unrealized = (mark_price - float(p.entry_price)) * float(p.quantity) * sign
            position_amount = float(p.quantity) * sign
            initial_margin = float(p.entry_price) * float(p.quantity) / max(p.leverage, 1)

            stop_loss_orders = []
            if p.stop_loss_price is not None:
                stop_loss_orders.append(self._synth_order(
                    p, float(p.stop_loss_price), "STOP_MARKET",
                ))
            take_profit_orders = []
            if p.take_profit_price is not None:
                take_profit_orders.append(self._synth_order(
                    p, float(p.take_profit_price), "TAKE_PROFIT_MARKET",
                ))

            out.append({
                "symbol": p.symbol,
                "position_amount": position_amount,
                "entry_price": float(p.entry_price),
                "mark_price": mark_price,
                "liquidation_price": 0.0,  # not modeled
                "unrealized_pnl": unrealized,
                "leverage": int(p.leverage),
                "side": p.side,
                "margin_type": "cross",
                "isolated_wallet": 0.0,
                "position_initial_margin": initial_margin,
                "stop_loss_orders": stop_loss_orders,
                "take_profit_orders": take_profit_orders,
                "limit_orders": [],
                "total_orders": len(stop_loss_orders) + len(take_profit_orders),
            })
        return out

    def get_futures_balance(self) -> dict:
        from tradings.models import PaperPosition
        wallet = float(self.account.current_balance)
        positions = PaperPosition.objects.filter(
            account=self.account, status=PaperPosition.Status.OPEN,
        )
        unrealized = 0.0
        used_margin = 0.0
        for p in positions:
            base = p.symbol.replace("USDT", "")
            mark_price = float(self.live.get_market_data(base)["current_price"])
            sign = 1 if p.side == PaperPosition.Side.LONG else -1
            unrealized += (mark_price - float(p.entry_price)) * float(p.quantity) * sign
            used_margin += float(p.entry_price) * float(p.quantity) / max(p.leverage, 1)
        return {
            "total_wallet_balance": wallet,
            "total_margin_balance": wallet + unrealized,
            "available_balance": wallet - used_margin,
            "total_unrealized_pnl": unrealized,
            "assets": [{
                "asset": "USDT",
                "wallet_balance": wallet,
                "unrealized_profit": unrealized,
                "margin_balance": wallet + unrealized,
                "available_balance": wallet - used_margin,
            }],
        }

    # ---- helpers -----------------------------------------------------------

    @staticmethod
    def _synth_order(position, stop_price: float, order_type: str) -> dict:
        """Build a live-shaped order dict from a PaperPosition's SL/TP field."""
        sign = 1 if position.side == "LONG" else -1
        side = "SELL" if sign == 1 else "BUY"
        return {
            "order_id": f"paper-{uuid.uuid4().hex[:12]}",
            "type": order_type,
            "side": side,
            "price": 0.0,
            "stop_price": float(stop_price),
            "quantity": float(position.quantity),
            "status": "NEW",
            "time": 0,
        }
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
pytest services/tests/test_paper_binance_client.py -v
```
Expected: `TestReadDelegation`, `TestBalance`, `TestGetOpenPosition`, `TestGetAllOpenPositions` all PASS.

- [ ] **Step 5: Commit**

```bash
git add services/paper_binance_client.py services/tests/test_paper_binance_client.py
git commit -m "feat: add PaperBinanceClient with read delegation and balance views"
```

---

## Task 9: `PaperBinanceClient` — open long / open short / set_leverage

**Files:**
- Modify: `services/paper_binance_client.py`
- Modify: `services/tests/test_paper_binance_client.py`

- [ ] **Step 1: Write failing tests**

Append to `services/tests/test_paper_binance_client.py`:

```python
class TestOpenLong(PaperBinanceClientTestBase):
    def test_requires_stop_loss(self):
        with pytest.raises(ValueError, match="stop_loss_price is required"):
            self.client.open_long_position(
                currency="BTC", quantity=1.0, stop_loss_price=None,
                leverage=5,
            )

    def test_min_notional_rejected(self):
        # price=100, qty=0.1, lev=5 → notional=50 < 100
        result = self.client.open_long_position(
            currency="BTC", quantity=0.1, stop_loss_price=95.0,
            leverage=5,
        )
        assert "error" in result
        assert "notional" in result["error"].lower()

    def test_insufficient_balance(self):
        # Make account poor
        self.account.current_balance = Decimal("5")
        self.account.save()
        # notional=100*1*5=500, required margin=100, balance=5
        result = self.client.open_long_position(
            currency="BTC", quantity=1.0, stop_loss_price=95.0,
            leverage=5,
        )
        assert "error" in result
        assert "balance" in result["error"].lower()

    def test_success_creates_position_and_deducts_fee(self):
        result = self.client.open_long_position(
            currency="BTC", quantity=1.0, stop_loss_price=95.0,
            take_profit_price=110.0, leverage=5,
        )
        assert "error" not in result
        assert result["side"] == "LONG"
        assert result["symbol"] == "BTCUSDT"
        # notional=100*1*5=500, fee=500*0.04/100=0.2
        self.account.refresh_from_db()
        assert self.account.current_balance == pytest.approx(Decimal("999.8"))
        positions = PaperPosition.objects.filter(account=self.account)
        assert positions.count() == 1
        assert positions.first().fees_paid == pytest.approx(Decimal("0.2"))


class TestOpenShort(PaperBinanceClientTestBase):
    def test_success_creates_short_position(self):
        result = self.client.open_short_position(
            currency="BTC", quantity=1.0, stop_loss_price=110.0,
            take_profit_price=90.0, leverage=5,
        )
        assert result["side"] == "SHORT"
        pos = PaperPosition.objects.filter(account=self.account).first()
        assert pos.side == "SHORT"


class TestSetLeverage(PaperBinanceClientTestBase):
    def test_set_leverage_picked_up_on_next_open(self):
        assert self.client.set_leverage("BTC", 10) is True
        # open without passing leverage: should use 10
        result = self.client.open_long_position(
            currency="BTC", quantity=0.2, stop_loss_price=95.0,
        )
        assert "error" not in result
        pos = PaperPosition.objects.filter(account=self.account).first()
        assert pos.leverage == 10
```

- [ ] **Step 2: Run tests, verify failures**

```bash
pytest services/tests/test_paper_binance_client.py::TestOpenLong services/tests/test_paper_binance_client.py::TestOpenShort services/tests/test_paper_binance_client.py::TestSetLeverage -v
```
Expected: FAIL — methods not defined.

- [ ] **Step 3: Implement the open/short/leverage methods**

Append to the `PaperBinanceClient` class in `services/paper_binance_client.py`:

```python
    def set_leverage(self, currency: str, leverage: int) -> bool:
        symbol = f"{currency.upper()}USDT"
        self._pending_leverage[symbol] = int(leverage)
        return True

    def open_long_position(self, currency: str, quantity: float,
                           stop_loss_price: float = None,
                           take_profit_price: float = None,
                           leverage: int = None) -> dict:
        return self._open(
            currency=currency, quantity=quantity, side="LONG",
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            leverage=leverage,
        )

    def open_short_position(self, currency: str, quantity: float,
                            stop_loss_price: float = None,
                            take_profit_price: float = None,
                            leverage: int = None) -> dict:
        return self._open(
            currency=currency, quantity=quantity, side="SHORT",
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            leverage=leverage,
        )

    def _open(self, *, currency: str, quantity: float, side: str,
              stop_loss_price, take_profit_price, leverage) -> dict:
        from django.db import transaction
        from tradings.models import PaperPosition

        from services.paper_fill_engine import PaperFillEngine

        if stop_loss_price is None:
            raise ValueError(
                "stop_loss_price is required. "
                f"Cannot open a {side.lower()} position without a stop loss."
            )

        symbol = f"{currency.upper()}USDT"
        effective_leverage = int(
            leverage if leverage is not None
            else self._pending_leverage.get(symbol, 1)
        )

        engine = PaperFillEngine()
        fill_side = "BUY" if side == "LONG" else "SELL"
        fill_price = engine.simulate_market_fill(
            self.live, currency=currency, side=fill_side,
            quantity=quantity,
        )
        if fill_price <= 0:
            return {"error": "No liquidity in order book"}

        notional = fill_price * quantity * effective_leverage
        if notional < 100:
            return {"error": f"Order notional below minimum ($100). Got ${notional:.2f}"}

        required_margin = Decimal(str(fill_price)) * Decimal(str(quantity)) / Decimal(effective_leverage)
        fee = engine.compute_fee(
            price=Decimal(str(fill_price)),
            quantity=Decimal(str(quantity)),
            fee_pct=self.account.taker_fee_pct,
        )

        with transaction.atomic():
            account = type(self.account).objects.select_for_update().get(pk=self.account.pk)
            if account.current_balance < required_margin + fee:
                return {"error": "Insufficient balance"}
            account.current_balance = account.current_balance - fee
            account.save(update_fields=["current_balance", "updated_at"])
            self.account.current_balance = account.current_balance

            position = PaperPosition.objects.create(
                account=account, symbol=symbol, side=side,
                quantity=Decimal(str(quantity)),
                entry_price=Decimal(str(fill_price)),
                leverage=effective_leverage,
                stop_loss_price=(
                    Decimal(str(stop_loss_price)) if stop_loss_price is not None else None
                ),
                take_profit_price=(
                    Decimal(str(take_profit_price)) if take_profit_price is not None else None
                ),
                status=PaperPosition.Status.OPEN,
                fees_paid=fee,
            )

        return {
            "main_order_id": f"paper-{uuid.uuid4().hex[:12]}",
            "symbol": symbol,
            "side": side,
            "quantity": float(quantity),
            "stop_loss_order_id": f"paper-sl-{position.id.hex[:12]}",
            "stop_loss_price": float(stop_loss_price),
            "take_profit_order_id": (
                f"paper-tp-{position.id.hex[:12]}" if take_profit_price is not None else None
            ),
            "take_profit_price": (
                float(take_profit_price) if take_profit_price is not None else None
            ),
        }
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest services/tests/test_paper_binance_client.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/paper_binance_client.py services/tests/test_paper_binance_client.py
git commit -m "feat: paper client open_long/open_short with fees and notional check"
```

---

## Task 10: `PaperBinanceClient` — close_position, _force_close, remaining read methods

**Files:**
- Modify: `services/paper_binance_client.py`
- Modify: `services/tests/test_paper_binance_client.py`

- [ ] **Step 1: Write failing tests**

Append to `services/tests/test_paper_binance_client.py`:

```python
class TestClosePosition(PaperBinanceClientTestBase):
    def test_no_position_returns_status(self):
        result = self.client.close_position("BTC")
        assert result == {"status": "NO_POSITION"}

    def test_close_long_in_profit_increases_balance(self):
        # Open a long at entry=90 first (use raw creation to skip fees)
        PaperPosition.objects.create(
            account=self.account, symbol="BTCUSDT", side="LONG",
            quantity=Decimal("1"), entry_price=Decimal("90"),
            leverage=10, status="OPEN",
        )
        # mocked mark price is 100; sell walks bids at 99
        self.live.get_order_book_depth.return_value = {
            "top_bids": [(99.0, 100.0)],
            "top_asks": [(100.0, 100.0)],
        }
        result = self.client.close_position("BTC")
        assert "error" not in result
        pos = PaperPosition.objects.get(account=self.account)
        assert pos.status == "CLOSED"
        assert pos.close_reason == "MANUAL"
        # PnL = (99-90)*1 = 9, minus close fee = 99*1*0.04/100 = 0.0396
        self.account.refresh_from_db()
        # balance = 1000 + 9 - 0.0396 = 1008.9604
        assert self.account.current_balance == pytest.approx(Decimal("1008.9604"), abs=0.0001)


class TestGetDailyPnl(PaperBinanceClientTestBase):
    def test_no_trades(self):
        pnl = self.client.get_daily_pnl()
        assert pnl["trade_count"] == 0
        assert pnl["win_rate"] == 0
        assert pnl["daily_realized_pnl"] == 0


class TestCancelAllOrders(PaperBinanceClientTestBase):
    def test_noop_returns_success(self):
        result = self.client.cancel_all_open_orders(symbol="BTCUSDT")
        assert result["cancelled_count"] == 0
```

- [ ] **Step 2: Run tests, verify failures**

```bash
pytest services/tests/test_paper_binance_client.py::TestClosePosition services/tests/test_paper_binance_client.py::TestGetDailyPnl services/tests/test_paper_binance_client.py::TestCancelAllOrders -v
```
Expected: FAIL.

- [ ] **Step 3: Implement the remaining methods**

Append to `services/paper_binance_client.py` inside `PaperBinanceClient`:

```python
    def close_position(self, currency: str) -> dict:
        from tradings.models import PaperPosition

        from services.paper_fill_engine import PaperFillEngine

        symbol = f"{currency.upper()}USDT"
        position = PaperPosition.objects.filter(
            account=self.account, symbol=symbol,
            status=PaperPosition.Status.OPEN,
        ).first()
        if position is None:
            return {"status": "NO_POSITION"}

        engine = PaperFillEngine()
        fill_side = "SELL" if position.side == "LONG" else "BUY"
        price = engine.simulate_market_fill(
            self.live, currency=currency, side=fill_side,
            quantity=float(position.quantity),
        )
        if price <= 0:
            return {"error": "No liquidity to close"}
        self._force_close(position, close_price=price, reason="MANUAL")
        return {
            "status": "CLOSED",
            "orderId": f"paper-close-{uuid.uuid4().hex[:12]}",
            "symbol": symbol,
            "side": fill_side,
            "quantity": float(position.quantity),
            "close_price": float(price),
        }

    def _force_close(self, position, close_price: float, reason: str):
        """
        Settle a position to the account: deduct close fee, compute realized PnL,
        update balance, mark the PaperPosition as CLOSED. Used by both
        close_position and PaperFillEngine.scan_and_close_triggered.
        """
        from django.db import transaction
        from django.utils import timezone as dj_tz
        from tradings.models import PaperAccount, PaperPosition

        from services.paper_fill_engine import PaperFillEngine

        engine = PaperFillEngine()
        sign = 1 if position.side == "LONG" else -1
        gross_pnl = (Decimal(str(close_price)) - position.entry_price) \
            * position.quantity * Decimal(sign)
        close_fee = engine.compute_fee(
            price=Decimal(str(close_price)),
            quantity=position.quantity,
            fee_pct=self.account.taker_fee_pct,
        )
        net_pnl = gross_pnl - close_fee

        with transaction.atomic():
            account = PaperAccount.objects.select_for_update().get(pk=self.account.pk)
            if reason == "LIQUIDATION":
                # Lose the entire initial margin, ignore net_pnl
                initial_margin = position.entry_price * position.quantity \
                    / Decimal(max(position.leverage, 1))
                account.current_balance = account.current_balance - initial_margin
                net_pnl = -initial_margin
            else:
                account.current_balance = account.current_balance + net_pnl
            account.save(update_fields=["current_balance", "updated_at"])
            self.account.current_balance = account.current_balance

            position.status = PaperPosition.Status.CLOSED
            position.closed_at = dj_tz.now()
            position.close_price = Decimal(str(close_price))
            position.close_reason = reason
            position.realized_pnl = net_pnl
            position.fees_paid = position.fees_paid + close_fee
            position.save(update_fields=[
                "status", "closed_at", "close_price", "close_reason",
                "realized_pnl", "fees_paid", "updated_at",
            ])

    def get_daily_pnl(self, include_unrealized: bool = True) -> dict:
        from datetime import datetime, time, timezone

        from tradings.models import PaperPosition

        today_start = datetime.combine(
            datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc,
        )
        closed = PaperPosition.objects.filter(
            account=self.account,
            status=PaperPosition.Status.CLOSED,
            closed_at__gte=today_start,
        )
        realized = float(sum((p.realized_pnl or Decimal("0")) for p in closed))
        winning = sum(1 for p in closed if (p.realized_pnl or 0) > 0)
        total = closed.count()
        unrealized = 0.0
        if include_unrealized:
            unrealized = self.get_futures_balance()["total_unrealized_pnl"]
        return {
            "daily_realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_daily_pnl": realized + unrealized,
            "trade_count": total,
            "winning_trades": winning,
            "losing_trades": total - winning,
            "win_rate": (winning / total * 100) if total > 0 else 0,
        }

    def get_recent_trades(self, currency: str, limit: int = 10) -> list:
        from tradings.models import PaperPosition

        symbol = f"{currency.upper()}USDT"
        closed = PaperPosition.objects.filter(
            account=self.account, symbol=symbol,
            status=PaperPosition.Status.CLOSED,
        ).order_by("-closed_at")[:limit]
        return [
            {
                "symbol": p.symbol,
                "trade_id": str(p.id),
                "order_id": f"paper-{p.id.hex[:12]}",
                "side": "SELL" if p.side == "LONG" else "BUY",
                "price": float(p.close_price or 0),
                "quantity": float(p.quantity),
                "realized_pnl": float(p.realized_pnl or 0),
                "commission": float(p.fees_paid),
                "commission_asset": "USDT",
                "time": int((p.closed_at or p.opened_at).timestamp() * 1000),
                "is_maker": False,
            }
            for p in closed
        ]

    def cancel_all_open_orders(self, symbol: str = None) -> dict:
        """Paper SL/TP live as position fields, not separate orders — no-op."""
        return {"cancelled_count": 0, "orders": []}
```

- [ ] **Step 4: Run all paper-client tests**

```bash
pytest services/tests/test_paper_binance_client.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/paper_binance_client.py services/tests/test_paper_binance_client.py
git commit -m "feat: paper client close_position, daily_pnl, force_close settlement"
```

---

## Task 11: Contract parity tests (live vs paper)

Ensure that `PaperBinanceClient` and `BinanceClient` expose the same public methods with the same signatures, and that their return dicts share key shapes. This is a safety net against drift.

**Files:**
- Create: `services/tests/test_paper_client_contract.py`

- [ ] **Step 1: Write the failing test**

Create `services/tests/test_paper_client_contract.py`:

```python
"""Contract parity tests: PaperBinanceClient must match BinanceClient's
public API surface and return-value shapes where applicable."""

import inspect

from services.binance_client import BinanceClient
from services.paper_binance_client import PaperBinanceClient


PUBLIC_METHODS = [
    "get_market_data",
    "get_order_book_depth",
    "get_available_futures_symbols",
    "get_futures_balance",
    "get_all_open_positions",
    "get_open_position",
    "get_daily_pnl",
    "get_recent_trades",
    "set_leverage",
    "open_long_position",
    "open_short_position",
    "close_position",
    "cancel_all_open_orders",
]


def test_paper_client_has_all_public_methods():
    """Every public BinanceClient method also exists on PaperBinanceClient."""
    for name in PUBLIC_METHODS:
        assert hasattr(BinanceClient, name), f"BinanceClient missing {name}"
        assert hasattr(PaperBinanceClient, name), \
            f"PaperBinanceClient missing {name} — interface drift"


def test_public_method_signatures_match():
    """Parameter names match between live and paper for each method (ignoring self)."""
    for name in PUBLIC_METHODS:
        live_sig = inspect.signature(getattr(BinanceClient, name))
        paper_sig = inspect.signature(getattr(PaperBinanceClient, name))
        live_params = [p for p in live_sig.parameters if p != "self"]
        paper_params = [p for p in paper_sig.parameters if p != "self"]
        assert live_params == paper_params, (
            f"Signature drift on {name}: live={live_params} paper={paper_params}"
        )
```

- [ ] **Step 2: Run the test and verify it passes**

```bash
cd /Users/gastonzarate/Documents/Code/opentrading
pytest services/tests/test_paper_client_contract.py -v
```
Expected: both tests PASS. If any fails, fix the method signature on `PaperBinanceClient` to match the live client (e.g. default values, parameter order).

- [ ] **Step 3: Commit**

```bash
git add services/tests/test_paper_client_contract.py
git commit -m "test: add contract parity tests between live and paper clients"
```

---

## Task 12: Scheduler — register `paper_trading_job` behind feature flag

**Files:**
- Modify: `apps/tradings/scheduler.py`
- Modify: `apps/genflows/trading_futures/binance_tools.py` — branch on `self.mode` when recording operations (previously deferred from Task 1)

- [ ] **Step 1: Make `BinanceTools` write to `PaperOperation` when in paper mode**

In `apps/genflows/trading_futures/binance_tools.py`, replace the three internal methods (`_open_long_position`, `_open_short_position`, `_close_position`) that currently call `TradingOperation.objects.create(...)` directly. Introduce a helper that picks the right model at the top of the class, just below `__init__`:

```python
    def _operation_model(self):
        if self.mode == "PAPER":
            from tradings.models import PaperOperation
            return PaperOperation
        from tradings.models import TradingOperation
        return TradingOperation

    def _paper_account(self):
        """Return the active PaperAccount when in paper mode, else None."""
        if self.mode != "PAPER":
            return None
        from tradings.models import PaperAccount
        return PaperAccount.objects.filter(is_active=True).first()
```

Then in each of `_open_long_position`, `_open_short_position`, `_close_position`, replace every `TradingOperation` reference with `Op = self._operation_model()` and `Op.OperationType...`. For paper mode also set `account=self._paper_account()` on the create call. Example for `_open_long_position`:

```python
def _open_long_position(self, currency: str, quantity: float,
                        stop_loss_price: float = None,
                        take_profit_price: float = None,
                        leverage: int = None) -> dict:
    Op = self._operation_model()
    create_kwargs = dict(
        operation_type=Op.OperationType.OPEN_LONG,
        currency=currency,
        quantity=quantity,
        leverage=leverage,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        status=Op.Status.PENDING,
    )
    if self.mode == "PAPER":
        create_kwargs["account"] = self._paper_account()
    operation = Op.objects.create(**create_kwargs)
    try:
        result = self.binance_client.open_long_position(
            currency=currency, quantity=quantity,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            leverage=leverage,
        )
        operation.status = Op.Status.SUCCESS
        operation.result_data = result
        operation.main_order_id = result.get("main_order_id")
        operation.stop_loss_order_id = result.get("stop_loss_order_id")
        operation.take_profit_order_id = result.get("take_profit_order_id")
        operation.save()
        return result
    except Exception as e:
        operation.status = Op.Status.ERROR
        operation.error_message = str(e)
        operation.save()
        raise e
```

Apply the same pattern to `_open_short_position` and `_close_position`.

- [ ] **Step 2: Add paper job to the scheduler**

Open `apps/tradings/scheduler.py` and replace the module-level `execute_workflow` / `run_trading_workflow` section to parameterize by mode, plus add the paper job. Replace the whole body of the file with:

```python
import asyncio
import logging
import os
import time

import nest_asyncio
from langfuse import get_client
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from tradings.models import TradingWorkflowExecution

from apps.genflows.trading_futures.workflow import TradingFuturesWorkflow
from services.binance_client import BinanceClient

nest_asyncio.apply()
logger = logging.getLogger(__name__)


async def _execute_workflow(binance_client, mode: str):
    LlamaIndexInstrumentor().instrument()
    langfuse = get_client()
    trace_id = langfuse.create_trace_id()
    # pylint: disable=not-context-manager
    with langfuse.start_as_current_span(
        name=f"trading-futures-workflow-{mode.lower()}",
        trace_context={"trace_id": trace_id},
    ):
        langfuse.update_current_trace(
            user_id="scheduler",
            session_id=f"scheduled-{mode.lower()}-{trace_id}",
        )
        workflow = TradingFuturesWorkflow(
            timeout=480, binance_client=binance_client, mode=mode,
        )
        logger.info("✅ %s workflow initialized", mode)
        handler = workflow.run(currencies=["BTC", "ETH", "BFUSD", "BNB", "USDC"])
    langfuse.flush()
    return await handler


def _run(binance_client, mode: str):
    start_time = time.time()
    result = None
    error = None
    try:
        result = asyncio.run(_execute_workflow(binance_client, mode))
    except Exception as e:
        error = e
        logger.error("❌ Error in %s workflow: %s", mode, e, exc_info=True)
    finally:
        execution_duration = time.time() - start_time
        try:
            if result:
                execution = TradingWorkflowExecution.save_from_workflow_result(
                    result=result, execution_duration=execution_duration,
                    error=error, mode=mode,
                )
                logger.info(
                    "💾 %s execution saved: %s status=%s duration=%.2fs",
                    mode, execution.id, execution.status, execution_duration,
                )
            elif error:
                execution = TradingWorkflowExecution(
                    status=TradingWorkflowExecution.Status.ERROR,
                    mode=mode,
                    execution_duration=execution_duration,
                    currencies=[], balance_info={}, market_data={},
                    open_positions=[], daily_pnl={}, system_prompt="",
                    error_message=str(error),
                )
                execution.save()
                logger.error("💾 %s error execution saved: %s", mode, execution.id)
        except Exception as db_error:
            logger.error("❌ Failed to save %s execution: %s",
                         mode, db_error, exc_info=True)
        logger.info("✅ %s workflow execution finished", mode)


def run_trading_workflow():
    """Live trading workflow job (APScheduler entry point)."""
    _run(BinanceClient(), mode="LIVE")


def run_paper_trading_workflow():
    """Paper trading workflow job (APScheduler entry point)."""
    from tradings.models import PaperAccount

    from services.paper_binance_client import PaperBinanceClient
    from services.paper_fill_engine import PaperFillEngine

    account = PaperAccount.objects.filter(is_active=True).first()
    if account is None:
        logger.warning("PAPER_TRADING_ENABLED but no active PaperAccount — skipping")
        return

    live_client = BinanceClient()
    paper_client = PaperBinanceClient(account, live_client)
    # Close SL/TP/liquidations that triggered in the previous minute first.
    try:
        PaperFillEngine().scan_and_close_triggered(paper_client, account)
    except Exception as e:
        logger.error("❌ PaperFillEngine scan failed: %s", e, exc_info=True)
    _run(paper_client, mode="PAPER")


def paper_trading_enabled() -> bool:
    return os.getenv("PAPER_TRADING_ENABLED", "false").lower() == "true"
```

- [ ] **Step 3: Register the paper job in `TradingsConfig.ready()`**

Open `apps/tradings/apps.py`. Find the block that ends with `scheduler.start()` (around line 52). Immediately **before** `scheduler.start()`, insert:

```python
from apps.tradings.scheduler import paper_trading_enabled, run_paper_trading_workflow

if paper_trading_enabled():
    scheduler.add_job(
        run_paper_trading_workflow,
        "interval",
        minutes=10,  # same cadence as live
        id="paper_trading_workflow",
        name="Paper Trading Workflow",
        replace_existing=True,
        misfire_grace_time=30,
        coalesce=True,
        max_instances=1,
        next_run_time=datetime.now(timezone.utc),
    )
    logger.info("🧪 Paper trading job registered (interval=10min)")
```

The existing `datetime` / `timezone` imports at line 34 are already in scope. The live job uses `minutes=10` in the real config — the paper job matches it.

- [ ] **Step 4: Document the env flag**

Open `env.local` and append:

```
# Paper trading (demo mode with virtual balance)
PAPER_TRADING_ENABLED=false
```

- [ ] **Step 5: Smoke-check the wiring**

Run (with the flag off):
```bash
cd /Users/gastonzarate/Documents/Code/opentrading
PAPER_TRADING_ENABLED=false python -c "from apps.tradings.scheduler import paper_trading_enabled; print(paper_trading_enabled())"
```
Expected: `False`.

Then with the flag on:
```bash
PAPER_TRADING_ENABLED=true python -c "from apps.tradings.scheduler import paper_trading_enabled; print(paper_trading_enabled())"
```
Expected: `True`.

- [ ] **Step 6: Commit**

```bash
git add apps/tradings/scheduler.py apps/tradings/apps.py apps/genflows/trading_futures/binance_tools.py env.local
git commit -m "feat: register paper trading scheduler job behind PAPER_TRADING_ENABLED flag"
```

---

## Task 13: Django admin — paper models, reset action, mode filter

**Files:**
- Modify: `apps/tradings/admin.py`

- [ ] **Step 1: Register `PaperAccount`, `PaperPosition`, `PaperOperation` admins + reset action**

Append to `apps/tradings/admin.py` (below the existing `TradingWorkflowExecutionAdmin`):

```python
from tradings.models import PaperAccount, PaperOperation, PaperPosition


@admin.register(PaperAccount)
class PaperAccountAdmin(admin.ModelAdmin):
    list_display = [
        "name", "current_balance", "initial_balance",
        "pnl_total", "is_active", "created_at",
    ]
    list_filter = ["is_active"]
    readonly_fields = ["id", "created_at", "updated_at", "last_scan_at"]
    actions = ["reset_balance"]

    def pnl_total(self, obj):
        delta = obj.current_balance - obj.initial_balance
        color = "green" if delta >= 0 else "red"
        return format_html('<span style="color:{};">${:.2f}</span>', color, float(delta))
    pnl_total.short_description = "PnL (total)"

    @admin.action(description="Reset balance and clear paper history")
    def reset_balance(self, request, queryset):
        for account in queryset:
            PaperPosition.objects.filter(account=account).delete()
            PaperOperation.objects.filter(account=account).delete()
            account.current_balance = account.initial_balance
            account.last_scan_at = None
            account.save(update_fields=[
                "current_balance", "last_scan_at", "updated_at",
            ])
        self.message_user(request, f"Reset {queryset.count()} account(s).")


@admin.register(PaperPosition)
class PaperPositionAdmin(admin.ModelAdmin):
    list_display = [
        "symbol", "side", "quantity", "entry_price",
        "close_price", "status", "close_reason",
        "realized_pnl", "opened_at",
    ]
    list_filter = ["status", "close_reason", "side", "symbol", "account"]
    search_fields = ["symbol"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(PaperOperation)
class PaperOperationAdmin(admin.ModelAdmin):
    list_display = [
        "operation_type", "currency", "quantity", "leverage",
        "status", "created_at",
    ]
    list_filter = ["operation_type", "status", "currency", "account"]
    search_fields = ["currency", "error_message"]
    readonly_fields = [
        "id", "created_at", "updated_at", "result_data",
        "main_order_id", "stop_loss_order_id", "take_profit_order_id",
    ]
```

- [ ] **Step 2: Add `mode` filter to `TradingWorkflowExecutionAdmin`**

In `apps/tradings/admin.py`, find `TradingWorkflowExecutionAdmin.list_filter` (around line 46) and replace with:

```python
    list_filter = [
        "status",
        "mode",
        "created_at",
    ]
```

Also add `"mode"` to `list_display` just after `status_badge`:

```python
    list_display = [
        "created_at",
        "status_badge",
        "mode",
        "currencies_display",
        "balance_display",
        "pnl_display",
        "duration_display",
        "positions_count",
    ]
```

- [ ] **Step 3: Verify admin registration doesn't error**

Run:
```bash
cd /Users/gastonzarate/Documents/Code/opentrading
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add apps/tradings/admin.py
git commit -m "feat: register paper trading admins and add mode filter"
```

---

## Task 14: Dashboard mode selector

Extend the existing dashboard API/view to filter by mode. The HTML update adds a simple toggle.

**Files:**
- Modify: `apps/tradings/views/trading_workflow_execution.py`
- Modify: `index.html`

- [ ] **Step 1: Inspect the current view to locate where it queries executions**

Run:
```bash
cd /Users/gastonzarate/Documents/Code/opentrading
grep -n "TradingWorkflowExecution" apps/tradings/views/trading_workflow_execution.py
```

Read the file to find where it calls `TradingWorkflowExecution.objects.filter(...)` or `.latest(...)`. The change in Step 2 assumes a single primary query; adapt to the actual call sites.

- [ ] **Step 2: Accept `mode` query param and default to LIVE**

In `apps/tradings/views/trading_workflow_execution.py`, wherever the view pulls executions from the DB, apply:

```python
mode = request.GET.get("mode", "LIVE").upper()
if mode not in ("LIVE", "PAPER"):
    mode = "LIVE"
# existing queryset:
qs = TradingWorkflowExecution.objects.filter(mode=mode)
# ...continue existing logic on `qs`
```

If the view currently uses `TradingWorkflowExecution.objects.all()` or no filter at all, add `.filter(mode=mode)` to every call that reads executions.

- [ ] **Step 3: Add a mode selector to `index.html`**

Open `index.html` and add at the top of the primary container (near the header, before any KPI widgets):

```html
<div class="mode-selector" style="margin: 1rem 0; font-family: system-ui;">
  <label style="margin-right: 0.5rem;">Mode:</label>
  <button id="mode-live" class="mode-btn">LIVE</button>
  <button id="mode-paper" class="mode-btn">PAPER</button>
</div>
<script>
  (function () {
    const params = new URLSearchParams(location.search);
    const current = (params.get("mode") || "LIVE").toUpperCase();
    document.getElementById("mode-live").style.fontWeight =
      current === "LIVE" ? "bold" : "normal";
    document.getElementById("mode-paper").style.fontWeight =
      current === "PAPER" ? "bold" : "normal";
    document.getElementById("mode-live").onclick = () => {
      params.set("mode", "LIVE");
      location.search = params.toString();
    };
    document.getElementById("mode-paper").onclick = () => {
      params.set("mode", "PAPER");
      location.search = params.toString();
    };
  })();
</script>
```

If the dashboard fetches data via `fetch("/api/...")`, add `?mode=${currentMode}` to each fetch URL in the existing JS so the backend filter takes effect.

- [ ] **Step 4: Manual smoke check**

Start the server:
```bash
cd /Users/gastonzarate/Documents/Code/opentrading
python manage.py runserver
```
Visit `http://localhost:8000/?mode=paper` and `http://localhost:8000/?mode=live`. Verify that no errors are thrown and that the selector toggles the URL. (Paper data will be empty until the paper job runs for the first time.)

- [ ] **Step 5: Commit**

```bash
git add apps/tradings/views/trading_workflow_execution.py index.html
git commit -m "feat: add mode selector to dashboard (LIVE vs PAPER)"
```

---

## Task 15: End-to-end integration test

Verify the workflow can complete with a `PaperBinanceClient` against a real `PaperAccount` in a test DB, with a mocked AI agent.

**Files:**
- Create: `apps/tradings/tests/__init__.py`
- Create: `apps/tradings/tests/test_paper_workflow.py`

- [ ] **Step 1: Create the test package**

Create `apps/tradings/tests/__init__.py` with a single empty line.

- [ ] **Step 2: Write the integration test**

Create `apps/tradings/tests/test_paper_workflow.py`:

```python
"""End-to-end integration test for the paper trading path.

Runs open → close on PaperBinanceClient against a real PaperAccount in a
test database. Does not exercise the LLM agent (that's covered by the
live workflow tests elsewhere)."""

from decimal import Decimal
from unittest.mock import MagicMock

from django.test import TestCase

from services.paper_binance_client import PaperBinanceClient
from services.paper_fill_engine import PaperFillEngine
from tradings.models import PaperAccount, PaperPosition


class TestPaperClientRoundTrip(TestCase):
    def setUp(self):
        self.account = PaperAccount.objects.create(
            name="integration",
            initial_balance=Decimal("1000"),
            current_balance=Decimal("1000"),
            is_active=True,
        )
        self.live = MagicMock()
        # Price starts at 100 (entry). Mark price drifts to 110 (profit for long).
        self.live.get_market_data.return_value = {"current_price": 100.0}
        self.live.get_order_book_depth.return_value = {
            "top_bids": [(99.0, 100.0)],
            "top_asks": [(100.0, 100.0)],
        }
        self.client = PaperBinanceClient(self.account, self.live)

    def test_open_long_check_unrealized_then_close(self):
        # Open long 1 @ ~100, lev 10, notional=1000
        result = self.client.open_long_position(
            currency="BTC", quantity=1.0,
            stop_loss_price=95.0, take_profit_price=110.0, leverage=10,
        )
        assert "error" not in result, result
        # Verify balance reflects open fee
        self.account.refresh_from_db()
        assert self.account.current_balance < Decimal("1000")
        assert self.account.current_balance > Decimal("999")

        # Move mark to 105, check unrealized pnl = +5
        self.live.get_market_data.return_value = {"current_price": 105.0}
        balance = self.client.get_futures_balance()
        assert balance["total_unrealized_pnl"] == \
            __import__("pytest").approx(5.0, abs=0.01)

        # Close position at bid 104
        self.live.get_order_book_depth.return_value = {
            "top_bids": [(104.0, 100.0)],
            "top_asks": [(105.0, 100.0)],
        }
        close = self.client.close_position("BTC")
        assert close["status"] == "CLOSED"

        self.account.refresh_from_db()
        assert self.account.current_balance > Decimal("1000"), \
            "Paper account should be in profit after close"
        assert PaperPosition.objects.filter(
            account=self.account, status="OPEN",
        ).count() == 0


class TestFillEngineClosesOnStopLoss(TestCase):
    def setUp(self):
        self.account = PaperAccount.objects.create(
            name="sl-test",
            initial_balance=Decimal("1000"),
            current_balance=Decimal("1000"),
            is_active=True,
        )
        self.live = MagicMock()
        self.live.get_market_data.return_value = {"current_price": 100.0}
        # Simulated 1m candle where low=89 breached a long SL at 95
        self.live.client.get_klines.return_value = [
            # [openTime, open, high, low, close, volume, closeTime, ...]
            [0, "100", "102", "89", "92", "10", 60000, "0", 0, "0", "0", "0"],
        ]
        self.client = PaperBinanceClient(self.account, self.live)
        PaperPosition.objects.create(
            account=self.account, symbol="BTCUSDT", side="LONG",
            quantity=Decimal("1"), entry_price=Decimal("100"),
            leverage=10, stop_loss_price=Decimal("95"),
            take_profit_price=Decimal("120"), status="OPEN",
        )

    def test_scan_triggers_stop_loss(self):
        PaperFillEngine().scan_and_close_triggered(self.client, self.account)
        pos = PaperPosition.objects.get(account=self.account)
        assert pos.status == "CLOSED"
        assert pos.close_reason == "STOP_LOSS"
        assert pos.close_price == Decimal("95")
```

- [ ] **Step 3: Run the integration tests**

```bash
cd /Users/gastonzarate/Documents/Code/opentrading
pytest apps/tradings/tests/test_paper_workflow.py -v
```
Expected: both tests PASS.

- [ ] **Step 4: Run the full test suite to verify nothing regressed**

```bash
pytest services/tests/test_paper_fill_engine.py services/tests/test_paper_binance_client.py services/tests/test_paper_client_contract.py apps/tradings/tests/test_paper_workflow.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/tradings/tests/
git commit -m "test: add end-to-end paper workflow integration tests"
```

---

## Final checklist (executor)

After all 15 tasks:

- [ ] `pytest services/tests/test_paper_fill_engine.py services/tests/test_paper_binance_client.py services/tests/test_paper_client_contract.py apps/tradings/tests/test_paper_workflow.py -v` — all pass
- [ ] `python manage.py check` — no issues
- [ ] `python manage.py migrate` — no pending migrations
- [ ] Create a `PaperAccount` via Django admin with `is_active=True` and an `initial_balance` (e.g. $1000)
- [ ] Set `PAPER_TRADING_ENABLED=true` in `.env`
- [ ] Restart the server and watch logs for `🧪 Paper trading job registered` and subsequent `PAPER workflow initialized` messages each minute
- [ ] Visit `http://localhost:8000/?mode=paper` and confirm the dashboard renders without errors

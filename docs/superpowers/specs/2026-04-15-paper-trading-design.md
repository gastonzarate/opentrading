# Paper Trading Mode — Design Spec

**Date:** 2026-04-15
**Status:** Design approved, pending implementation plan

## Purpose

Add a persistent paper trading mode that runs in parallel with the live bot, using a virtual USDT balance, real market data from Binance, and realistic fill simulation (fees, order-book slippage, intra-minute stop-loss / take-profit detection).

The goal is to evaluate the live strategy continuously without risking real capital — the paper bot runs the **same** workflow, prompt, and currencies as the live bot, and its performance is visible alongside the live one in the Django admin and HTML dashboard.

## Scope

**In scope:**
- A single persistent paper account with configurable initial balance, active/paused flag, and configurable taker/maker fees.
- Parallel execution with the live bot via two scheduler jobs using the same `TradingFuturesWorkflow` class with different clients injected.
- Realistic fill simulation: order-book-walking slippage on market orders, taker fees, intra-minute SL/TP detection via 1m klines, liquidation at -95% of initial margin.
- Persistence of paper positions, operations, and workflow executions so history is auditable.
- Django admin integration and a mode selector in the HTML dashboard to view paper or live metrics.

**Out of scope (explicitly deferred):**
- Multiple paper accounts with different prompts/currencies/risk settings. The data model leaves room for this, but the feature is single-account for now.
- Maker-fee simulation for limit orders (the agent currently only uses market orders; the fee field exists on the model but is unused).
- Funding-rate application to open positions.
- Simulating order rejections, latency, or partial fills beyond what order-book-walking already produces.
- Exact Binance maintenance-margin calculation for liquidation (we use a -95% heuristic).

## Architecture

```
┌─────────────────────┐       ┌─────────────────────┐
│   APScheduler       │       │   APScheduler       │
│   live_job (1 min)  │       │   paper_job (1 min) │
└──────────┬──────────┘       └──────────┬──────────┘
           │                             │
           ▼                             ▼
 TradingFuturesWorkflow      TradingFuturesWorkflow
   (same class, mode=LIVE)   (same class, mode=PAPER)
           │                             │
           ▼                             ▼
     BinanceClient              PaperBinanceClient
     (real API)                     │
                                    ├─► reads → delegate to BinanceClient
                                    └─► writes/state → PaperAccount + models

                              ┌──────────────────────┐
                              │  PaperFillEngine     │
                              │  (runs inside        │
                              │   paper_job before   │
                              │   the workflow)      │
                              │  - scans 1m klines   │
                              │  - triggers SL/TP    │
                              │  - liquidates        │
                              └──────────────────────┘
```

Two APScheduler jobs run every minute. The live job uses the real `BinanceClient`. The paper job first runs `PaperFillEngine.scan_and_close_triggered` to close any positions whose SL/TP/liquidation was hit during the previous minute, then runs the same `TradingFuturesWorkflow` with a `PaperBinanceClient` injected. The workflow and tools are identical across modes — `TradingFuturesWorkflow` and `BinanceTools` must be refactored to accept the client via dependency injection.

A feature flag `PAPER_TRADING_ENABLED` (default `false`) gates registration of the paper job so existing deployments are unaffected until the feature is explicitly enabled.

## Data model

New Django models in `apps/tradings/models/`:

### `PaperAccount`
- `id` (UUID, PK)
- `name` (str)
- `initial_balance` (Decimal, USDT) — starting wallet balance
- `current_balance` (Decimal, USDT) — live wallet balance, excludes unrealized PnL
- `is_active` (bool) — if false, scheduler does not register the paper job
- `taker_fee_pct` (Decimal, default 0.04) — percentage, not fraction
- `maker_fee_pct` (Decimal, default 0.02) — reserved for future limit-order support
- `last_scan_at` (DateTime, nullable) — watermark used by `PaperFillEngine` for idempotent scans
- `created_at` / `updated_at`

The model is designed as a collection (FKs elsewhere point to it) so future expansion to multiple accounts does not require a migration.

### `PaperPosition`
- `id` (UUID, PK)
- `account` (FK → `PaperAccount`)
- `symbol` (str, e.g. `"BTCUSDT"`)
- `side` (`"LONG" | "SHORT"`)
- `quantity` (Decimal)
- `entry_price` (Decimal) — price after slippage at open
- `leverage` (int)
- `stop_loss_price` (Decimal, nullable) — mandatory at open by `PaperBinanceClient`, but nullable in DB so the engine can clear it on close
- `take_profit_price` (Decimal, nullable)
- `status` (`"OPEN" | "CLOSED"`)
- `opened_at` / `closed_at`
- `close_price` (Decimal, nullable)
- `close_reason` (`"STOP_LOSS" | "TAKE_PROFIT" | "MANUAL" | "LIQUIDATION"`, nullable)
- `realized_pnl` (Decimal, nullable) — net of fees
- `fees_paid` (Decimal, default 0) — cumulative open + close fees

### `PaperOperation`
Mirror of the existing `TradingOperation` model but with a FK to `PaperAccount` instead of the live-trade context. Tracks OPEN_LONG / OPEN_SHORT / CLOSE_POSITION events with status and agent reasoning, so the admin shows paper decision history with the same UX as live.

### Change to existing `TradingWorkflowExecution`
Add `mode` field (`"LIVE" | "PAPER"`, default `"LIVE"`) so the existing model can hold executions of both jobs. Chosen over duplicating the model — fewer migrations, the dashboard can filter by mode trivially.

## `PaperBinanceClient`

Location: `services/paper_binance_client.py`. Same public contract as `BinanceClient` so the workflow and `BinanceTools` cannot distinguish them.

### Constructor
```python
class PaperBinanceClient:
    def __init__(self, account: PaperAccount, live_client: BinanceClient):
        self.account = account
        self.live = live_client  # used only for market-data reads
```

### Method behavior

**Read-only methods delegated 1:1 to `self.live`:**
- `get_market_data(currency)`
- `get_order_book_depth(currency, limit)`
- `get_available_futures_symbols(quote_asset)`
- Internal helpers: `_get_klines`, `_calculate_indicators`, `_get_futures_metrics`

**Overridden methods operating on paper state:**

| Method | Behavior |
|---|---|
| `get_futures_balance()` | `total_wallet_balance = account.current_balance`. `total_unrealized_pnl` = sum of `(mark_price - entry_price) * quantity * sign` over open `PaperPosition` rows, using `self.live.get_market_data(currency).current_price` for each symbol. `available_balance = current_balance - used_margin` where `used_margin = sum(entry_price * quantity / leverage)`. Returns same schema as live. |
| `get_all_open_positions()` | Query `PaperPosition.objects.filter(account=account, status=OPEN)`. For each, compute `mark_price` and `unrealized_pnl` as above, then return the same dict shape as the live client — including `stop_loss_orders` / `take_profit_orders` arrays synthesized from the position's SL/TP fields so the agent sees consistent structure. |
| `get_open_position(currency)` | Return signed `positionAmt` from the open `PaperPosition` for that symbol (0 if none). |
| `open_long_position(currency, quantity, stop_loss_price, take_profit_price, leverage)` | Raise `ValueError` if `stop_loss_price is None`. Fetch execution price via `PaperFillEngine.simulate_market_fill(currency, BUY, quantity)`. Enforce minimum notional: if `quantity * price * leverage < 100` (USD), return `{"error": "Order notional below minimum ($100)"}` to mirror Binance's server-side rejection. Validate available margin; return `{"error": "Insufficient balance"}` if not enough. Compute fees, deduct from balance, create `PaperPosition(side=LONG, ...)`, create `PaperOperation(type=OPEN_LONG, status=SUCCESS)`. Return dict matching live shape (`main_order_id`, `stop_loss_order_id`, `take_profit_order_id` — synthesized UUIDs). |
| `open_short_position(...)` | Same as long, with `side=SHORT` and SELL direction for slippage simulation. Same minimum-notional enforcement. |
| `close_position(currency)` | Fetch open position; if none, return `{"status": "NO_POSITION"}`. Get close price via slippage simulation, compute realized PnL net of close fees, add to `account.current_balance`, mark position `CLOSED` with `close_reason=MANUAL`. |
| `set_leverage(currency, leverage)` | Stateful in-memory dict (mirrors Binance behavior where leverage is a per-symbol account setting). Next `open_*` call for that currency picks it up if `leverage` arg is not passed. |
| `get_daily_pnl(include_unrealized)` | Sum `realized_pnl` over `PaperPosition` closed today. Include unrealized from open positions if requested. Compute win rate, counts. |
| `get_recent_trades(currency, limit)` | Query closed `PaperPosition` rows for that symbol, ordered by `closed_at` desc. |
| `cancel_all_open_orders(symbol)` | No-op returning success. SL/TP are fields on the position, not separate orders. |

**Contract requirement:** every overridden method must return the same keys and types as the live client. This is verified by contract tests (see Testing).

## `PaperFillEngine`

Location: `services/paper_fill_engine.py`. Stateless helper whose methods take a `PaperBinanceClient` or `PaperAccount` as input.

### Slippage simulation (`simulate_market_fill`)
```
Input: currency, side (BUY|SELL), quantity
1. book = live_client.get_order_book_depth(currency, limit=50)
2. Walk the book on the relevant side (asks for BUY, bids for SELL):
   - Accumulate (price, qty) levels until total qty >= requested quantity
   - Compute VWAP over the consumed portion
3. If book depth is insufficient, use the worst available price and log a warning.
   Never fail the fill — the live API would also match at whatever price is available.
Output: fill_price (VWAP)
```

### Fees
- Taker fee on every market fill (open and close).
- `fee = price * quantity * account.taker_fee_pct / 100`
- Deducted from `account.current_balance` at open. Deducted from gross PnL at close (before adding to balance).
- Accumulated in `PaperPosition.fees_paid`.

### Intra-minute SL/TP detection (`scan_and_close_triggered`)
Runs at the start of every paper job, before the workflow.

```
For each open PaperPosition in account:
  klines = live_client._get_klines(position.symbol, "1m", limit=2)
  For each kline newer than account.last_scan_at:
    high, low, open, close = kline OHLC

    If position.side == LONG:
      sl_hit = (sl is not None) and (low <= sl)
      tp_hit = (tp is not None) and (high >= tp)
    Else (SHORT):
      sl_hit = (sl is not None) and (high >= sl)
      tp_hit = (tp is not None) and (low <= tp)

    If both hit in the same candle:
      # Conservative heuristic: whichever is closer to kline open triggers first
      first = sl if abs(open - sl) < abs(open - tp) else tp
    Elif sl_hit: first = sl
    Elif tp_hit: first = tp
    Else: continue

    Close position at exactly `first` (no slippage — simplification).
    Apply close fee, compute PnL, update balance, mark close_reason.
    Break out of kline loop for this position.

Update account.last_scan_at = max(kline.close_time processed).
```

**Known simplification:** real Binance stop-market orders fill at market price after trigger (may slip). We fill exactly at `stop_price`. This is slightly optimistic but far less distorting than missing the intra-minute hit entirely. Documented trade-off.

### Liquidation
Checked inside the same scan loop, before the SL/TP checks:
```
mark_price = live_client.get_market_data(symbol).current_price
unrealized = (mark - entry) * quantity * sign(side)
initial_margin = entry * quantity / leverage
if unrealized <= -0.95 * initial_margin:
  Close at mark_price, close_reason = LIQUIDATION
  Account loses the full initial_margin.
```

### Idempotency
`last_scan_at` on `PaperAccount` ensures that if the scheduler runs the scan twice for overlapping minutes (e.g. on retry), candles are not double-processed.

## Scheduler integration

`apps/tradings/scheduler.py` gains a second job registration, guarded by env flag:

```python
def start_scheduler():
    scheduler.add_job(live_trading_job, 'interval', minutes=1, id='live', ...)

    if os.getenv("PAPER_TRADING_ENABLED", "false").lower() == "true":
        account = PaperAccount.objects.filter(is_active=True).first()
        if account:
            scheduler.add_job(paper_trading_job, 'interval', minutes=1,
                              id='paper', kwargs={"account_id": account.id}, ...)

def paper_trading_job(account_id):
    account = PaperAccount.objects.get(id=account_id)
    live_client = BinanceClient()
    paper_client = PaperBinanceClient(account, live_client)
    PaperFillEngine().scan_and_close_triggered(paper_client, account)
    workflow = TradingFuturesWorkflow(client=paper_client, mode="PAPER")
    workflow.run()
```

**Refactor required:** `TradingFuturesWorkflow` and `BinanceTools` currently instantiate `BinanceClient()` internally. They must be changed to accept the client as a constructor argument. Affected files: `apps/genflows/trading_futures/workflow.py`, `apps/genflows/trading_futures/binance_tools.py`, `main.py`.

## Django admin and dashboard

### Admin (`apps/tradings/admin.py`)
- `PaperAccountAdmin` — list view with name, initial/current balance, total PnL (= current − initial), active flag. Custom action: **Reset balance** (restore `current_balance = initial_balance`, delete all `PaperPosition` and `PaperOperation` for that account, clear `last_scan_at`).
- `PaperPositionAdmin` — list with symbol, side, entry/close price, PnL, close_reason, timestamps. Filters by account, symbol, status.
- `PaperOperationAdmin` — mirror of `TradingOperationAdmin`.
- Update `TradingWorkflowExecutionAdmin` to expose the new `mode` field as a filter.

### Dashboard (`index.html` + `apps/tradings/views/`)
Add a **mode selector** (LIVE / PAPER) at the top of the dashboard. Every existing view endpoint accepts a `?mode=paper|live` query parameter and filters its data source accordingly:
- Balance / PnL / win-rate endpoints read from `PaperAccount` and `PaperPosition` when `mode=paper`.
- Market-data endpoints are mode-agnostic (same Binance data for both).
- Agent-reasoning / execution-history endpoints filter `TradingWorkflowExecution` by the `mode` field.

The UI is identical across modes — only the data source changes.

## Error handling

- **Real-client failures during paper ops**: market-data reads go to the real `BinanceClient`. If they fail, propagate the same exceptions the live workflow already handles. The agent's existing error paths cover this.
- **Insufficient virtual balance**: `open_*_position` returns `{"error": "Insufficient balance"}` matching the live error shape, so the agent reacts the same way it would to a real margin failure.
- **Empty / thin order book**: slippage walker uses the worst available price and logs a warning. Never fails.
- **Concurrent mutations on the account**: writes to `PaperAccount.current_balance` and `PaperPosition` rows are wrapped in `transaction.atomic()` with `select_for_update()`. With a single scheduler worker this is belt-and-suspenders, but it's cheap and guards against future parallelization.
- **Paper account missing or inactive at startup**: scheduler logs a warning and skips the paper job registration. Does not crash.
- **Scheduler retries / duplicate scans**: `last_scan_at` watermark on `PaperAccount` prevents double-processing of candles.

## Testing

Four test layers:

1. **Contract tests** (`services/tests/test_paper_client_contract.py`)
   Parametrized tests asserting that for every public method, `PaperBinanceClient` and `BinanceClient` return dicts with the same keys and compatible types. If someone changes the live client's return shape, this test fails and forces the paper client to stay in sync.

2. **Fill-engine unit tests** (`services/tests/test_paper_fill_engine.py`)
   With hand-crafted 1m-kline fixtures:
   - SL hit on LONG when `low <= sl`
   - TP hit on SHORT when `low <= tp`
   - Both-hit-same-candle resolution via the open-distance heuristic
   - Liquidation at -95% of initial margin
   - VWAP slippage across multiple order-book levels
   - Fees deducted correctly on open and close
   - Idempotency: second scan over the same window is a no-op

3. **Paper client unit tests** (`services/tests/test_paper_binance_client.py`)
   - Opening long/short creates `PaperPosition`, deducts fees, decrements balance
   - Missing `stop_loss_price` raises `ValueError`
   - Insufficient balance returns error dict
   - Notional below $100 returns error dict
   - Unrealized PnL calculated correctly under both LONG and SHORT
   - `set_leverage` is picked up by subsequent open calls

4. **Integration test** (`apps/tradings/tests/test_paper_workflow.py`)
   Run `TradingFuturesWorkflow` end-to-end with a real `PaperBinanceClient` against a test `PaperAccount` in a test DB. LLM agent is mocked to emit deterministic tool calls. Assert that `PaperOperation` and `PaperPosition` rows are created correctly and `current_balance` evolves as expected.

## Open questions / assumptions

- **Single paper account** — the active one is picked via `PaperAccount.objects.filter(is_active=True).first()`. If multiple are active, only the first (by creation order) runs. Acceptable under the current single-account scope.
- **Initial balance** — set at account creation via Django admin. Default suggested: $1000 USDT, but not enforced in code.
- **Funding rate** — not applied to open positions. Given BTC/ETH funding rates typically sit near ±0.01%/8h, the impact on strategy evaluation over days/weeks is small. Revisit if paper-vs-live divergence becomes noticeable.
- **Reset semantics** — "Reset balance" admin action deletes paper history for that account. If historical comparison is wanted, clone the account first (manual operation). No scheduled reset.

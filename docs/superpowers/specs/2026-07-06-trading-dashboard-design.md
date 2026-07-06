# Trading Dashboard Redesign — Design Spec

Date: 2026-07-06
Status: Approved (brainstorming)

## Goal
Replace the existing `index.html` dashboard (broken charts, confusing info) with a
brand-new single-view dashboard that shows, at a glance, **how the bot is doing right
now** and **how it has performed over time**, with polished ambient three.js effects
that never obstruct the data.

## Data sources (existing REST API, public/AllowAny, base = `{{ api_base_url }}`)
- `GET /executions/?page_size=N` — list (id, created_at, status, execution_duration,
  currencies, summary{total_balance, available_balance, daily_pnl, trade_count,
  win_rate, open_positions_count, has_error}). Time series for history.
- `GET /executions/{id}/` — full latest snapshot: balance_info, market_data per
  currency (price, ema_9/21, macd+signal, rsi, adx, **regime**, funding, oi, atr),
  open_positions (side, amount, entry, mark, liquidation_price, unrealized_pnl,
  leverage, margin_type, stop_loss_orders, take_profit_orders), daily_pnl,
  agent_response (markdown), strategy_for_next_execution, next_run_minutes, error.
- `GET /executions/statistics/` — total, success/error, success_rate, avg_duration,
  total_daily_pnl.
- `GET /operations/?page_size=N` — trades (operation_type long/short/close, currency,
  quantity, leverage, entry/stop/take prices, status, created_at).
- `GET /operations/statistics/` — counts by type, success_rate, top_currencies.

## Realtime
REST polling of the latest execution + stats every ~10s (bot cadence is minutes).
Show "last updated" and a countdown to the next run (from `next_run_minutes` +
last execution time). Pause polling when the tab is hidden.

## Information architecture (single scroll, top → bottom)
1. **Hero (three.js background)**: bot status (active/idle) + countdown to next run;
   Equity total (wallet + unrealized PnL); Today's PnL (large, color-coded); win rate.
   Circuit-breaker banner when daily loss approaches the configured limit.
2. **Live state**:
   - Open-position cards: side, size, entry vs mark, **liquidation-distance risk gauge**,
     unrealized PnL, leverage, SL/TP present. Empty state when flat.
   - Regime chips per symbol (BTC/ETH/BNB/SOL): TREND / RANGE / UNDEFINED + ADX.
3. **Performance (clean 2D charts)**: equity/PnL curve over executions; win-rate trend;
   drawdown; operations-by-type donut; decision cadence (minutes between runs).
4. **Agent brain**: latest reasoning (rendered markdown), strategy for next execution.
5. **Activity**: recent operations + recent executions with status.

## Visual / three.js concept
GPU particle/energy field behind the hero that reacts to bot state:
- Color: calm green when profitable / ranging; energizes and speeds up in trends;
  red turbulence on drawdown or circuit-breaker.
- Density/flow tied to today's PnL and open-position count.
- Subtle central flow (sphere/curl-noise) with bloom; sits behind the numbers.
- Graceful degradation: fewer particles / static gradient on mobile or if WebGL
  unavailable or `prefers-reduced-motion`.

## Tech approach
- Clean rebuild of `index.html` (served by Django `HomePageView`, template var
  `api_base_url`). Vanilla ES modules (no Vue). three.js (ESM via CDN/importmap) for
  the ambient background; Chart.js for the 2D data charts with careful, correct configs
  (the old failure was config, not the library). Dark theme.
- Components as small, single-purpose functions: `api` (fetch + poll), `state`
  (normalize latest execution + history), `hero`, `positions`, `regime`, `charts`,
  `brain`, `activity`, and `three-bg` (isolated, feature-detected).
- Accessibility: readable contrast, `prefers-reduced-motion` respected, charts have
  text fallbacks (numbers always shown alongside).

## Out of scope
- Auth (endpoints are public). Live websocket (polling is sufficient). Editing/controlling
  the bot from the UI (read-only dashboard).

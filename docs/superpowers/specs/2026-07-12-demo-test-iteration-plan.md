# Demo Test & Agent-Iteration Plan

Date: 2026-07-12
Status: In progress (Fase 0 e2e validated)

## Goal
Establish a repeatable test loop to run the trading agent on the Binance **demo**
(fake money) and iterate on its behaviour. The aim is a fast, grounded feedback
cycle — conclusions from data (persisted executions + the digest report), not vibes.

## What this test CAN and CAN'T tell us
- **CAN**: whether the machinery is reliable and the agent decides sensibly —
  loop runs without crashing, guardrails fire, regime gate respected, sizing/SL/TP
  correct, cadence sane, no API/tool errors. This is the iteration target.
- **CANNOT**: whether the strategy is profitable. A 1–2 day, 4-symbol,
  regime-gated run yields single-digit trades → PnL is pure variance noise.
  Do **not** read PnL as an edge verdict. Edge belongs to the offline backtest
  harness (`services/backtest_harness.py`) over months of data + parameter sweeps.
  The backtest already showed **negative expectancy** for the current strategy —
  so the demo validates plumbing + behaviour, while the strategy's edge is a
  separate (open) question for the backtest track.

## Model configuration
The trading agent's model is env-selectable via `TRADING_AGENT_MODEL`
(`apps/genflows/trading_futures/workflow.py:trading_agent_model()`):
`opus-4-8` | `sonnet-5` | `sonnet-4-6` | `haiku-4-5`. Default: `sonnet-5`.

Bedrock access status for this AWS account (us-east-2), as of 2026-07-12:

| Model | Bedrock id | Access |
|---|---|---|
| Sonnet 4.6 | `global.anthropic.claude-sonnet-4-6` | ✅ works |
| Haiku 4.5 | `global.anthropic.claude-haiku-4-5-20251001-v1:0` | ✅ works |
| Sonnet 5 | `global.anthropic.claude-sonnet-5` | ⛔ AccessDenied (AWS gate) |
| Opus 4.8 | `global.anthropic.claude-opus-4-8` | ⛔ AccessDenied (AWS gate) |
| Fable 5 | `global.anthropic.claude-fable-5` | ⛔ AccessDenied (AWS gate) |

Sonnet 5 / Opus 4.8 / Fable 5: Marketplace agreements accepted, everything
`AVAILABLE`, but invocation still denied ("contact AWS Sales"). Needs an AWS
Support/Sales entitlement review or the gradual per-account rollout — no
self-serve fix. **Use `TRADING_AGENT_MODEL=sonnet-4-6` until those are enabled.**

## Prerequisites (in `.env`, gitignored)
- `BINANCE_TESTNET=true` — routes the whole loop to the demo (fake money).
  ⚠️ `false` trades **real money** — only set consciously.
- `TRADING_AGENT_MODEL=sonnet-4-6` — the model that currently works on Bedrock.
- `BINANCE_DEMO_API_KEY` / `BINANCE_DEMO_API_SECRET` — demo credentials.
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION` — Bedrock.
- `MCP_TRENDRADAR_URL` (optional) — news tools; the flow degrades gracefully if unset.

## Fase 0 — Smoke run (~1h)
**Objective:** confirm the machinery runs reliably end-to-end. Not a performance
judgement — just that it *works*.

**Success criteria:**
- Loop self-schedules and runs multiple ticks without crashing.
- If the agent decides to trade: position opens on the demo with **SL + TP
  attached** (reduceOnly/closePosition), correct sizing (~1% risk), isolated margin.
- Guardrails fire where expected (regime gate, leverage cap, min-notional, daily-loss).
- Dashboard + DB reflect live state.

**How to run:** `docker compose up` (scheduler starts on boot, self-schedules via
`NEXT_RUN_MINUTES`). Watch the dashboard and `docker compose logs -f api`.

**Status (2026-07-12):** the core path is validated. A single end-to-end run on
the demo with Sonnet 4.6 completed in ~72s: balance gate → market data → regimes
(BTC/ETH RANGE, BNB UNDEFINED, SOL TREND) → agent reasoning → decision (no-op,
capital preservation) → cadence (30 min) → persisted to DB (SUCCESS), no errors.
Remaining: let it run ~1h across several ticks and, ideally, observe one real
demo order lifecycle (open → SL/TP → manage/close).

## Fase 1 — Bounded run (24h → 48h)
**Objective:** collect behaviour + ops data over a real window to iterate on.
Still **not** a PnL verdict.

**Metrics to review:**
- Regime gate respected? Every position had SL/TP? Sizing ≈ 1% risk?
- Trades/day and fee drag (over-trading / churn).
- Reasoning coherence vs. the data (hallucinations, ignored signals).
- News usage sanity.
- Ops: crashes, API/tool errors, latency per run, guardrail rollback events.
- Cadence: did `NEXT_RUN_MINUTES` make sense vs. actual gaps?

**How to review:** `docker compose run --rm api python manage.py trading_run_digest --last N --details`
(per-execution regime/action/reasoning, guardrail blocks, errors, cadence, plus
an aggregate summary and an issues bucket).

## Fase 2 — Review & iterate
Classify findings into buckets: **bugs · prompt/strategy · risk-config · model · ops**.
Change **one lever per round** (prompt OR `STRATEGY` risk config OR model) and
re-run, so the effect is attributable. Repeat.

The model swap is a first-class lever: once Sonnet 5 / Opus 4.8 access lands,
flip `TRADING_AGENT_MODEL` and compare behaviour against the Sonnet 4.6 baseline.

## Running a single execution (ad-hoc, no scheduler)
```
docker compose run --rm -e BINANCE_TESTNET=true -e TRADING_AGENT_MODEL=sonnet-4-6 \
  api python -c "import asyncio, os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.base'); django.setup(); \
  from apps.genflows.trading_futures.workflow import TradingFuturesWorkflow; \
  print(asyncio.run(TradingFuturesWorkflow(timeout=480).run(currencies=['BTC','ETH','BNB','SOL'])))"
```

## Out of scope
- Real-money trading (demo only until explicitly approved).
- Edge/profitability conclusions from the demo run (backtest's job).
- Changing the strategy itself during Fase 0/1 (that's Fase 2, one lever at a time).

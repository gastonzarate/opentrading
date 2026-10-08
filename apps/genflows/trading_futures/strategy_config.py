"""
Single source of truth for the trading strategy's numeric parameters.

These values are the deterministic risk guardrails of the bot. The ones that
protect capital (leverage cap, risk per trade, daily loss) are enforced in code
(the LLM cannot override them); the rest are injected into the agent prompt so
the model reasons with the same numbers the code enforces.

Rationale for the defaults is documented inline and backed by the strategy
review (Van Tharp 1-2% rule, fractional Kelly, ATR stops, leverage/liquidation
math, regime filtering). Change a value here and it propagates everywhere.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyConfig:
    # --- Leverage -----------------------------------------------------------
    # 10x liquidates on a 10% move, 20x on 5% — too tight for crypto intraday
    # and it makes the ATR stop sit beyond the liquidation price. Keep it low.
    default_leverage: int = 3
    max_leverage: int = 5

    # --- Position sizing ----------------------------------------------------
    # NOTE: TESTNET-AGGRESSIVE values (2026-08-11). The prudent production values
    # are risk_per_trade_pct=1.0 / max_portfolio_risk_pct=3.0 / max_daily_loss_pct=5.0
    # (Van Tharp 1-2% rule). We deliberately size UP on the demo account to make the
    # forward-test's dollar P&L bigger/faster to read. This does NOT improve the edge
    # (Sharpe/%-return are unchanged) — it only scales P&L and drawdown. DO NOT ship
    # these to a real-money account without reverting to the 1% / 3% / 5% guardrails.
    risk_per_trade_pct: float = 5.0
    # Aggregate cap across all open positions. LEARNING MODE (2026-08-14): widened
    # so ~8 concurrent positions at 5% risk each can be open (prod value: 3.0).
    max_portfolio_risk_pct: float = 40.0
    max_concurrent_positions: int = 8

    # --- Circuit breaker ----------------------------------------------------
    # Halt new positions once the day is down this much (kill-switch in code).
    # LEARNING MODE: widened so the day rarely halts and keeps generating trades
    # (testnet-only; prod value: 5.0).
    max_daily_loss_pct: float = 50.0

    # --- Exits --------------------------------------------------------------
    atr_stop_multiplier: float = 1.5
    tp1_atr_multiplier: float = 1.5
    tp2_atr_multiplier: float = 3.0
    # LEARNING MODE: relaxed from 2.0 so more setups qualify (prod value: 2.0).
    min_risk_reward: float = 1.0

    # --- Dynamic cadence ----------------------------------------------------
    # The agent decides when to run next (NEXT_RUN_MINUTES). The code clamps it:
    # SL/TP live on the exchange (reduce-only), so the bot does not need seconds-
    # level polling — it re-evaluates on the agent's schedule, bounded here.
    default_run_minutes: int = 10          # used when the agent gives no/invalid value
    min_run_minutes: int = 1               # floor (avoid hammering / cost)
    max_run_minutes: int = 15              # LEARNING MODE: capped low so it re-evaluates often (prod value: 60)

    # --- Regime filter (ADX-14) --------------------------------------------
    # ADX >= trend threshold  -> trending  -> momentum entries only
    # ADX <= range threshold  -> ranging   -> mean-reversion entries only
    # in between               -> undefined -> do NOT trade
    # LEARNING MODE: both set to 22 so the "UNDEFINED / do-not-trade" band collapses
    # to zero — every reading is TREND or RANGE, so the bot always has a playable edge
    # and stops sitting out (prod values: 25 / 20). This was the single biggest throttle.
    adx_trend_threshold: float = 22.0
    adx_range_threshold: float = 22.0


# Module-level singleton used across the workflow, prompt and client.
STRATEGY = StrategyConfig()

# Regime labels
REGIME_TREND = "TREND"
REGIME_RANGE = "RANGE"
REGIME_UNDEFINED = "UNDEFINED"


def classify_regime(adx: float, config: StrategyConfig = STRATEGY) -> str:
    """
    Classify the market regime from ADX so the agent applies exactly one edge:
    momentum in trends, mean-reversion in ranges, nothing in between.
    """
    if adx is None:
        return REGIME_UNDEFINED
    if adx >= config.adx_trend_threshold:
        return REGIME_TREND
    if adx <= config.adx_range_threshold:
        return REGIME_RANGE
    return REGIME_UNDEFINED

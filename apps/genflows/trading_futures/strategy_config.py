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
    # Classic 1% risk-per-trade rule. Enforced in code against the actual
    # stop distance, not left to the model to "calculate".
    risk_per_trade_pct: float = 1.0
    # Aggregate cap across all open positions (BTC/ETH/alts are correlated, so
    # concurrent positions are closer to one concentrated bet than to N bets).
    max_portfolio_risk_pct: float = 3.0
    max_concurrent_positions: int = 3

    # --- Circuit breaker ----------------------------------------------------
    # Halt new positions once the day is down this much (kill-switch in code).
    max_daily_loss_pct: float = 5.0

    # --- Exits --------------------------------------------------------------
    atr_stop_multiplier: float = 1.5
    tp1_atr_multiplier: float = 1.5
    tp2_atr_multiplier: float = 3.0
    min_risk_reward: float = 2.0

    # --- Dynamic cadence ----------------------------------------------------
    # The agent decides when to run next (NEXT_RUN_MINUTES). The code clamps it:
    # SL/TP live on the exchange (reduce-only), so the bot does not need seconds-
    # level polling — it re-evaluates on the agent's schedule, bounded here.
    default_run_minutes: int = 15          # used when the agent gives no/invalid value
    min_run_minutes: int = 1               # floor (avoid hammering / cost)
    max_run_minutes: int = 60              # ceiling when flat
    max_run_minutes_with_position: int = 10  # tighter ceiling while a position is open

    # --- Regime filter (ADX-14) --------------------------------------------
    # ADX >= trend threshold  -> trending  -> momentum entries only
    # ADX <= range threshold  -> ranging   -> mean-reversion entries only
    # in between               -> undefined -> do NOT trade
    adx_trend_threshold: float = 25.0
    adx_range_threshold: float = 20.0


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

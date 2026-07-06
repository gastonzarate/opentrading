"""
Strategy iteration sweep — runs a curated set of variants over a train/test split
across multiple symbols, to find a robust positive edge WITHOUT overfitting.

Anti-overfit discipline:
- Split each symbol's history into TRAIN (older 60%) and TEST (recent 40%).
- Evaluate every variant on both, on BTC/ETH/SOL.
- A variant is only a "candidate" if it is profitable (profit factor > 1) on TRAIN
  *and* TEST *and* averaged across symbols — not just on one cherry-picked slice.

Run: python -m services.backtest_sweep
"""
from apps.genflows.trading_futures.strategy_config import REGIME_RANGE, REGIME_TREND
from services.backtest_harness import BacktestParams, RegimeBacktester, fetch_history
from services.binance_client import BinanceClient

import sys

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
INTERVAL = sys.argv[1] if len(sys.argv) > 1 else "1h"
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 330
TRAIN_FRAC = 0.6

VARIANTS = {
    "baseline_all_fixedTP": BacktestParams(),
    "trend_fixedTP": BacktestParams(trade_regimes=(REGIME_TREND,)),
    "trend_trail3": BacktestParams(trade_regimes=(REGIME_TREND,), exit_mode="trailing", trail_atr_mult=3.0),
    "trend_trail2": BacktestParams(trade_regimes=(REGIME_TREND,), exit_mode="trailing", trail_atr_mult=2.0),
    "trend_trail4_widestop": BacktestParams(
        trade_regimes=(REGIME_TREND,), exit_mode="trailing", trail_atr_mult=4.0, atr_stop_mult=2.0
    ),
    "trend_tp5": BacktestParams(trade_regimes=(REGIME_TREND,), atr_tp_mult=5.0),
    "range_fixedTP": BacktestParams(trade_regimes=(REGIME_RANGE,)),
    "range_trail3": BacktestParams(trade_regimes=(REGIME_RANGE,), exit_mode="trailing", trail_atr_mult=3.0),
}


def _agg(dfs, params):
    """Average metrics of a variant across symbols for a set of (symbol, slice) frames."""
    pfs, exps, rets, trades = [], [], [], 0
    for ohlcv in dfs:
        m = RegimeBacktester(params).run(ohlcv)["metrics"]
        if m.get("trades", 0) == 0:
            continue
        pf = m["profit_factor"]
        pfs.append(min(pf, 10) if pf != float("inf") else 10)
        exps.append(m["expectancy_r"])
        rets.append(m["total_return_pct"])
        trades += m["trades"]
    n = len(pfs) or 1
    return {
        "pf": round(sum(pfs) / n, 2),
        "exp_r": round(sum(exps) / n, 3),
        "ret": round(sum(rets) / n, 1),
        "trades": trades,
    }


def main():  # pragma: no cover - CLI/analysis entry
    client = BinanceClient()
    train_frames, test_frames = [], []
    print(f"Interval={INTERVAL}  Days={DAYS}")
    for sym in SYMBOLS:
        df = fetch_history(client, sym, INTERVAL, DAYS)
        split = int(len(df) * TRAIN_FRAC)
        train_frames.append(df.iloc[:split].reset_index(drop=True))
        test_frames.append(df.iloc[split:].reset_index(drop=True))
        print(f"{sym}: {len(df)} bars -> train {split}, test {len(df) - split}")

    print("\n{:<24} {:>18} {:>18}   {}".format("variant", "TRAIN pf/exp/ret", "TEST pf/exp/ret", "candidate"))
    print("-" * 90)
    rows = []
    for name, params in VARIANTS.items():
        tr = _agg(train_frames, params)
        te = _agg(test_frames, params)
        candidate = tr["pf"] > 1.0 and te["pf"] > 1.0 and tr["exp_r"] > 0 and te["exp_r"] > 0
        rows.append((name, tr, te, candidate))
        print("{:<24} {:>7.2f}/{:>5.2f}/{:>6.1f} {:>7.2f}/{:>5.2f}/{:>6.1f}   {}".format(
            name, tr["pf"], tr["exp_r"], tr["ret"], te["pf"], te["exp_r"], te["ret"],
            "✅" if candidate else "",
        ))

    winners = [r for r in rows if r[3]]
    print("\nRobust candidates (profitable on train AND test, all symbols):",
          ", ".join(w[0] for w in winners) if winners else "NONE")


if __name__ == "__main__":  # pragma: no cover
    main()

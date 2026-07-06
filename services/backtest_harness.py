"""
Offline backtest harness for the regime strategy.

Unlike services/backtest_service.py (a light in-loop "similar conditions" heuristic
used live by the agent), this is a proper offline simulator over long history:
- Runs the exact regime rules (TREND -> momentum, RANGE -> mean-reversion, else flat)
- Fixed-fractional (1%) risk sizing with a compounding equity curve
- Subtracts trading fees + slippage and an approximate funding cost per 8h held
- Reports return, win rate, profit factor, expectancy (R), max drawdown, Sharpe

It is deliberately simple and honest: one position at a time, entry at the close of
the signal bar, ATR stop / TP with stop priority intrabar. It is NOT a parameter
optimizer — it evaluates the fixed strategy out-of-sample. Run it before trusting
the strategy with real money.

CLI:  python -m services.backtest_harness BTC 1h 90
"""
from dataclasses import dataclass

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, MACD, EMAIndicator
from ta.volatility import AverageTrueRange

from apps.genflows.trading_futures.strategy_config import (
    REGIME_RANGE,
    REGIME_TREND,
    STRATEGY,
    classify_regime,
)


@dataclass
class BacktestParams:
    risk_per_trade_pct: float = STRATEGY.risk_per_trade_pct
    atr_stop_mult: float = STRATEGY.atr_stop_multiplier
    atr_tp_mult: float = STRATEGY.tp2_atr_multiplier  # 3xATR -> ~1:2 R:R vs 1.5x stop
    max_holding_bars: int = 48
    fee_pct_per_side: float = 0.05
    slippage_pct_per_side: float = 0.02
    funding_pct_per_8h: float = 0.01  # approximate cost against the position
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    # Which regimes to trade (a variant may trade only trends, or only ranges).
    trade_regimes: tuple = (REGIME_TREND, REGIME_RANGE)
    # Exit style: "fixed_tp" = fixed ATR take-profit; "trailing" = chandelier trailing
    # stop with no fixed TP (lets winners run — the trend-following edge).
    exit_mode: str = "fixed_tp"
    trail_atr_mult: float = 3.0

    @property
    def round_trip_cost_pct(self) -> float:
        return (self.fee_pct_per_side + self.slippage_pct_per_side) * 2


class RegimeBacktester:
    def __init__(self, params: BacktestParams = None):
        self.p = params or BacktestParams()

    # --- indicators ----------------------------------------------------
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_9"] = EMAIndicator(close=df["close"], window=9).ema_indicator()
        df["ema_21"] = EMAIndicator(close=df["close"], window=21).ema_indicator()
        macd = MACD(close=df["close"])
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["rsi_7"] = RSIIndicator(close=df["close"], window=7).rsi()
        df["atr_14"] = AverageTrueRange(
            high=df["high"], low=df["low"], close=df["close"], window=14
        ).average_true_range()
        df["adx"] = ADXIndicator(high=df["high"], low=df["low"], close=df["close"], window=14).adx()
        return df

    # --- strategy rules ------------------------------------------------
    def entry_signal(self, row) -> str | None:
        """Return 'LONG'/'SHORT'/None for a bar, applying exactly one edge per regime."""
        regime = classify_regime(None if pd.isna(row["adx"]) else float(row["adx"]))
        if regime not in self.p.trade_regimes:
            return None
        if pd.isna(row["ema_9"]) or pd.isna(row["ema_21"]) or pd.isna(row["macd"]) or pd.isna(row["rsi_7"]):
            return None
        close = row["close"]
        if regime == REGIME_TREND:
            if close > row["ema_9"] and close > row["ema_21"] and row["macd"] > row["macd_signal"]:
                return "LONG"
            if close < row["ema_9"] and close < row["ema_21"] and row["macd"] < row["macd_signal"]:
                return "SHORT"
            return None
        if regime == REGIME_RANGE:
            if row["rsi_7"] < self.p.rsi_oversold:
                return "LONG"
            if row["rsi_7"] > self.p.rsi_overbought:
                return "SHORT"
            return None
        return None  # UNDEFINED -> no trade

    # --- single-trade simulation --------------------------------------
    def simulate_trade(self, df: pd.DataFrame, i: int, direction: str) -> dict | None:
        entry = float(df.iloc[i]["close"])
        atr = float(df.iloc[i]["atr_14"])
        if pd.isna(atr) or atr <= 0 or entry <= 0:
            return None
        stop_dist = self.p.atr_stop_mult * atr
        tp_dist = self.p.atr_tp_mult * atr
        trail_dist = self.p.trail_atr_mult * atr
        trailing = self.p.exit_mode == "trailing"
        if direction == "LONG":
            stop, tp = entry - stop_dist, entry + tp_dist
        else:
            stop, tp = entry + stop_dist, entry - tp_dist

        exit_price, exit_i = None, None
        extreme = entry  # best price reached, for the trailing stop
        end = min(i + self.p.max_holding_bars, len(df) - 1)
        for j in range(i + 1, end + 1):
            hi, lo = float(df.iloc[j]["high"]), float(df.iloc[j]["low"])
            if direction == "LONG":
                if lo <= stop:  # stop (initial or trailed) checked before this bar's move
                    exit_price, exit_i = stop, j
                    break
                if not trailing and hi >= tp:
                    exit_price, exit_i = tp, j
                    break
                if trailing:  # ratchet the stop up under the highest high
                    extreme = max(extreme, hi)
                    stop = max(stop, extreme - trail_dist)
            else:
                if hi >= stop:
                    exit_price, exit_i = stop, j
                    break
                if not trailing and lo <= tp:
                    exit_price, exit_i = tp, j
                    break
                if trailing:
                    extreme = min(extreme, lo)
                    stop = min(stop, extreme + trail_dist)
        if exit_price is None:
            exit_i = end
            exit_price = float(df.iloc[end]["close"])

        holding_hours = self._bars_to_hours(df, i, exit_i)
        gross_pct = ((exit_price - entry) / entry * 100) if direction == "LONG" else ((entry - exit_price) / entry * 100)
        funding_cost = self.p.funding_pct_per_8h * (holding_hours / 8)
        net_pct = gross_pct - self.p.round_trip_cost_pct - funding_cost
        stop_pct = stop_dist / entry * 100
        r_multiple = net_pct / stop_pct if stop_pct > 0 else 0.0
        return {
            "direction": direction,
            "entry": entry,
            "exit": exit_price,
            "exit_index": exit_i,
            "holding_hours": round(holding_hours, 1),
            "net_pct": round(net_pct, 4),
            "r_multiple": round(r_multiple, 3),
        }

    @staticmethod
    def _bars_to_hours(df, i, j) -> float:
        if "datetime" in df.columns:
            return (df.iloc[j]["datetime"] - df.iloc[i]["datetime"]).total_seconds() / 3600
        return float(j - i)  # assume 1h bars when no timestamps

    # --- full run ------------------------------------------------------
    def run(self, ohlcv: pd.DataFrame) -> dict:
        df = self.add_indicators(ohlcv).reset_index(drop=True)
        risk_frac = self.p.risk_per_trade_pct / 100
        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        equity_curve = [equity]
        trades = []

        i = 30  # warm-up for indicators
        while i < len(df) - 1:
            sig = self.entry_signal(df.iloc[i])
            if not sig:
                i += 1
                continue
            trade = self.simulate_trade(df, i, sig)
            if not trade:
                i += 1
                continue
            equity *= 1 + risk_frac * trade["r_multiple"]
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak)
            equity_curve.append(equity)
            trades.append(trade)
            i = trade["exit_index"] + 1  # no overlapping positions

        return {"metrics": self._metrics(trades, equity, max_dd), "trades": trades, "equity_curve": equity_curve}

    def _metrics(self, trades: list, equity: float, max_dd: float) -> dict:
        n = len(trades)
        if n == 0:
            return {"trades": 0, "note": "No trades generated in this period."}
        rs = [t["r_multiple"] for t in trades]
        wins = [r for r in rs if r > 0]
        losses = [r for r in rs if r <= 0]
        mean_r = sum(rs) / n
        std_r = (sum((r - mean_r) ** 2 for r in rs) / n) ** 0.5
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        return {
            "trades": n,
            "win_rate_pct": round(len(wins) / n * 100, 1),
            "expectancy_r": round(mean_r, 3),
            "avg_win_r": round(sum(wins) / len(wins), 3) if wins else 0.0,
            "avg_loss_r": round(sum(losses) / len(losses), 3) if losses else 0.0,
            "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else float("inf"),
            "total_return_pct": round((equity - 1) * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "sharpe_per_trade": round(mean_r / std_r, 2) if std_r > 0 else 0.0,
            "avg_holding_hours": round(sum(t["holding_hours"] for t in trades) / n, 1),
            "costs_included": "fees + slippage + funding",
        }


def fetch_history(binance_client, symbol: str, interval: str = "1h", days: int = 90) -> pd.DataFrame:
    """Paginate Binance klines into a single OHLCV DataFrame (needs a live client)."""
    import time as _time

    ms_per = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}.get(interval, 3_600_000)
    end = int(_time.time() * 1000)
    start = end - days * 86_400_000
    rows = []
    cursor = start
    while cursor < end:
        batch = binance_client.client.futures_klines(symbol=symbol, interval=interval, startTime=cursor, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        cursor = batch[-1][6] + 1  # last close_time + 1
        if len(batch) < 1000:
            break
    df = pd.DataFrame(
        rows,
        columns=["timestamp", "open", "high", "low", "close", "volume", "close_time",
                 "qav", "trades", "tbbav", "tbqav", "ignore"],
    )
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


def _main():  # pragma: no cover - CLI entry
    import sys

    from services.binance_client import BinanceClient

    currency = sys.argv[1] if len(sys.argv) > 1 else "BTC"
    interval = sys.argv[2] if len(sys.argv) > 2 else "1h"
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 90
    symbol = f"{currency.upper()}USDT"

    df = fetch_history(BinanceClient(), symbol, interval, days)
    print(f"Loaded {len(df)} {interval} bars for {symbol} (~{days}d)")
    result = RegimeBacktester().run(df)
    print("METRICS:")
    for k, v in result["metrics"].items():
        print(f"  {k}: {v}")


if __name__ == "__main__":  # pragma: no cover
    _main()

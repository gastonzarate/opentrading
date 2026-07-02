"""
Backtest Service for simulating trading strategies with historical data.

This service allows the trading agent to validate strategies before executing
real trades by analyzing how similar market conditions performed historically.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import AverageTrueRange


class BacktestService:
    """
    Service for backtesting trading strategies using historical market data.

    The service finds historical moments with similar market conditions to the
    current state, simulates trades, and returns performance metrics.
    """

    # Condition matching tolerances (based on professional trading practices)
    RSI_TOLERANCE = 5  # ±5 points
    ATR_TOLERANCE = 0.25  # ±25% of current value
    # MACD and funding rate: same sign (positive/negative)

    # Round-trip trading cost applied to every simulated trade so the backtest is
    # not systematically optimistic: taker fee ~0.05% per side + ~0.02% slippage
    # per side => ~0.14% total. Subtracted from each trade's PnL.
    FEE_PCT_PER_SIDE = 0.05
    SLIPPAGE_PCT_PER_SIDE = 0.02
    ROUND_TRIP_COST_PCT = (FEE_PCT_PER_SIDE + SLIPPAGE_PCT_PER_SIDE) * 2

    # Similar setups within this many bars (hours) of an accepted one are skipped,
    # so heavily overlapping/autocorrelated entries are not counted as independent.
    MIN_BARS_BETWEEN_ENTRIES = 6

    # Minimum simulated trades for the metrics to be treated as meaningful.
    MIN_SAMPLE = 20

    def _apply_costs(self, pnl_pct: float) -> float:
        """Subtract the round-trip trading cost from a trade's percentage PnL."""
        return pnl_pct - self.ROUND_TRIP_COST_PCT

    def __init__(self, binance_client):
        """
        Initialize BacktestService.

        Args:
            binance_client: BinanceClient instance for fetching historical data.
        """
        self.binance_client = binance_client

    def backtest_strategy(
        self,
        currency: str,
        direction: str,
        current_conditions: dict,
        lookback_days: int = 30,
        stop_loss_pct: float = 2.0,
        take_profit_pct: float = 4.0,
    ) -> dict:
        """
        Backtest a trading strategy based on similar historical conditions.

        Args:
            currency: Base currency symbol (e.g., 'BTC', 'ETH').
            direction: Trade direction ('LONG' or 'SHORT').
            current_conditions: Dict with current market indicators:
                - rsi: Current RSI value
                - macd: Current MACD value
                - price: Current price
                - ema_9: Current EMA(9) value
                - funding_rate: Current funding rate
                - atr: Current ATR value (optional)
            lookback_days: Number of days of historical data to analyze.
            stop_loss_pct: Stop loss percentage to simulate.
            take_profit_pct: Take profit percentage to simulate.

        Returns:
            dict: Backtest results with performance metrics.
        """
        # Validate direction
        direction = direction.upper()
        if direction not in ("LONG", "SHORT"):
            return {"error": f"Invalid direction: {direction}. Must be 'LONG' or 'SHORT'."}

        # Load historical data with indicators
        df = self._load_historical_data(currency, lookback_days)

        if df.empty:
            return {
                "error": "Could not load historical data",
                "similar_setups_found": 0,
            }

        # Find similar market conditions in history
        similar_conditions = self._find_similar_conditions(df, current_conditions)

        if not similar_conditions:
            return {
                "similar_setups_found": 0,
                "trades_simulated": 0,
                "message": "No similar market conditions found in the lookback period.",
            }

        # Simulate trades for each similar condition
        trade_results = []
        for condition in similar_conditions:
            result = self._simulate_trade(
                df=df,
                entry_index=condition["index"],
                direction=direction,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
            )
            if result:
                trade_results.append(result)

        if not trade_results:
            return {
                "similar_setups_found": len(similar_conditions),
                "trades_simulated": 0,
                "message": "Similar conditions found but could not simulate trades (insufficient data after entry points).",
            }

        # Calculate aggregate metrics
        return self._calculate_metrics(
            trade_results=trade_results,
            similar_conditions=similar_conditions,
            direction=direction,
        )

    def _load_historical_data(self, currency: str, lookback_days: int) -> pd.DataFrame:
        """
        Load historical klines and calculate indicators.

        Args:
            currency: Base currency symbol.
            lookback_days: Number of days of data to load.

        Returns:
            pd.DataFrame: Historical data with calculated indicators.
        """
        symbol = f"{currency.upper()}USDT"

        # Calculate how many 1-hour candles we need
        # Add extra buffer for indicator calculation warm-up
        limit = min(lookback_days * 24 + 50, 1000)  # Binance max is 1000

        try:
            # Get klines using the existing Binance client method
            klines = self.binance_client.client.get_klines(
                symbol=symbol,
                interval="1h",
                limit=limit,
            )

            if not klines:
                return pd.DataFrame()

            df = pd.DataFrame(
                klines,
                columns=[
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "close_time",
                    "quote_asset_volume",
                    "number_of_trades",
                    "taker_buy_base_asset_volume",
                    "taker_buy_quote_asset_volume",
                    "ignore",
                ],
            )

            # Convert numeric columns
            numeric_cols = ["open", "high", "low", "close", "volume"]
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, axis=1)

            # Convert timestamp to datetime
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")

            # Calculate indicators
            df = self._calculate_indicators(df)

            # Filter to the actual lookback period (after indicators are calculated).
            # df["datetime"] is tz-naive (epoch ms parsed as UTC), so the cutoff must
            # also be naive — pandas 3.0 raises on naive/tz-aware comparisons.
            cutoff_time = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).replace(tzinfo=None)
            df = df[df["datetime"] >= cutoff_time].reset_index(drop=True)

            return df

        except Exception as e:
            print(f"Error loading historical data: {e}")
            return pd.DataFrame()

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators for the dataframe.

        Args:
            df: DataFrame with OHLCV data.

        Returns:
            pd.DataFrame: DataFrame with added indicator columns.
        """
        # EMA
        df["ema_9"] = EMAIndicator(close=df["close"], window=9).ema_indicator()
        df["ema_21"] = EMAIndicator(close=df["close"], window=21).ema_indicator()

        # MACD
        macd = MACD(close=df["close"])
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()

        # RSI
        df["rsi_7"] = RSIIndicator(close=df["close"], window=7).rsi()
        df["rsi_14"] = RSIIndicator(close=df["close"], window=14).rsi()

        # ATR
        atr = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14)
        df["atr_14"] = atr.average_true_range()

        # Price position relative to EMA
        df["price_above_ema9"] = df["close"] > df["ema_9"]
        df["price_above_ema21"] = df["close"] > df["ema_21"]

        return df

    def _find_similar_conditions(
        self,
        df: pd.DataFrame,
        current_conditions: dict,
    ) -> list[dict]:
        """
        Find historical moments with similar market conditions.

        Args:
            df: Historical data with indicators.
            current_conditions: Current market conditions.

        Returns:
            list: List of dicts with index and matched conditions.
        """
        similar = []

        current_rsi = current_conditions.get("rsi")
        current_macd = current_conditions.get("macd")
        current_price = current_conditions.get("price")
        current_ema_9 = current_conditions.get("ema_9")
        current_funding = current_conditions.get("funding_rate", 0)
        current_atr = current_conditions.get("atr")

        # Determine current price position relative to EMA
        price_above_ema = current_price > current_ema_9 if current_ema_9 else None

        # Track the last accepted entry so overlapping (autocorrelated) setups
        # within the cooldown window are not counted as independent samples.
        last_accepted_idx = None

        # Skip last 24 rows (most recent day - need space to simulate trades)
        for idx in range(len(df) - 24):
            if last_accepted_idx is not None and (idx - last_accepted_idx) < self.MIN_BARS_BETWEEN_ENTRIES:
                continue

            row = df.iloc[idx]
            matches = True
            match_details = {}

            # RSI match (within tolerance)
            if current_rsi is not None and pd.notna(row["rsi_7"]):
                rsi_diff = abs(row["rsi_7"] - current_rsi)
                if rsi_diff > self.RSI_TOLERANCE:
                    matches = False
                else:
                    match_details["rsi"] = row["rsi_7"]

            # MACD sign match
            if current_macd is not None and pd.notna(row["macd"]):
                current_macd_sign = 1 if current_macd > 0 else -1
                hist_macd_sign = 1 if row["macd"] > 0 else -1
                if current_macd_sign != hist_macd_sign:
                    matches = False
                else:
                    match_details["macd"] = row["macd"]

            # Price position relative to EMA match
            if price_above_ema is not None and pd.notna(row["price_above_ema9"]):
                if row["price_above_ema9"] != price_above_ema:
                    matches = False
                else:
                    match_details["price_above_ema9"] = row["price_above_ema9"]

            # ATR match (within 25% tolerance) - if provided
            if current_atr is not None and pd.notna(row["atr_14"]):
                atr_ratio = row["atr_14"] / current_atr if current_atr > 0 else 1
                if abs(atr_ratio - 1) > self.ATR_TOLERANCE:
                    matches = False
                else:
                    match_details["atr"] = row["atr_14"]

            if matches:
                last_accepted_idx = idx
                similar.append(
                    {
                        "index": idx,
                        "datetime": row["datetime"],
                        "price": row["close"],
                        "rsi": row["rsi_7"],
                        "macd": row["macd"],
                        "matched_conditions": match_details,
                    }
                )

        return similar

    def _simulate_trade(
        self,
        df: pd.DataFrame,
        entry_index: int,
        direction: str,
        stop_loss_pct: float,
        take_profit_pct: float,
        max_holding_hours: int = 48,
    ) -> dict | None:
        """
        Simulate a trade from a specific entry point.

        Args:
            df: Historical data.
            entry_index: Index in df where trade is entered.
            direction: 'LONG' or 'SHORT'.
            stop_loss_pct: Stop loss percentage.
            take_profit_pct: Take profit percentage.
            max_holding_hours: Maximum hours to hold before force exit.

        Returns:
            dict: Trade result or None if simulation not possible.
        """
        if entry_index >= len(df) - 1:
            return None

        entry_price = df.iloc[entry_index]["close"]
        entry_time = df.iloc[entry_index]["datetime"]

        # Calculate SL and TP prices
        if direction == "LONG":
            stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
            take_profit_price = entry_price * (1 + take_profit_pct / 100)
        else:  # SHORT
            stop_loss_price = entry_price * (1 + stop_loss_pct / 100)
            take_profit_price = entry_price * (1 - take_profit_pct / 100)

        # Simulate forward from entry
        for i in range(entry_index + 1, min(entry_index + max_holding_hours + 1, len(df))):
            row = df.iloc[i]
            high = row["high"]
            low = row["low"]
            close = row["close"]
            current_time = row["datetime"]

            holding_hours = (current_time - entry_time).total_seconds() / 3600

            if direction == "LONG":
                # Check stop loss hit (low touches SL)
                if low <= stop_loss_price:
                    pnl_pct = self._apply_costs(-stop_loss_pct)
                    return {
                        "outcome": "STOP_LOSS",
                        "pnl_pct": pnl_pct,
                        "entry_price": entry_price,
                        "exit_price": stop_loss_price,
                        "holding_hours": holding_hours,
                    }

                # Check take profit hit (high touches TP)
                if high >= take_profit_price:
                    pnl_pct = self._apply_costs(take_profit_pct)
                    return {
                        "outcome": "TAKE_PROFIT",
                        "pnl_pct": pnl_pct,
                        "entry_price": entry_price,
                        "exit_price": take_profit_price,
                        "holding_hours": holding_hours,
                    }

            else:  # SHORT
                # Check stop loss hit (high touches SL)
                if high >= stop_loss_price:
                    pnl_pct = self._apply_costs(-stop_loss_pct)
                    return {
                        "outcome": "STOP_LOSS",
                        "pnl_pct": pnl_pct,
                        "entry_price": entry_price,
                        "exit_price": stop_loss_price,
                        "holding_hours": holding_hours,
                    }

                # Check take profit hit (low touches TP)
                if low <= take_profit_price:
                    pnl_pct = self._apply_costs(take_profit_pct)
                    return {
                        "outcome": "TAKE_PROFIT",
                        "pnl_pct": pnl_pct,
                        "entry_price": entry_price,
                        "exit_price": take_profit_price,
                        "holding_hours": holding_hours,
                    }

        # Timeout - exit at last available price
        last_row = df.iloc[min(entry_index + max_holding_hours, len(df) - 1)]
        exit_price = last_row["close"]
        holding_hours = (last_row["datetime"] - entry_time).total_seconds() / 3600

        if direction == "LONG":
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        else:  # SHORT
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100

        return {
            "outcome": "TIMEOUT",
            "pnl_pct": self._apply_costs(pnl_pct),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "holding_hours": holding_hours,
        }

    def _calculate_metrics(
        self,
        trade_results: list[dict],
        similar_conditions: list[dict],
        direction: str,
    ) -> dict:
        """
        Calculate aggregate performance metrics from trade simulations.

        Args:
            trade_results: List of simulated trade results.
            similar_conditions: List of matched conditions.
            direction: Trade direction.

        Returns:
            dict: Aggregated metrics.
        """
        total_trades = len(trade_results)
        wins = [t for t in trade_results if t["pnl_pct"] > 0]
        losses = [t for t in trade_results if t["pnl_pct"] <= 0]

        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0

        # Calculate averages
        all_pnl = [t["pnl_pct"] for t in trade_results]
        avg_profit = sum(all_pnl) / total_trades if total_trades > 0 else 0

        win_pnl = [t["pnl_pct"] for t in wins]
        loss_pnl = [t["pnl_pct"] for t in losses]

        avg_win = sum(win_pnl) / len(wins) if wins else 0
        avg_loss = sum(loss_pnl) / len(losses) if losses else 0

        max_win = max(all_pnl) if all_pnl else 0
        max_loss = min(all_pnl) if all_pnl else 0

        # Profit factor: sum of wins / abs(sum of losses)
        total_wins = sum(win_pnl) if win_pnl else 0
        total_losses = abs(sum(loss_pnl)) if loss_pnl else 1  # Avoid division by zero
        profit_factor = total_wins / total_losses if total_losses > 0 else total_wins

        # Expectancy: (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
        expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

        # Holding time
        holding_times = [t["holding_hours"] for t in trade_results]
        avg_holding = sum(holding_times) / len(holding_times) if holding_times else 0

        # Outcome breakdown
        outcomes = {
            "take_profit": len([t for t in trade_results if t["outcome"] == "TAKE_PROFIT"]),
            "stop_loss": len([t for t in trade_results if t["outcome"] == "STOP_LOSS"]),
            "timeout": len([t for t in trade_results if t["outcome"] == "TIMEOUT"]),
        }

        return {
            "direction": direction,
            "similar_setups_found": len(similar_conditions),
            "trades_simulated": total_trades,
            "sufficient_sample": total_trades >= self.MIN_SAMPLE,
            "costs_included": True,
            "round_trip_cost_pct": self.ROUND_TRIP_COST_PCT,
            "win_rate": round(win_rate, 1),
            "avg_profit_pct": round(avg_profit, 2),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "max_win_pct": round(max_win, 2),
            "max_loss_pct": round(max_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy": round(expectancy, 2),
            "avg_holding_hours": round(avg_holding, 1),
            "outcome_breakdown": outcomes,
        }

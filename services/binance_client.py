import os
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, MACD, EMAIndicator
from ta.volatility import AverageTrueRange


class BinanceClient:
    def __init__(
        self,
        client=None,
        testnet=False,
        max_daily_loss_pct=None,
        max_leverage=None,
        risk_per_trade_pct=None,
        max_portfolio_risk_pct=None,
        max_concurrent_positions=None,
        enforce_regime=False,
    ):
        """
        Initialize the Binance Client.

        Args:
            client: Optional pre-built binance Client (used for testing / DI).
                    When omitted, one is created from environment variables.
            testnet (bool): Route to the Binance Futures testnet instead of live.
            max_daily_loss_pct (float | None): Daily loss kill-switch threshold as
                    a percent of wallet balance. When the day's loss reaches this,
                    opening new positions is blocked. None disables the switch and
                    falls back to the MAX_DAILY_LOSS_PCT env var if present.
            max_leverage (int | None): Hard cap on leverage. Requests above this are
                    rejected in code so the LLM cannot over-leverage. None disables.
            risk_per_trade_pct (float | None): Hard cap on the risk of a single trade
                    as a percent of wallet balance (quantity x |mark - stop|). Trades
                    exceeding it are rejected in code. None disables.
        """
        if client is not None:
            self.client = client
        else:
            # In testnet mode use the separate demo credentials (they only work on
            # the futures testnet); fall back to the live vars if demo ones absent.
            if testnet:
                api_key = os.getenv("BINANCE_DEMO_API_KEY") or os.getenv("BINANCE_API_KEY")
                api_secret = os.getenv("BINANCE_DEMO_API_SECRET") or os.getenv("BINANCE_API_SECRET")
            else:
                api_key = os.getenv("BINANCE_API_KEY")
                api_secret = os.getenv("BINANCE_API_SECRET")

            if not api_key or not api_secret:
                raise ValueError("Binance API key/secret must be set in environment variables.")

            self.client = Client(api_key, api_secret, testnet=testnet)

        if max_daily_loss_pct is None:
            env_val = os.getenv("MAX_DAILY_LOSS_PCT")
            max_daily_loss_pct = float(env_val) if env_val else None
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_leverage = max_leverage
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.max_concurrent_positions = max_concurrent_positions
        self.enforce_regime = enforce_regime

        # Cache of per-symbol exchange filters (step size, tick size, ...).
        self._symbol_filters_cache = {}

    def compute_quantity_for_risk(self, currency: str, stop_loss_price: float) -> float:
        """
        Position size so that the loss at the stop equals risk_per_trade_pct% of
        wallet (the 1% rule), computed in code instead of trusting the LLM's math.
        Returns 0 if it cannot be determined.
        """
        if not self.risk_per_trade_pct or stop_loss_price is None:
            return 0.0
        mark = self.get_mark_price(currency)
        if mark <= 0:
            return 0.0
        distance = abs(mark - stop_loss_price)
        if distance <= 0:
            return 0.0
        wallet = self.get_futures_balance().get("total_wallet_balance", 0) or 0
        if wallet <= 0:
            return 0.0
        risk_budget = wallet * (self.risk_per_trade_pct / 100)
        symbol = f"{currency.upper()}USDT"
        return self._round_quantity(symbol, risk_budget / distance)

    def get_regime(self, currency: str) -> str:
        """Current market regime for a symbol from 1h ADX (TREND/RANGE/UNDEFINED)."""
        from apps.genflows.trading_futures.strategy_config import REGIME_UNDEFINED, classify_regime

        symbol = f"{currency.upper()}USDT"
        try:
            df = self._calculate_indicators(self._get_klines(symbol, Client.KLINE_INTERVAL_1HOUR, limit=100))
            adx = df["adx"].iloc[-1]
            return classify_regime(None if pd.isna(adx) else float(adx))
        except Exception as e:
            print(f"Error computing regime for {symbol}: {e}")
            return REGIME_UNDEFINED

    def _below_min_notional(self, symbol: str, quantity: float, mark: float) -> bool:
        """True if the order notional is below the exchange minimum (default $100)."""
        min_notional = self._get_symbol_filters(symbol).get("min_notional") or 0
        if min_notional <= 0 or mark <= 0:
            return False
        return quantity * mark < min_notional

    def _open_positions_risk_and_count(self):
        """
        (total_risk_usd, count) across open positions, where each position's risk
        is quantity x distance from mark to its stop-loss order. Positions without
        a stop are counted but contribute 0 risk here (the prompt/rules require a
        stop to exist; a missing one is handled separately).
        """
        positions = self.get_all_open_positions()
        total_risk = 0.0
        for p in positions:
            stops = p.get("stop_loss_orders") or []
            if not stops:
                continue
            stop_price = float(stops[0].get("stop_price", 0))
            mark = float(p.get("mark_price", 0) or 0)
            qty = abs(float(p.get("position_amount", 0) or 0))
            total_risk += qty * abs(mark - stop_price)
        return total_risk, len(positions)

    def _portfolio_limits_block(self, currency: str, quantity: float, stop_loss_price: float):
        """
        Return a block dict if opening this trade would breach the max concurrent
        positions or the aggregate portfolio-risk cap; otherwise None.
        """
        if not (self.max_concurrent_positions or self.max_portfolio_risk_pct):
            return None

        existing_risk, count = self._open_positions_risk_and_count()

        if self.max_concurrent_positions and count >= self.max_concurrent_positions:
            return {"error": f"Max concurrent positions ({self.max_concurrent_positions}) reached.", "blocked": True}

        if self.max_portfolio_risk_pct:
            mark = self.get_mark_price(currency)
            wallet = self.get_futures_balance().get("total_wallet_balance", 0) or 0
            if mark > 0 and wallet > 0 and stop_loss_price is not None:
                new_risk = quantity * abs(mark - stop_loss_price)
                total_pct = (existing_risk + new_risk) / wallet * 100
                if total_pct > self.max_portfolio_risk_pct:
                    return {
                        "error": f"Portfolio risk {total_pct:.2f}% would exceed the "
                        f"{self.max_portfolio_risk_pct}% cap.",
                        "blocked": True,
                    }
        return None

    def get_mark_price(self, currency: str) -> float:
        """Current mark price for a symbol (used for pre-trade risk checks)."""
        symbol = f"{currency.upper()}USDT"
        try:
            info = self.client.futures_mark_price(symbol=symbol)
            return float(info["markPrice"])
        except (BinanceAPIException, KeyError, TypeError) as e:
            print(f"Error fetching mark price for {symbol}: {e}")
            return 0.0

    def _trade_exceeds_risk_cap(self, currency: str, quantity: float, stop_loss_price: float) -> bool:
        """
        True when a trade's risk (quantity x distance-to-stop) exceeds the
        configured percent of wallet balance (audit / phase-2 guardrail).
        Fails open (returns False) when price or balance cannot be determined.
        """
        if not self.risk_per_trade_pct:
            return False
        mark = self.get_mark_price(currency)
        if mark <= 0 or stop_loss_price is None:
            return False
        wallet = self.get_futures_balance().get("total_wallet_balance", 0) or 0
        if wallet <= 0:
            return False
        risk_usd = quantity * abs(mark - stop_loss_price)
        risk_pct = risk_usd / wallet * 100
        return risk_pct > self.risk_per_trade_pct

    # ------------------------------------------------------------------
    # Exchange precision helpers (audit fix #18)
    # ------------------------------------------------------------------
    def _get_symbol_filters(self, symbol: str) -> dict:
        """
        Fetch and cache LOT_SIZE / PRICE_FILTER / MIN_NOTIONAL filters for a symbol.
        """
        if symbol in self._symbol_filters_cache:
            return self._symbol_filters_cache[symbol]

        filters = {
            "step_size": None,
            "tick_size": None,
            "min_notional": None,
            "quantity_precision": None,
            "price_precision": None,
        }
        try:
            info = self.client.futures_exchange_info()
            for s in info.get("symbols", []):
                if s.get("symbol") == symbol:
                    filters["quantity_precision"] = s.get("quantityPrecision")
                    filters["price_precision"] = s.get("pricePrecision")
                    for f in s.get("filters", []):
                        ft = f.get("filterType")
                        if ft == "LOT_SIZE":
                            filters["step_size"] = float(f["stepSize"])
                        elif ft == "PRICE_FILTER":
                            filters["tick_size"] = float(f["tickSize"])
                        elif ft in ("MIN_NOTIONAL", "NOTIONAL"):
                            filters["min_notional"] = float(f.get("notional", f.get("minNotional", 0)))
                    break
        except BinanceAPIException as e:
            print(f"Error fetching symbol filters for {symbol}: {e}")

        self._symbol_filters_cache[symbol] = filters
        return filters

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """Floor a quantity to the symbol's LOT_SIZE step (never over-buy)."""
        step = self._get_symbol_filters(symbol).get("step_size")
        if not step or step <= 0:
            return quantity
        d_step = Decimal(str(step))
        rounded = (Decimal(str(quantity)) / d_step).to_integral_value(rounding=ROUND_DOWN) * d_step
        return float(rounded)

    def _round_price(self, symbol: str, price: float) -> float:
        """Round a price to the symbol's PRICE_FILTER tick size."""
        tick = self._get_symbol_filters(symbol).get("tick_size")
        if not tick or tick <= 0:
            return price
        d_tick = Decimal(str(tick))
        rounded = (Decimal(str(price)) / d_tick).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * d_tick
        return float(rounded)

    # ------------------------------------------------------------------
    # Risk controls
    # ------------------------------------------------------------------
    def set_margin_type(self, currency: str, margin_type: str = "ISOLATED") -> bool:
        """
        Set the margin type for a symbol (audit fix #5).

        Isolating margin bounds the blast radius of a bad position to its own
        allocated margin instead of the whole wallet. Returns True if the margin
        type is already as requested (Binance error -4046 is benign).
        """
        symbol = f"{currency.upper()}USDT"
        try:
            self.client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
            return True
        except BinanceAPIException as e:
            if getattr(e, "code", None) == -4046 or "No need to change" in str(e):
                return True
            print(f"Error setting margin type for {symbol}: {e}")
            return False

    def _daily_loss_limit_breached(self) -> bool:
        """
        True when today's loss has reached the configured kill-switch threshold
        (audit fix #4). Disabled when max_daily_loss_pct is not set.
        """
        if not self.max_daily_loss_pct:
            return False
        balance = self.get_futures_balance()
        wallet = balance.get("total_wallet_balance", 0) or 0
        if wallet <= 0:
            return False
        total_pnl = self.get_daily_pnl().get("total_daily_pnl", 0)
        if total_pnl >= 0:
            return False
        loss_pct = abs(total_pnl) / wallet * 100
        return loss_pct >= self.max_daily_loss_pct

    def get_market_data(self, currency: str) -> dict:
        """
        Fetch and aggregate market data for a given currency.

        Args:
            currency (str): The currency symbol (e.g., 'BTC').

        Returns:
            dict: A dictionary containing the aggregated market data.
        """
        symbol = f"{currency.upper()}USDT"

        # 1. Fetch Current Snapshot
        ticker = self.client.get_symbol_ticker(symbol=symbol)
        current_price = float(ticker["price"])

        # Fetch recent klines for current indicators (using 1h interval for "current" context)
        # We need enough data for EMA(9), MACD(26, 12, 9), RSI(7)
        klines_1h = self._get_klines(symbol, Client.KLINE_INTERVAL_1HOUR, limit=100)
        df_1h = self._calculate_indicators(klines_1h)

        current_ema_9 = df_1h["ema_9"].iloc[-1]
        current_ema_21 = df_1h["ema_21"].iloc[-1]
        current_macd = df_1h["macd"].iloc[-1]
        current_macd_signal = df_1h["macd_signal"].iloc[-1]
        current_rsi_7 = df_1h["rsi_7"].iloc[-1]
        current_adx = df_1h["adx"].iloc[-1]

        # Regime from 1h ADX: momentum in trends, mean-reversion in ranges, else none.
        from apps.genflows.trading_futures.strategy_config import classify_regime

        regime = classify_regime(None if pd.isna(current_adx) else float(current_adx))

        # 2. Fetch Perpetual Futures Metrics
        futures_metrics = self._get_futures_metrics(symbol)

        # 3. Intraday Series (1h interval)
        # We want the series data. Let's take the last 10 points for the "series" display.
        series_length = 10
        intraday_series = {
            "prices": df_1h["close"].tail(series_length).tolist(),
            "ema_9": df_1h["ema_9"].tail(series_length).tolist(),
            "ema_21": df_1h["ema_21"].tail(series_length).tolist(),
            "macd": df_1h["macd"].tail(series_length).tolist(),
            "macd_signal": df_1h["macd_signal"].tail(series_length).tolist(),
            "rsi_7": df_1h["rsi_7"].tail(series_length).tolist(),
            "rsi_14": df_1h["rsi_14"].tail(series_length).tolist(),
        }

        # 4. Longer-term Context (1d interval)
        klines_1d = self._get_klines(symbol, Client.KLINE_INTERVAL_1DAY, limit=100)
        df_1d = self._calculate_indicators(klines_1d)

        current_vol = df_1d["volume"].iloc[-1]
        avg_vol = df_1d["volume"].mean()  # Simple average of the fetched period

        long_term_context = {
            "ema_9": df_1d["ema_9"].iloc[-1],
            "ema_21": df_1d["ema_21"].iloc[-1],
            "atr_14": df_1d["atr_14"].iloc[-1],
            "atr_28": df_1d["atr_28"].iloc[-1],
            "current_volume": current_vol,
            "average_volume": avg_vol,
            "macd_series": df_1d["macd"].tail(series_length).tolist(),
            "rsi_14_series": df_1d["rsi_14"].tail(series_length).tolist(),
        }

        # Construct the final dictionary
        return {
            "current_price": current_price,
            "current_ema_fast": current_ema_9,
            "current_ema_slow": current_ema_21,
            "current_macd": current_macd,
            "current_macd_signal": current_macd_signal,
            "current_rsi_short": current_rsi_7,
            "current_adx": current_adx,
            "regime": regime,
            "oi_latest": futures_metrics["oi_latest"],
            "oi_average": futures_metrics["oi_average"],
            "funding_rate": futures_metrics["funding_rate"],
            "intraday_interval_label": "1H",
            "mid_prices": intraday_series["prices"],
            "ema_series": intraday_series["ema_9"],
            "ema_slow_series": intraday_series["ema_21"],
            "macd_series": intraday_series["macd"],
            "macd_signal_series": intraday_series["macd_signal"],
            "rsi_short_series": intraday_series["rsi_7"],
            "rsi_long_series": intraday_series["rsi_14"],
            "long_tf_label": "1D",
            "ema_fast_long": long_term_context["ema_9"],
            "ema_slow_long": long_term_context["ema_21"],
            "atr_fast": long_term_context["atr_14"],
            "atr_slow": long_term_context["atr_28"],
            "current_volume": long_term_context["current_volume"],
            "average_volume": long_term_context["average_volume"],
            "macd_long_series": long_term_context["macd_series"],
            "rsi_long_series_longtf": long_term_context["rsi_14_series"],
        }

    def _get_klines(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        """
        Fetch historical klines and return as a DataFrame.
        """
        klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
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

        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators (EMA, MACD, RSI, ATR).
        """
        # EMA
        df["ema_9"] = EMAIndicator(close=df["close"], window=9).ema_indicator()
        df["ema_21"] = EMAIndicator(close=df["close"], window=21).ema_indicator()

        # MACD (12, 26, 9) with signal line so crossovers are computable
        macd = MACD(close=df["close"])
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()

        # RSI
        df["rsi_7"] = RSIIndicator(close=df["close"], window=7).rsi()
        df["rsi_14"] = RSIIndicator(close=df["close"], window=14).rsi()

        # ADX (trend strength) for the regime filter
        df["adx"] = ADXIndicator(high=df["high"], low=df["low"], close=df["close"], window=14).adx()

        # ATR
        atr_14 = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14)
        df["atr_14"] = atr_14.average_true_range()

        atr_28 = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=28)
        df["atr_28"] = atr_28.average_true_range()

        return df

    def _get_futures_metrics(self, symbol: str) -> dict:
        """
        Fetch Futures Open Interest and Funding Rate.
        """
        try:
            # Open Interest
            # Fetching Open Interest Statistics (last 24 hours)
            oi_stats = self.client.futures_open_interest_hist(symbol=symbol, period="1h", limit=24)

            if not oi_stats:
                return {"oi_latest": 0, "oi_average": 0, "funding_rate": 0}

            latest_oi = float(oi_stats[-1]["sumOpenInterest"])
            avg_oi = sum(float(x["sumOpenInterest"]) for x in oi_stats) / len(oi_stats)

            # Funding Rate
            funding_rate_info = self.client.futures_funding_rate(symbol=symbol, limit=1)
            funding_rate = float(funding_rate_info[-1]["fundingRate"]) * 100 if funding_rate_info else 0.0

            return {"oi_latest": latest_oi, "oi_average": avg_oi, "funding_rate": funding_rate}

        except BinanceAPIException as e:
            print(f"Error fetching futures metrics: {e}")
            return {"oi_latest": 0, "oi_average": 0, "funding_rate": 0}

    def set_leverage(self, currency: str, leverage: int) -> bool:
        """
        Set leverage for a symbol.

        Args:
            currency (str): The currency symbol (e.g., 'BTC').
            leverage (int): Leverage value (1-125 depending on symbol).

        Returns:
            bool: True if successful, False otherwise.
        """
        symbol = f"{currency.upper()}USDT"
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            print(f"Leverage set to {leverage}x for {symbol}")
            return True
        except BinanceAPIException as e:
            print(f"Error setting leverage: {e}")
            return False

    def _place_stop_loss(self, symbol: str, side: str, stop_price: float) -> dict:
        """
        Place a position-reducing Stop Loss order (audit fix #2).

        Uses closePosition=True so the order can ONLY reduce/close the position
        and can never open a new one if left orphaned. Binance also auto-cancels
        the paired closePosition order when the position is closed.

        Args:
            symbol: Trading pair symbol
            side: 'SELL' for long positions, 'BUY' for short positions
            stop_price: Stop loss trigger price
        """
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="STOP_MARKET",
                stopPrice=stop_price,
                closePosition=True,
            )
            print(f"Stop Loss placed at ${stop_price:.2f}")
            return order
        except BinanceAPIException as e:
            print(f"Error placing Stop Loss: {e}")
            return {"error": str(e)}

    def _place_take_profit(self, symbol: str, side: str, tp_price: float) -> dict:
        """
        Place a position-reducing Take Profit order (audit fix #2).

        Uses closePosition=True for the same safety reason as the stop loss.

        Args:
            symbol: Trading pair symbol
            side: 'SELL' for long positions, 'BUY' for short positions
            tp_price: Take profit trigger price
        """
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="TAKE_PROFIT_MARKET",
                stopPrice=tp_price,
                closePosition=True,
            )
            print(f"Take Profit placed at ${tp_price:.2f}")
            return order
        except BinanceAPIException as e:
            print(f"Error placing Take Profit: {e}")
            return {"error": str(e)}

    def open_long_position(
        self,
        currency: str,
        quantity: float = None,
        stop_loss_price: float = None,
        take_profit_price: float = None,
        leverage: int = None,
    ) -> dict:
        """
        Open a Long position with mandatory Stop Loss and optional Take Profit.

        Args:
            currency (str): The currency symbol (e.g., 'BTC').
            quantity (float): The quantity to buy.
            stop_loss_price (float): Stop loss trigger price (REQUIRED).
            take_profit_price (float, optional): Take profit trigger price.
            leverage (int, optional): Leverage to use (1-125).

        Returns:
            dict: Summary with main order and SL/TP order IDs.

        Raises:
            ValueError: If stop_loss_price is not provided.
        """
        # Validate that stop loss is provided
        if stop_loss_price is None:
            raise ValueError("stop_loss_price is required. Cannot open a long position without a stop loss.")

        symbol = f"{currency.upper()}USDT"

        # Daily loss kill-switch (audit fix #4)
        if self._daily_loss_limit_breached():
            return {"error": "Daily loss limit reached - new positions are blocked.", "blocked": True}

        # Regime gate (phase-2 #2): never open in an undefined (no-edge) regime
        if self.enforce_regime and self.get_regime(currency) == "UNDEFINED":
            return {"error": "Regime is UNDEFINED (no clear trend/range) - not opening.", "blocked": True}

        # Leverage cap (phase-2 guardrail): the LLM cannot exceed the hard limit
        if self.max_leverage and leverage and leverage > self.max_leverage:
            return {"error": f"Leverage {leverage}x exceeds the {self.max_leverage}x cap.", "blocked": True}

        # Size the position in code from the 1% rule when quantity is omitted (phase-2 #2)
        if quantity is None:
            quantity = self.compute_quantity_for_risk(currency, stop_loss_price)
            if not quantity or quantity <= 0:
                return {"error": "Could not compute a valid position size for the given risk/stop.", "blocked": True}

        # Risk-per-trade cap (phase-2 guardrail)
        if self._trade_exceeds_risk_cap(currency, quantity, stop_loss_price):
            return {"error": f"Trade risk exceeds the {self.risk_per_trade_pct}% per-trade cap.", "blocked": True}

        # Portfolio-level caps: max concurrent positions and aggregate risk (phase-2 guardrail)
        portfolio_block = self._portfolio_limits_block(currency, quantity, stop_loss_price)
        if portfolio_block:
            return portfolio_block

        # Isolate margin before trading to bound blast radius (audit fix #5)
        self.set_margin_type(currency, "ISOLATED")

        # Leverage MUST apply; abort rather than trade at an unintended leverage (audit fix #5)
        if leverage and not self.set_leverage(currency, leverage):
            return {"error": f"Could not set leverage to {leverage}x; aborting to avoid trading at an unintended leverage."}

        # Conform to exchange precision (audit fix #18)
        quantity = self._round_quantity(symbol, quantity)
        stop_loss_price = self._round_price(symbol, stop_loss_price)
        if take_profit_price:
            take_profit_price = self._round_price(symbol, take_profit_price)

        # Reject sub-minimum notional before hitting the exchange (phase-2 #2)
        mark_for_notional = self.get_mark_price(currency)
        if self._below_min_notional(symbol, quantity, mark_for_notional):
            return {
                "error": f"Order notional ${quantity * mark_for_notional:.2f} is below the exchange minimum.",
                "blocked": True,
            }

        # Open main position (RESULT response type so avgPrice/entry is populated)
        main_order = self._place_order(
            symbol, Client.SIDE_BUY, quantity, Client.ORDER_TYPE_MARKET, newOrderRespType="RESULT"
        )

        if "error" in main_order or not main_order.get("orderId"):
            if "error" in main_order:
                return main_order
            return {"error": "Main order did not return an orderId.", "response": main_order}

        result = {
            "main_order_id": main_order.get("orderId"),
            "symbol": symbol,
            "side": "LONG",
            "quantity": quantity,
            "entry_price": float(main_order["avgPrice"]) if main_order.get("avgPrice") else None,
        }

        # Mandatory stop loss. If it cannot be placed, roll back the naked
        # position instead of running unprotected (audit fix #1).
        sl_order = self._place_stop_loss(symbol, Client.SIDE_SELL, stop_loss_price)
        if "error" in sl_order:
            rollback = self._place_order(symbol, Client.SIDE_SELL, quantity, Client.ORDER_TYPE_MARKET)
            return {
                "error": f"Stop loss could not be placed ({sl_order['error']}); position was rolled back "
                "to avoid running without protection.",
                "rolled_back": True,
                "rollback_order": rollback,
                "main_order_id": main_order.get("orderId"),
            }
        result["stop_loss_order_id"] = sl_order.get("orderId")
        result["stop_loss_price"] = stop_loss_price

        # Take profit is optional; a failure here is non-fatal (SL still protects).
        if take_profit_price:
            tp_order = self._place_take_profit(symbol, Client.SIDE_SELL, take_profit_price)
            if "error" not in tp_order:
                result["take_profit_order_id"] = tp_order.get("orderId")
                result["take_profit_price"] = take_profit_price
            else:
                result["take_profit_error"] = tp_order["error"]

        return result

    def open_short_position(
        self,
        currency: str,
        quantity: float = None,
        stop_loss_price: float = None,
        take_profit_price: float = None,
        leverage: int = None,
    ) -> dict:
        """
        Open a Short position with mandatory Stop Loss and optional Take Profit.

        Args:
            currency (str): The currency symbol (e.g., 'BTC').
            quantity (float): The quantity to sell.
            stop_loss_price (float): Stop loss trigger price (REQUIRED).
            take_profit_price (float, optional): Take profit trigger price.
            leverage (int, optional): Leverage to use (1-125).

        Returns:
            dict: Summary with main order and SL/TP order IDs.

        Raises:
            ValueError: If stop_loss_price is not provided.
        """
        # Validate that stop loss is provided
        if stop_loss_price is None:
            raise ValueError("stop_loss_price is required. Cannot open a short position without a stop loss.")

        symbol = f"{currency.upper()}USDT"

        # Daily loss kill-switch (audit fix #4)
        if self._daily_loss_limit_breached():
            return {"error": "Daily loss limit reached - new positions are blocked.", "blocked": True}

        # Regime gate (phase-2 #2): never open in an undefined (no-edge) regime
        if self.enforce_regime and self.get_regime(currency) == "UNDEFINED":
            return {"error": "Regime is UNDEFINED (no clear trend/range) - not opening.", "blocked": True}

        # Leverage cap (phase-2 guardrail): the LLM cannot exceed the hard limit
        if self.max_leverage and leverage and leverage > self.max_leverage:
            return {"error": f"Leverage {leverage}x exceeds the {self.max_leverage}x cap.", "blocked": True}

        # Size the position in code from the 1% rule when quantity is omitted (phase-2 #2)
        if quantity is None:
            quantity = self.compute_quantity_for_risk(currency, stop_loss_price)
            if not quantity or quantity <= 0:
                return {"error": "Could not compute a valid position size for the given risk/stop.", "blocked": True}

        # Risk-per-trade cap (phase-2 guardrail)
        if self._trade_exceeds_risk_cap(currency, quantity, stop_loss_price):
            return {"error": f"Trade risk exceeds the {self.risk_per_trade_pct}% per-trade cap.", "blocked": True}

        # Portfolio-level caps: max concurrent positions and aggregate risk (phase-2 guardrail)
        portfolio_block = self._portfolio_limits_block(currency, quantity, stop_loss_price)
        if portfolio_block:
            return portfolio_block

        # Isolate margin before trading to bound blast radius (audit fix #5)
        self.set_margin_type(currency, "ISOLATED")

        # Leverage MUST apply; abort rather than trade at an unintended leverage (audit fix #5)
        if leverage and not self.set_leverage(currency, leverage):
            return {"error": f"Could not set leverage to {leverage}x; aborting to avoid trading at an unintended leverage."}

        # Conform to exchange precision (audit fix #18)
        quantity = self._round_quantity(symbol, quantity)
        stop_loss_price = self._round_price(symbol, stop_loss_price)
        if take_profit_price:
            take_profit_price = self._round_price(symbol, take_profit_price)

        # Reject sub-minimum notional before hitting the exchange (phase-2 #2)
        mark_for_notional = self.get_mark_price(currency)
        if self._below_min_notional(symbol, quantity, mark_for_notional):
            return {
                "error": f"Order notional ${quantity * mark_for_notional:.2f} is below the exchange minimum.",
                "blocked": True,
            }

        # Open main position (RESULT response type so avgPrice/entry is populated)
        main_order = self._place_order(
            symbol, Client.SIDE_SELL, quantity, Client.ORDER_TYPE_MARKET, newOrderRespType="RESULT"
        )

        if "error" in main_order or not main_order.get("orderId"):
            if "error" in main_order:
                return main_order
            return {"error": "Main order did not return an orderId.", "response": main_order}

        result = {
            "main_order_id": main_order.get("orderId"),
            "symbol": symbol,
            "side": "SHORT",
            "quantity": quantity,
            "entry_price": float(main_order["avgPrice"]) if main_order.get("avgPrice") else None,
        }

        # Mandatory stop loss (BUY to close a short). Roll back if it fails (audit fix #1).
        sl_order = self._place_stop_loss(symbol, Client.SIDE_BUY, stop_loss_price)
        if "error" in sl_order:
            rollback = self._place_order(symbol, Client.SIDE_BUY, quantity, Client.ORDER_TYPE_MARKET)
            return {
                "error": f"Stop loss could not be placed ({sl_order['error']}); position was rolled back "
                "to avoid running without protection.",
                "rolled_back": True,
                "rollback_order": rollback,
                "main_order_id": main_order.get("orderId"),
            }
        result["stop_loss_order_id"] = sl_order.get("orderId")
        result["stop_loss_price"] = stop_loss_price

        # Take profit is optional; a failure here is non-fatal (SL still protects).
        if take_profit_price:
            tp_order = self._place_take_profit(symbol, Client.SIDE_BUY, take_profit_price)
            if "error" not in tp_order:
                result["take_profit_order_id"] = tp_order.get("orderId")
                result["take_profit_price"] = take_profit_price
            else:
                result["take_profit_error"] = tp_order["error"]

        return result

    def _place_order(self, symbol: str, side: str, quantity: float, order_type: str, **extra) -> dict:
        """
        Helper to place a futures order.
        """
        try:
            print(f"Placing {side} {order_type} order for {quantity} {symbol}...")
            # Note: This executes a REAL order if connected to a live account!
            order = self.client.futures_create_order(
                symbol=symbol, side=side, type=order_type, quantity=quantity, **extra
            )
            return order
        except BinanceAPIException as e:
            print(f"Error placing order: {e}")
            return {"error": str(e)}

    def get_open_position(self, currency: str) -> float:
        """
        Get the current open position amount for a currency.
        Positive = Long, Negative = Short, 0 = No position.
        """
        symbol = f"{currency.upper()}USDT"
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            for p in positions:
                if p["symbol"] == symbol:
                    return float(p["positionAmt"])
            return 0.0
        except BinanceAPIException as e:
            print(f"Error fetching position: {e}")
            return 0.0

    def close_position(self, currency: str) -> dict:
        """
        Close the current open position for the given currency and cancel any
        associated SL/TP orders so no orphan reduce-only order remains that could
        later re-open a position (audit fix #3).
        """
        symbol = f"{currency.upper()}USDT"
        amount = self.get_open_position(currency)

        if amount == 0:
            # No position, but still clear any dangling orders for the symbol.
            self._cancel_symbol_orders(symbol)
            print(f"No open position for {currency}.")
            return {"status": "NO_POSITION"}

        side = Client.SIDE_SELL if amount > 0 else Client.SIDE_BUY
        quantity = abs(amount)

        print(f"Closing position for {currency}: {side} {quantity}")
        close_order = self._place_order(symbol, side, quantity, Client.ORDER_TYPE_MARKET)

        # Cancel associated SL/TP after flattening.
        self._cancel_symbol_orders(symbol)

        return close_order

    def _cancel_symbol_orders(self, symbol: str) -> None:
        """Best-effort cancel of all open orders for a symbol."""
        try:
            self.client.futures_cancel_all_open_orders(symbol=symbol)
        except BinanceAPIException as e:
            print(f"Error cancelling orders for {symbol}: {e}")

    def get_all_open_positions(self) -> list:
        """
        Get all open futures positions with associated orders and risk metrics.

        Returns:
            list: List of dictionaries with comprehensive position information including:
                  - Position details (amount, entry price, PnL, leverage)
                  - Associated orders (stop-loss, take-profit, limit orders)
                  - Risk metrics (liquidation price, mark price, margin ratio)
        """
        try:
            positions = self.client.futures_position_information()
            # Fetch all open orders once to avoid multiple API calls
            all_orders = self.client.futures_get_open_orders()

            open_positions = []

            for p in positions:
                position_amt = float(p["positionAmt"])
                if position_amt != 0:
                    symbol = p["symbol"]

                    # Filter orders for this symbol
                    symbol_orders = [o for o in all_orders if o["symbol"] == symbol]

                    # Categorize orders by type
                    stop_loss_orders = []
                    take_profit_orders = []
                    limit_orders = []

                    for order in symbol_orders:
                        order_info = {
                            "order_id": order["orderId"],
                            "type": order["type"],
                            "side": order["side"],
                            "price": float(order.get("price", 0)),
                            "stop_price": float(order.get("stopPrice", 0)),
                            "quantity": float(order["origQty"]),
                            "status": order["status"],
                            "time": order["time"],
                        }

                        if order["type"] in ["STOP_MARKET", "STOP"]:
                            stop_loss_orders.append(order_info)
                        elif order["type"] in ["TAKE_PROFIT_MARKET", "TAKE_PROFIT"]:
                            take_profit_orders.append(order_info)
                        elif order["type"] == "LIMIT":
                            limit_orders.append(order_info)

                    # Build comprehensive position info
                    position_info = {
                        "symbol": symbol,
                        "position_amount": position_amt,
                        "entry_price": float(p.get("entryPrice", 0)),
                        "mark_price": float(p.get("markPrice", 0)),
                        "liquidation_price": float(p.get("liquidationPrice", 0)),
                        "unrealized_pnl": float(p.get("unRealizedProfit", 0)),
                        "leverage": int(p.get("leverage", 1)),
                        "side": "LONG" if position_amt > 0 else "SHORT",
                        "margin_type": p.get("marginType", "cross"),
                        "isolated_wallet": float(p.get("isolatedWallet", 0)),
                        "position_initial_margin": float(p.get("positionInitialMargin", 0)),
                        # Associated orders
                        "stop_loss_orders": stop_loss_orders,
                        "take_profit_orders": take_profit_orders,
                        "limit_orders": limit_orders,
                        "total_orders": len(symbol_orders),
                    }

                    open_positions.append(position_info)

            return open_positions
        except BinanceAPIException as e:
            print(f"Error fetching all positions: {e}")
            return []

    def get_futures_balance(self) -> dict:
        """
        Get the futures account balance information.

        Returns:
            dict: Dictionary with balance information including total balance, available balance, and unrealized PnL.
        """
        try:
            account_info = self.client.futures_account()

            # Extract relevant balance information
            total_balance = float(account_info.get("totalWalletBalance", 0))
            available_balance = float(account_info.get("availableBalance", 0))
            total_unrealized_pnl = float(account_info.get("totalUnrealizedProfit", 0))
            total_margin_balance = float(account_info.get("totalMarginBalance", 0))

            # Get individual asset balances
            assets = []
            for asset in account_info.get("assets", []):
                wallet_balance = float(asset.get("walletBalance", 0))
                if wallet_balance > 0:  # Only include assets with balance
                    assets.append(
                        {
                            "asset": asset.get("asset"),
                            "wallet_balance": wallet_balance,
                            "unrealized_profit": float(asset.get("unrealizedProfit", 0)),
                            "margin_balance": float(asset.get("marginBalance", 0)),
                            "available_balance": float(asset.get("availableBalance", 0)),
                        }
                    )

            return {
                "total_wallet_balance": total_balance,
                "total_margin_balance": total_margin_balance,
                "available_balance": available_balance,
                "total_unrealized_pnl": total_unrealized_pnl,
                "assets": assets,
            }
        except BinanceAPIException as e:
            print(f"Error fetching futures balance: {e}")
            return {
                "total_wallet_balance": 0,
                "total_margin_balance": 0,
                "available_balance": 0,
                "total_unrealized_pnl": 0,
                "assets": [],
            }

    def get_available_futures_symbols(self, quote_asset: str = "USDT") -> list:
        """
        Get all available futures trading symbols.

        Args:
            quote_asset (str): Filter by quote asset (default: 'USDT').

        Returns:
            list: List of dictionaries with symbol information.
        """
        try:
            exchange_info = self.client.futures_exchange_info()
            symbols = []

            for symbol_info in exchange_info.get("symbols", []):
                # Filter by quote asset and only include PERPETUAL contracts
                if (
                    symbol_info.get("quoteAsset") == quote_asset
                    and symbol_info.get("contractType") == "PERPETUAL"
                    and symbol_info.get("status") == "TRADING"
                ):

                    symbols.append(
                        {
                            "symbol": symbol_info.get("symbol"),
                            "base_asset": symbol_info.get("baseAsset"),
                            "quote_asset": symbol_info.get("quoteAsset"),
                            "price_precision": symbol_info.get("pricePrecision"),
                            "quantity_precision": symbol_info.get("quantityPrecision"),
                        }
                    )

            return sorted(symbols, key=lambda x: x["symbol"])

        except BinanceAPIException as e:
            print(f"Error fetching futures symbols: {e}")
            return []

    def cancel_all_open_orders(self, symbol: str = None) -> dict:
        """
        Cancel all open orders for futures.

        Args:
            symbol (str, optional): If provided, only cancel orders for this symbol.
                                   If None, cancel all orders for all symbols.

        Returns:
            dict: Summary of cancelled orders.
        """
        try:
            cancelled_orders = []

            if symbol:
                # Cancel orders for specific symbol
                result = self.client.futures_cancel_all_open_orders(symbol=symbol)
                cancelled_orders.append({"symbol": symbol, "result": result})
                print(f"✓ Cancelled all open orders for {symbol}")
            else:
                # Get all open orders first
                all_orders = self.client.futures_get_open_orders()

                if not all_orders:
                    print("No open orders to cancel.")
                    return {"cancelled_count": 0, "orders": []}

                # Group by symbol
                symbols_with_orders = set(order["symbol"] for order in all_orders)

                # Cancel for each symbol
                for sym in symbols_with_orders:
                    result = self.client.futures_cancel_all_open_orders(symbol=sym)
                    cancelled_orders.append({"symbol": sym, "result": result})
                    print(f"✓ Cancelled all open orders for {sym}")

            return {"cancelled_count": len(cancelled_orders), "orders": cancelled_orders}

        except BinanceAPIException as e:
            print(f"Error cancelling orders: {e}")
            return {"error": str(e), "cancelled_count": 0, "orders": []}

    def get_daily_pnl(self, include_unrealized: bool = True) -> dict:
        """
        Get today's realized PnL and trade statistics.

        Args:
            include_unrealized (bool): If True, includes unrealized PnL from open positions 
                                      to match Binance's total daily PnL display (default: True)

        Returns:
            dict: Daily performance metrics including realized PnL, unrealized PnL, 
                  total daily PnL, and trade count.
        """
        try:
            # Compute today's start first so we can scope the API query to it and
            # avoid truncating a high-volume day (audit fix #17).
            from datetime import datetime, timezone

            today_start = int(
                datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000
            )

            # Get income history (realized PnL) scoped to today.
            income = self.client.futures_income_history(
                incomeType="REALIZED_PNL", startTime=today_start, limit=1000
            )

            today_trades = [i for i in income if i["time"] >= today_start]
            today_realized_pnl = sum(float(i["income"]) for i in today_trades)

            # Get unrealized PnL from open positions if requested
            unrealized_pnl = 0
            if include_unrealized:
                balance_info = self.get_futures_balance()
                unrealized_pnl = balance_info.get("total_unrealized_pnl", 0)

            # Calculate total daily PnL (matches Binance's display)
            total_daily_pnl = today_realized_pnl + unrealized_pnl

            # Calculate win rate
            winning_trades = sum(1 for i in today_trades if float(i["income"]) > 0)
            total_trades = len(today_trades)
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            return {
                "daily_realized_pnl": today_realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "total_daily_pnl": total_daily_pnl,
                "trade_count": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": total_trades - winning_trades,
                "win_rate": win_rate,
            }
        except BinanceAPIException as e:
            print(f"Error fetching daily PnL: {e}")
            return {
                "daily_realized_pnl": 0,
                "unrealized_pnl": 0,
                "total_daily_pnl": 0,
                "trade_count": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
            }

    def get_recent_trades(self, currency: str, limit: int = 10) -> list:
        """
        Get recent executed trades for a specific currency.

        Args:
            currency (str): The currency symbol (e.g., 'BTC').
            limit (int): Number of recent trades to fetch (default: 10).

        Returns:
            list: Recent trades with execution details and PnL.
        """
        symbol = f"{currency.upper()}USDT"
        try:
            trades = self.client.futures_account_trades(symbol=symbol, limit=limit)

            return [
                {
                    "symbol": t["symbol"],
                    "trade_id": t["id"],
                    "order_id": t["orderId"],
                    "side": t["side"],
                    "price": float(t["price"]),
                    "quantity": float(t["qty"]),
                    "realized_pnl": float(t["realizedPnl"]),
                    "commission": float(t["commission"]),
                    "commission_asset": t["commissionAsset"],
                    "time": t["time"],
                    "is_maker": t["maker"],
                }
                for t in trades
            ]
        except BinanceAPIException as e:
            print(f"Error fetching recent trades for {currency}: {e}")
            return []

    def get_order_book_depth(self, currency: str, limit: int = 10) -> dict:
        """
        Get order book depth for market liquidity analysis.

        Args:
            currency (str): The currency symbol (e.g., 'BTC').
            limit (int): Number of price levels to fetch (default: 10).

        Returns:
            dict: Order book with bid/ask levels and volumes.
        """
        symbol = f"{currency.upper()}USDT"
        try:
            depth = self.client.futures_order_book(symbol=symbol, limit=limit)

            # Calculate total volumes
            bid_volume = sum(float(q) for _, q in depth["bids"])
            ask_volume = sum(float(q) for _, q in depth["asks"])

            # Get top 5 levels for display
            top_bids = [(float(p), float(q)) for p, q in depth["bids"][:5]]
            top_asks = [(float(p), float(q)) for p, q in depth["asks"][:5]]

            # Calculate spread
            best_bid = float(depth["bids"][0][0]) if depth["bids"] else 0
            best_ask = float(depth["asks"][0][0]) if depth["asks"] else 0
            spread = best_ask - best_bid
            spread_percentage = (spread / best_bid * 100) if best_bid > 0 else 0

            return {
                "symbol": symbol,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": spread,
                "spread_percentage": spread_percentage,
                "top_bids": top_bids,
                "top_asks": top_asks,
                "total_bid_volume": bid_volume,
                "total_ask_volume": ask_volume,
                "bid_ask_ratio": bid_volume / ask_volume if ask_volume > 0 else 0,
            }
        except BinanceAPIException as e:
            print(f"Error fetching order book for {currency}: {e}")
            return {
                "symbol": symbol,
                "best_bid": 0,
                "best_ask": 0,
                "spread": 0,
                "spread_percentage": 0,
                "top_bids": [],
                "top_asks": [],
                "total_bid_volume": 0,
                "total_ask_volume": 0,
                "bid_ask_ratio": 0,
            }

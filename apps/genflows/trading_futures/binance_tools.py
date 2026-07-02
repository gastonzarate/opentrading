from llama_index.core.tools import FunctionTool
from tradings.models import TradingOperation

from services.backtest_service import BacktestService
from services.binance_client import BinanceClient


class BinanceTools:
    """
    Wrapper class to expose BinanceClient trading functions as LlamaIndex FunctionTools.
    """

    def __init__(self, binance_client: BinanceClient):
        """
        Initialize BinanceTools with a BinanceClient instance.

        Args:
            binance_client (BinanceClient): An initialized BinanceClient instance.
        """
        self.binance_client = binance_client
        self.backtest_service = BacktestService(binance_client)

    def list_tools(self) -> list[FunctionTool]:
        """
        Returns a list of FunctionTool objects for trading operations.

        Returns:
            list[FunctionTool]: List of LlamaIndex FunctionTools for trading.
        """
        return [
            FunctionTool.from_defaults(
                fn=self._open_long_position,
                name="open_long_position",
                description=(
                    "Opens a long position (buy) on a cryptocurrency futures contract. "
                    "Use this when you expect the price to increase.\n\n"
                    "⚠️ MANDATORY RISK MANAGEMENT: stop_loss_price is REQUIRED. "
                    "The function will ERROR if you attempt to open a position without a stop loss.\n\n"
                    "CRITICAL PARAMETER REQUIREMENTS:\n"
                    "- currency: Use ONLY the base currency name (e.g., 'BTC', 'ETH', 'SOL'). "
                    "NEVER include 'USDT' suffix (e.g., 'BTCUSDT' is WRONG).\n"
                    "- quantity: Must be rounded correctly:\n"
                    "  * BTC/ETH: Exactly 3 decimals (e.g., 0.001, 0.002, 0.003)\n"
                    "  * Other coins: 1-2 decimals or whole numbers\n"
                    "  * Calculate: (Available_Balance × Leverage) / Current_Price, then round\n"
                    "- leverage: Integer 1-125. Recommended: 1-10x for safety\n"
                    "- stop_loss_price: ⚠️ MANDATORY ⚠️ "
                    "Function will fail without this.\n"
                    "- take_profit_price: RECOMMENDED. Set minimum 1:2 risk-reward ratio\n\n"
                    "MINIMUM ORDER SIZE: quantity × price × leverage MUST be ≥ $100 USD\n\n"
                    "EXAMPLE: If BTC=$100,000, available_balance=$50, leverage=5x:\n"
                    "  quantity = ($50 × 5) / $100,000 = 0.0025 → round to 0.002 (3 decimals)\n"
                    "  notional = 0.002 × $100,000 × 5 = $1,000 ✓ (≥$100)\n"
                    "  stop_loss = $98,000 (2% below) ← MANDATORY\n"
                    "  take_profit = $104,000 (4% above) ← RECOMMENDED\n\n"
                    "Best practices: Always calculate exact values, never guess. "
                    "If balance is too low to meet $100 minimum, explain to user instead of attempting trade."
                ),
            ),
            FunctionTool.from_defaults(
                fn=self._open_short_position,
                name="open_short_position",
                description=(
                    "Opens a short position (sell) on a cryptocurrency futures contract. "
                    "Use this when you expect the price to decrease.\n\n"
                    "⚠️ MANDATORY RISK MANAGEMENT: stop_loss_price is REQUIRED. "
                    "The function will ERROR if you attempt to open a position without a stop loss.\n\n"
                    "CRITICAL PARAMETER REQUIREMENTS:\n"
                    "- currency: Use ONLY the base currency name (e.g., 'BTC', 'ETH', 'SOL'). "
                    "NEVER include 'USDT' suffix (e.g., 'BTCUSDT' is WRONG).\n"
                    "- quantity: Must be rounded correctly:\n"
                    "  * BTC/ETH: Exactly 3 decimals (e.g., 0.001, 0.002, 0.003)\n"
                    "  * Other coins: 1-2 decimals or whole numbers\n"
                    "  * Calculate: (Available_Balance × Leverage) / Current_Price, then round\n"
                    "- leverage: Integer 1-125. Recommended: 1-10x for safety\n"
                    "- stop_loss_price: ⚠️ MANDATORY ⚠️ "
                    "Function will fail without this.\n"
                    "- take_profit_price: RECOMMENDED. Set minimum 1:2 risk-reward ratio BELOW current price\n\n"
                    "MINIMUM ORDER SIZE: quantity × price × leverage MUST be ≥ $100 USD\n\n"
                    "EXAMPLE: If ETH=$3,500, available_balance=$30, leverage=3x:\n"
                    "  quantity = ($30 × 3) / $3,500 = 0.0257 → round to 0.025 (3 decimals)\n"
                    "  notional = 0.025 × $3,500 × 3 = $262.50 ✓ (≥$100)\n"
                    "  stop_loss = $3,605 (3% above) ← MANDATORY\n"
                    "  take_profit = $3,290 (6% below) ← RECOMMENDED\n\n"
                    "⚠️ WARNING: Short positions carry unlimited theoretical risk. Stop losses are CRITICAL. "
                    "Monitor funding rates - negative rates favor shorts, positive rates favor longs. "
                    "Always calculate exact values, never guess."
                ),
            ),
            FunctionTool.from_defaults(
                fn=self._close_position,
                name="close_position",
                description=(
                    "Closes the current open position for a specified cryptocurrency. "
                    "Use this to exit a trade, either to take profits, cut losses, or rebalance portfolio.\n\n"
                    "PARAMETER REQUIREMENTS:\n"
                    "- currency: Use ONLY the base currency name (e.g., 'BTC', 'ETH', 'SOL'). "
                    "NEVER include 'USDT' suffix.\n\n"
                    "This function automatically:\n"
                    "- Detects whether the position is long or short\n"
                    "- Closes the entire position at market price\n"
                    "- Cancels any associated stop loss or take profit orders\n\n"
                    "Best practices: Close positions when stop loss or take profit targets are hit. "
                    "Consider partial exits to lock in profits while maintaining exposure. "
                    "Monitor market conditions and close positions if the original trade thesis is invalidated. "
                    "Avoid emotional decision-making - stick to your trading plan."
                ),
            ),
            FunctionTool.from_defaults(
                fn=self._backtest_strategy,
                name="backtest_strategy",
                description=(
                    "Simula cómo habría funcionado una estrategia de trading "
                    "basándose en condiciones de mercado similares en el pasado.\n\n"
                    "⚠️ USA ESTA HERRAMIENTA ANTES de abrir una posición para validar "
                    "que las condiciones actuales históricamente han sido rentables.\n\n"
                    "PARÁMETROS:\n"
                    "- currency: Base currency (ej: 'BTC', 'ETH'). NO incluir 'USDT'.\n"
                    "- direction: 'LONG' o 'SHORT'\n"
                    "- current_rsi: RSI actual (del market data)\n"
                    "- current_macd: MACD actual (del market data)\n"
                    "- current_price: Precio actual\n"
                    "- current_ema_9: EMA(9) actual\n"
                    "- current_funding_rate: Funding rate actual (opcional)\n"
                    "- lookback_days: Días de historia a analizar (default: 7)\n"
                    "- stop_loss_pct: % de stop loss a simular (default: 2.0)\n"
                    "- take_profit_pct: % de take profit a simular (default: 4.0)\n\n"
                    "RETORNA métricas para ayudar en la decisión:\n"
                    "- win_rate: % de trades ganadores\n"
                    "- avg_profit_pct: Ganancia promedio por trade\n"
                    "- expectancy: Ganancia esperada por trade\n"
                    "- profit_factor: Ratio ganancias/pérdidas\n"
                    "- similar_setups_found: Cuántas condiciones similares se encontraron\n\n"
                    "EJEMPLO DE USO:\n"
                    "Antes de abrir LONG en BTC, llamar:\n"
                    "backtest_strategy(currency='BTC', direction='LONG', "
                    "current_rsi=28.5, current_macd=-150.2, current_price=105000, "
                    "current_ema_9=104500, stop_loss_pct=2.0, take_profit_pct=4.0)\n\n"
                    "Si win_rate < 50% o expectancy < 0, considera NO operar."
                ),
            ),
        ]

    def _open_long_position(
        self,
        currency: str,
        quantity: float,
        stop_loss_price: float = None,
        take_profit_price: float = None,
        leverage: int = None,
    ) -> dict:
        """
        Wrapper for BinanceClient.open_long_position.

        Args:
            currency (str): The base currency symbol ONLY (e.g., 'BTC', 'ETH', 'SOL').
                           DO NOT include 'USDT' suffix.
            quantity (float): The quantity to buy, properly rounded:
                             - BTC/ETH: 3 decimals (e.g., 0.001, 0.002)
                             - Others: 1-2 decimals or whole numbers
            stop_loss_price (float): REQUIRED. Stop loss trigger price (1-3% below entry).
            take_profit_price (float, optional): Take profit trigger price (minimum 1:2 risk-reward).
            leverage (int, optional): Leverage to use (1-125). Recommended: 1-10x.

        Returns:
            dict: Summary with main order and SL/TP order IDs.

        Example:
            >>> _open_long_position(
            ...     currency="BTC",  # Not "BTCUSDT"
            ...     quantity=0.002,  # 3 decimals
            ...     leverage=5,
            ...     stop_loss_price=98000.0,
            ...     take_profit_price=104000.0
            ... )
        """
        # Create operation record
        operation = TradingOperation.objects.create(
            operation_type=TradingOperation.OperationType.OPEN_LONG,
            currency=currency,
            quantity=quantity,
            leverage=leverage,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            status=TradingOperation.Status.PENDING,
        )

        try:
            result = self.binance_client.open_long_position(
                currency=currency,
                quantity=quantity,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                leverage=leverage,
            )

            # Update operation with success result
            operation.status = TradingOperation.Status.SUCCESS
            operation.result_data = result
            operation.main_order_id = result.get("main_order_id")
            operation.entry_price = result.get("entry_price")
            operation.stop_loss_order_id = result.get("stop_loss_order_id")
            operation.take_profit_order_id = result.get("take_profit_order_id")
            operation.save()

            return result

        except Exception as e:
            # Update operation with error
            operation.status = TradingOperation.Status.ERROR
            operation.error_message = str(e)
            operation.save()
            raise e

    def _open_short_position(
        self,
        currency: str,
        quantity: float,
        stop_loss_price: float = None,
        take_profit_price: float = None,
        leverage: int = None,
    ) -> dict:
        """
        Wrapper for BinanceClient.open_short_position.

        Args:
            currency (str): The base currency symbol ONLY (e.g., 'BTC', 'ETH', 'SOL').
                           DO NOT include 'USDT' suffix.
            quantity (float): The quantity to sell, properly rounded:
                             - BTC/ETH: 3 decimals (e.g., 0.001, 0.002)
                             - Others: 1-2 decimals or whole numbers
            stop_loss_price (float): REQUIRED. Stop loss trigger price (1-3% ABOVE entry for shorts).
            take_profit_price (float, optional): Take profit trigger price (minimum 1:2 risk-reward BELOW entry).
            leverage (int, optional): Leverage to use (1-125). Recommended: 1-10x.

        Returns:
            dict: Summary with main order and SL/TP order IDs.

        Example:
            >>> _open_short_position(
            ...     currency="ETH",  # Not "ETHUSDT"
            ...     quantity=0.025,  # 3 decimals
            ...     leverage=3,
            ...     stop_loss_price=3605.0,  # Above entry
            ...     take_profit_price=3290.0  # Below entry
            ... )
        """
        # Create operation record
        operation = TradingOperation.objects.create(
            operation_type=TradingOperation.OperationType.OPEN_SHORT,
            currency=currency,
            quantity=quantity,
            leverage=leverage,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            status=TradingOperation.Status.PENDING,
        )

        try:
            result = self.binance_client.open_short_position(
                currency=currency,
                quantity=quantity,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                leverage=leverage,
            )

            # Update operation with success result
            operation.status = TradingOperation.Status.SUCCESS
            operation.result_data = result
            operation.main_order_id = result.get("main_order_id")
            operation.entry_price = result.get("entry_price")
            operation.stop_loss_order_id = result.get("stop_loss_order_id")
            operation.take_profit_order_id = result.get("take_profit_order_id")
            operation.save()

            return result

        except Exception as e:
            # Update operation with error
            operation.status = TradingOperation.Status.ERROR
            operation.error_message = str(e)
            operation.save()
            raise e

    def _close_position(self, currency: str) -> dict:
        """
        Wrapper for BinanceClient.close_position.

        Args:
            currency (str): The base currency symbol ONLY (e.g., 'BTC', 'ETH', 'SOL').
                           DO NOT include 'USDT' suffix.

        Returns:
            dict: Order details or status message.

        Example:
            >>> _close_position(currency="BTC")  # Not "BTCUSDT"
        """
        # Create operation record
        operation = TradingOperation.objects.create(
            operation_type=TradingOperation.OperationType.CLOSE_POSITION,
            currency=currency,
            status=TradingOperation.Status.PENDING,
        )

        try:
            result = self.binance_client.close_position(currency=currency)

            # Update operation with success result
            operation.status = TradingOperation.Status.SUCCESS
            operation.result_data = result
            operation.main_order_id = result.get("orderId")
            operation.save()

            return result

        except Exception as e:
            # Update operation with error
            operation.status = TradingOperation.Status.ERROR
            operation.error_message = str(e)
            operation.save()
            raise e

    def _backtest_strategy(
        self,
        currency: str,
        direction: str,
        current_rsi: float,
        current_macd: float,
        current_price: float,
        current_ema_9: float,
        current_funding_rate: float = 0.0,
        current_atr: float = None,
        lookback_days: int = 30,
        stop_loss_pct: float = 2.0,
        take_profit_pct: float = 4.0,
    ) -> dict:
        """
        Wrapper for BacktestService.backtest_strategy().

        Args:
            currency: Base currency symbol (e.g., 'BTC', 'ETH').
            direction: Trade direction ('LONG' or 'SHORT').
            current_rsi: Current RSI value from market data.
            current_macd: Current MACD value from market data.
            current_price: Current price.
            current_ema_9: Current EMA(9) value.
            current_funding_rate: Current funding rate (optional).
            current_atr: Current ATR value (optional).
            lookback_days: Days of historical data to analyze (default: 7).
            stop_loss_pct: Stop loss percentage to simulate (default: 2.0).
            take_profit_pct: Take profit percentage to simulate (default: 4.0).

        Returns:
            dict: Backtest results with performance metrics.

        Example:
            >>> _backtest_strategy(
            ...     currency="BTC",
            ...     direction="LONG",
            ...     current_rsi=28.5,
            ...     current_macd=-150.2,
            ...     current_price=105000,
            ...     current_ema_9=104500,
            ...     lookback_days=7,
            ...     stop_loss_pct=2.0,
            ...     take_profit_pct=4.0
            ... )
        """
        current_conditions = {
            "rsi": current_rsi,
            "macd": current_macd,
            "price": current_price,
            "ema_9": current_ema_9,
            "funding_rate": current_funding_rate,
        }

        if current_atr is not None:
            current_conditions["atr"] = current_atr

        return self.backtest_service.backtest_strategy(
            currency=currency,
            direction=direction,
            current_conditions=current_conditions,
            lookback_days=lookback_days,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )

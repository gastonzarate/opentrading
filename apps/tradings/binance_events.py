"""
Event-driven wake-ups from Binance's User Data Stream.

On top of the agent's self-chosen cadence, real account events (an order filling,
a stop-loss or take-profit executing) trigger an immediate re-evaluation so the
bot reacts the instant a position changes instead of waiting for its next timer.

Binance pushes these via the futures user data websocket as `ORDER_TRADE_UPDATE`
messages (status FILLED / PARTIALLY_FILLED). The pure helpers here (filter +
debounce) are unit-tested; the websocket wiring is thin glue.
"""
import logging

logger = logging.getLogger(__name__)

# Order statuses that mean a position/exposure actually changed.
_FILL_STATUSES = {"FILLED", "PARTIALLY_FILLED"}


def should_wake_on_event(msg: dict) -> bool:
    """
    True when a Binance user-data message means exposure changed and the agent
    should re-evaluate now: an order (entry, stop-loss, take-profit, or close)
    got (partially) filled.
    """
    if not isinstance(msg, dict):
        return False
    if msg.get("e") != "ORDER_TRADE_UPDATE":
        return False
    order = msg.get("o") or {}
    return order.get("X") in _FILL_STATUSES


def describe_event(msg: dict) -> str:
    """Short human description of a wake-worthy event, for logging."""
    o = msg.get("o") or {}
    return f"{o.get('o', '?')} {o.get('S', '?')} {o.get('s', '?')} -> {o.get('X', '?')}"


class EventDebouncer:
    """Allows at most one wake per `min_seconds` window (avoids event storms)."""

    def __init__(self, min_seconds: float = 10.0):
        self.min_seconds = min_seconds
        self._last = None

    def should_fire(self, now: float) -> bool:
        if self._last is None or (now - self._last) >= self.min_seconds:
            self._last = now
            return True
        return False


def start_user_stream(api_key, api_secret, on_wake, testnet: bool = False, min_debounce_seconds: float = 10.0):
    """
    Start the futures user-data websocket and call `on_wake()` (debounced) whenever
    a fill occurs. Returns the ThreadedWebsocketManager so the caller can stop it.
    Returns None if credentials are missing.
    """
    if not api_key or not api_secret:
        logger.warning("⏭️  Binance event stream not started: missing API credentials")
        return None

    import time

    from binance import ThreadedWebsocketManager

    debouncer = EventDebouncer(min_debounce_seconds)
    twm = ThreadedWebsocketManager(api_key=api_key, api_secret=api_secret, testnet=testnet)
    twm.start()

    def _handle(msg):
        try:
            if should_wake_on_event(msg) and debouncer.should_fire(time.time()):
                logger.info(f"⚡ Binance event -> waking agent: {describe_event(msg)}")
                on_wake()
        except Exception as e:  # never let a socket callback crash the stream
            logger.error(f"Error handling Binance event: {e}", exc_info=True)

    twm.start_futures_user_socket(callback=_handle)
    logger.info("✅ Binance user-data stream started (event-driven wake-ups enabled)")
    return twm

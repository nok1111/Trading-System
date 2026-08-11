"""WebSocket client for Binance real-time price streaming with auto-reconnect."""

import asyncio
import json
import logging
from collections.abc import Callable as _Callable
from decimal import Decimal
from threading import Event, Thread
from time import time
from typing import Callable, Optional

import websockets

logger = logging.getLogger(__name__)

_BINANCE_WS_BASE = "wss://stream.binance.com:9443/stream"
_BINANCE_WS_TESTNET = "wss://testnet.binance.vision/stream"


class PriceStream:
    """Manages a WebSocket connection to Binance for real-time price updates.

    Runs in a background thread with its own asyncio event loop.
    Auto-reconnects on disconnect with exponential backoff.
    """

    def __init__(
        self,
        symbols: list[str],
        on_price: Optional[Callable[[str, Decimal, float], None]] = None,
        testnet: bool = False,
        reconnect_interval: float = 1.0,
        max_reconnect_interval: float = 30.0,
    ) -> None:
        self._symbols = [s.lower() for s in symbols]
        self._on_price = on_price
        self._testnet = testnet
        self._reconnect_interval = reconnect_interval
        self._max_reconnect_interval = max_reconnect_interval
        self._thread: Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event = Event()
        self._prices: dict[str, Decimal] = {}
        self._timestamps: dict[str, float] = {}
        self._connected = False
        self._reconnect_count = 0
        self._last_message_time: float = 0.0
        self._ws = None
        self._subscribers: list[Callable[[str, Decimal, float], None]] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    def get_price(self, symbol: str) -> Decimal | None:
        return self._prices.get(symbol.upper())

    def get_all_prices(self) -> dict[str, Decimal]:
        return dict(self._prices)

    def get_last_update_age(self) -> float:
        """Seconds since last message received. -1 if never."""
        if self._last_message_time == 0.0:
            return -1.0
        return time() - self._last_message_time

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("PriceStream started for symbols: %s", self._symbols)

    def stop(self) -> None:
        self._stop_event.set()
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._cancel_ws(), self._loop)
        if self._thread:
            self._thread.join(timeout=5)
        self._connected = False
        logger.info("PriceStream stopped")

    def add_symbol(self, symbol: str) -> None:
        """Add a symbol to the stream and reconnect to activate it immediately."""
        sym = symbol.lower()
        if sym not in self._symbols:
            self._symbols.append(sym)
            logger.info("Added symbol %s to stream, reconnecting to activate", sym)
            # Close current WS to force reconnect with updated symbol list
            if self._ws and not self._ws.closed:
                try:
                    asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
                except Exception:
                    pass
        else:
            logger.debug("Symbol %s already in stream", sym)

    def add_subscriber(self, callback: Callable[[str, Decimal, float], None]) -> None:
        """Register a callback that gets called on every price update."""
        self._subscribers.append(callback)

    def remove_subscriber(self, callback: Callable[[str, Decimal, float], None]) -> None:
        """Remove a previously registered subscriber callback."""
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_loop())

    async def _cancel_ws(self) -> None:
        """Close the active WebSocket to unblock _connect_and_listen."""
        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._connected = False

    async def _connect_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._connect_and_listen()
            except Exception as exc:
                self._connected = False
                self._reconnect_count += 1
                backoff = min(
                    self._reconnect_interval * (2 ** min(self._reconnect_count, 5)),
                    self._max_reconnect_interval,
                )
                logger.warning(
                    "WebSocket disconnected: %s. Reconnecting in %.1fs (attempt #%d)",
                    exc,
                    backoff,
                    self._reconnect_count,
                )
                await asyncio.sleep(backoff)

    async def _connect_and_listen(self) -> None:
        base = _BINANCE_WS_TESTNET if self._testnet else _BINANCE_WS_BASE
        streams = "/".join(f"{s}@miniTicker" for s in self._symbols)
        url = f"{base}?streams={streams}"

        logger.info("Connecting to Binance WebSocket: %s", url)
        async with websockets.connect(
            url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
            max_size=2**20,
        ) as ws:
            self._ws = ws
            self._connected = True
            self._reconnect_count = 0
            logger.info("WebSocket connected. Listening for price updates...")

            while not self._stop_event.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=60.0)
                except TimeoutError:
                    await ws.ping()
                    continue

                self._last_message_time = time()
                self._handle_message(raw)

    def _handle_message(self, raw: str | bytes) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        stream_data = data.get("data", data)
        symbol = stream_data.get("s", "").upper()
        price_str = stream_data.get("c")

        if not symbol or not price_str:
            return

        price = Decimal(str(price_str))
        self._prices[symbol] = price
        self._timestamps[symbol] = time()

        # Prune stale entries: remove symbols not updated in 10 min
        # This prevents unbounded growth if symbols are added/removed dynamically
        if len(self._prices) > len(self._symbols) * 2:
            cutoff = time() - 600  # 10 minutes
            stale = [s for s, ts in self._timestamps.items() if ts < cutoff]
            for s in stale:
                self._prices.pop(s, None)
                self._timestamps.pop(s, None)

        if self._on_price:
            try:
                self._on_price(symbol, price, self._timestamps[symbol])
            except Exception:
                logger.exception("Error in on_price callback for %s", symbol)

        # Notify all subscribers
        for sub in list(self._subscribers):
            try:
                sub(symbol, price, self._timestamps[symbol])
            except Exception:
                logger.exception("Error in subscriber callback for %s", symbol)


# Singleton instance
_price_stream: PriceStream | None = None


def get_price_stream() -> PriceStream | None:
    return _price_stream


def init_price_stream(
    symbols: list[str],
    testnet: bool = False,
    on_price: Optional[Callable[[str, Decimal, float], None]] = None,
) -> PriceStream:
    global _price_stream
    if _price_stream and _price_stream.is_connected:
        for s in symbols:
            _price_stream.add_symbol(s)
        return _price_stream
    _price_stream = PriceStream(symbols, on_price=on_price, testnet=testnet)
    _price_stream.start()
    return _price_stream


def stop_price_stream() -> None:
    global _price_stream
    if _price_stream:
        _price_stream.stop()
        _price_stream = None

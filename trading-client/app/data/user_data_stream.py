"""Binance User-Data WebSocket Stream — real-time order, balance, and position updates.

Connects to Binance's user-data stream via listenKey, which provides:
- executionReport: order status updates (pending, partially filled, filled, cancelled)
- outboundAccountPosition: balance updates after trades
- marginCall: margin call warnings (futures)
- ACCOUNT_UPDATE: futures account/balance/position updates

This replaces REST polling (5s for positions, 10s for orders) with event-driven updates.
Auto-reconnects with exponential backoff. Keeps listenKey alive with periodic pings.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable as _Callable
from datetime import UTC, datetime
from typing import Any, Callable, Optional

import httpx
import websockets

logger = logging.getLogger(__name__)

# Binance endpoints
_BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"
_BINANCE_WS_TESTNET = "wss://stream.testnet.binance.vision/ws"
_BINANCE_REST_BASE = "https://api.binance.com"
_BINANCE_REST_TESTNET = "https://testnet.binance.vision"

# ListenKey refresh interval (30 min as per Binance docs)
_LISTENKEY_REFRESH_INTERVAL = 30 * 60  # 30 minutes


class BinanceUserDataStream:
    """Manages a Binance user-data WebSocket stream for a single user.

    Runs in a background thread with its own asyncio event loop.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        on_order_update: Optional[Callable[[dict], None]] = None,
        on_balance_update: Optional[Callable[[dict], None]] = None,
        on_position_update: Optional[Callable[[dict], None]] = None,
        reconnect_interval: float = 1.0,
        max_reconnect_interval: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._testnet = testnet
        self._on_order_update = on_order_update
        self._on_balance_update = on_balance_update
        self._on_position_update = on_position_update
        self._reconnect_interval = reconnect_interval
        self._max_reconnect_interval = max_reconnect_interval

        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event = threading.Event()
        self._connected = False
        self._reconnect_count = 0
        self._listen_key: str | None = None
        self._ws: Any = None
        self._last_message_time: float = 0.0

        # REST endpoints
        self._rest_base = _BINANCE_REST_TESTNET if testnet else _BINANCE_REST_BASE
        self._ws_base = _BINANCE_WS_TESTNET if testnet else _BINANCE_WS_BASE

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    @property
    def listen_key(self) -> str | None:
        return self._listen_key

    def get_last_update_age(self) -> float:
        """Seconds since last message. -1 if never."""
        if self._last_message_time == 0.0:
            return -1.0
        return time.time() - self._last_message_time

    def start(self) -> None:
        """Start the stream in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("BinanceUserDataStream started (testnet=%s)", self._testnet)

    def stop(self) -> None:
        """Stop the stream."""
        self._stop_event.set()
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._close_ws(), self._loop)
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("BinanceUserDataStream stopped")

    def _run_loop(self) -> None:
        """Main loop running in background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main_loop())

    async def _main_loop(self) -> None:
        """Main coroutine: get listenKey, connect, and maintain the stream."""
        while not self._stop_event.is_set():
            try:
                # 1. Get or refresh listenKey
                self._listen_key = await self._get_listen_key()
                if not self._listen_key:
                    logger.warning("Failed to get listenKey, retrying in %ss", self._reconnect_interval)
                    await asyncio.sleep(self._reconnect_interval)
                    continue

                # 2. Start listenKey refresh task
                refresh_task = asyncio.create_task(self._refresh_listen_key_loop())

                # 3. Connect to WebSocket
                ws_url = f"{self._ws_base}/{self._listen_key}"
                try:
                    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                        self._ws = ws
                        self._connected = True
                        self._reconnect_count = 0
                        logger.info("BinanceUserDataStream connected to %s", ws_url)

                        # 4. Listen for messages
                        while not self._stop_event.is_set():
                            try:
                                message = await asyncio.wait_for(ws.recv(), timeout=60.0)
                                self._last_message_time = time.time()
                                self._handle_message(message)
                            except asyncio.TimeoutError:
                                # No message in 60s — send ping to keep alive
                                try:
                                    await ws.ping()
                                except Exception:
                                    break
                except Exception as exc:
                    logger.warning("BinanceUserDataStream disconnected: %s", exc)
                finally:
                    self._connected = False
                    self._ws = None
                    refresh_task.cancel()
                    try:
                        await refresh_task
                    except asyncio.CancelledError:
                        pass

                # 5. Reconnect with backoff
                if not self._stop_event.is_set():
                    self._reconnect_count += 1
                    delay = min(self._reconnect_interval * (2 ** min(self._reconnect_count, 5)), self._max_reconnect_interval)
                    logger.info("Reconnecting in %.1fs (attempt %d)", delay, self._reconnect_count)
                    await asyncio.sleep(delay)

            except Exception as exc:
                logger.error("BinanceUserDataStream main loop error: %s", exc)
                if not self._stop_event.is_set():
                    await asyncio.sleep(self._reconnect_interval)

    async def _get_listen_key(self) -> str | None:
        """Fetch a listenKey from Binance REST API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._rest_base}/api/v3/userDataStream",
                    headers={"X-MBX-APIKEY": self._api_key},
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("listenKey")
                else:
                    logger.warning("Failed to get listenKey: %s %s", response.status_code, response.text)
                    return None
        except Exception as exc:
            logger.warning("Error getting listenKey: %s", exc)
            return None

    async def _refresh_listen_key_loop(self) -> None:
        """Periodically refresh the listenKey to keep it alive."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(_LISTENKEY_REFRESH_INTERVAL)
                if self._listen_key:
                    async with httpx.AsyncClient() as client:
                        response = await client.put(
                            f"{self._rest_base}/api/v3/userDataStream",
                            params={"listenKey": self._listen_key},
                            headers={"X-MBX-APIKEY": self._api_key},
                        )
                        if response.status_code == 200:
                            logger.debug("listenKey refreshed")
                        else:
                            logger.warning("Failed to refresh listenKey: %s", response.status_code)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Error refreshing listenKey: %s", exc)

    def _handle_message(self, raw_message: str | bytes) -> None:
        """Parse and dispatch a user-data stream message."""
        try:
            data = json.loads(raw_message) if isinstance(raw_message, (str, bytes)) else raw_message
            event_type = data.get("e")

            if event_type == "executionReport":
                # Order update
                if self._on_order_update:
                    self._on_order_update(self._parse_order_event(data))
            elif event_type == "outboundAccountPosition":
                # Balance update after trade
                if self._on_balance_update:
                    self._on_balance_update(self._parse_balance_event(data))
            elif event_type == "ACCOUNT_UPDATE":
                # Futures account/position update
                if self._on_position_update:
                    self._on_position_update(self._parse_account_update(data))
            elif event_type == "marginCall":
                logger.warning("Margin call event received: %s", data)
            else:
                logger.debug("Unknown user-data event: %s", event_type)

        except Exception as exc:
            logger.error("Error handling user-data message: %s", exc)

    def _parse_order_event(self, data: dict) -> dict:
        """Parse an executionReport event into a normalized order update."""
        return {
            "event_type": "order_update",
            "order_id": data.get("i"),
            "client_order_id": data.get("c"),
            "symbol": data.get("s"),
            "side": data.get("S"),
            "order_type": data.get("o"),
            "order_status": data.get("X"),
            "quantity": float(data.get("q", 0)),
            "filled_quantity": float(data.get("z", 0)),
            "price": float(data.get("p", 0)) if data.get("p") else None,
            "avg_fill_price": float(data.get("Z", 0)) if data.get("Z") else None,
            "commission": float(data.get("n", 0)) if data.get("n") else 0,
            "commission_asset": data.get("N"),
            "timestamp": data.get("T"),
            "trade_id": data.get("t"),
            "is_maker": data.get("m", False),
        }

    def _parse_balance_event(self, data: dict) -> dict:
        """Parse an outboundAccountPosition event."""
        balances = []
        for b in data.get("B", []):
            balances.append({
                "asset": b.get("a"),
                "free": float(b.get("f", 0)),
                "locked": float(b.get("l", 0)),
            })
        return {
            "event_type": "balance_update",
            "balances": balances,
            "last_account_update": data.get("u"),
        }

    def _parse_account_update(self, data: dict) -> dict:
        """Parse a futures ACCOUNT_UPDATE event."""
        account_data = data.get("a", {})
        positions = []
        for p in account_data.get("P", []):
            positions.append({
                "symbol": p.get("s"),
                "position_amount": float(p.get("pa", 0)),
                "entry_price": float(p.get("ep", 0)),
                "unrealized_pnl": float(p.get("up", 0)),
                "margin_type": p.get("mt"),
                "leverage": int(p.get("l", 1)),
            })
        balances = []
        for b in account_data.get("B", []):
            balances.append({
                "asset": b.get("a"),
                "balance": float(b.get("wb", 0)),
                "cross_wallet": float(b.get("cw", 0)),
            })
        return {
            "event_type": "account_update",
            "positions": positions,
            "balances": balances,
            "timestamp": data.get("E"),
        }

    async def _close_ws(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Stream manager — manages streams per user
# ---------------------------------------------------------------------------

_streams: dict[int, BinanceUserDataStream] = {}
_streams_lock = threading.Lock()


def get_user_data_stream(user_id: int) -> BinanceUserDataStream | None:
    """Get the active user-data stream for a user, if any."""
    with _streams_lock:
        return _streams.get(user_id)


def start_user_data_stream(
    user_id: int,
    api_key: str,
    api_secret: str,
    testnet: bool = False,
    on_order_update: Callable[[dict], None] | None = None,
    on_balance_update: Callable[[dict], None] | None = None,
    on_position_update: Callable[[dict], None] | None = None,
) -> BinanceUserDataStream:
    """Start a user-data stream for a user. Returns the stream instance.

    If a stream is already running for this user, it is restarted with new credentials.
    """
    with _streams_lock:
        # Stop existing stream if any
        existing = _streams.get(user_id)
        if existing:
            existing.stop()

        stream = BinanceUserDataStream(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            on_order_update=on_order_update,
            on_balance_update=on_balance_update,
            on_position_update=on_position_update,
        )
        stream.start()
        _streams[user_id] = stream
        return stream


def stop_user_data_stream(user_id: int) -> None:
    """Stop the user-data stream for a user."""
    with _streams_lock:
        stream = _streams.pop(user_id, None)
    if stream:
        stream.stop()


def stop_all_streams() -> None:
    """Stop all user-data streams. Called on app shutdown."""
    with _streams_lock:
        streams = list(_streams.values())
        _streams.clear()
    for stream in streams:
        stream.stop()

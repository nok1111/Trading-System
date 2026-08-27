"""MCP (Model Context Protocol) server for Alvora Trading Platform.

Exposes trading tools via JSON-RPC so external AI clients (Claude, ChatGPT,
Cursor) can interact with the user's portfolio, place orders, manage bots,
and query market intelligence.

Privacy: API keys are never exposed — only results are returned.
Auth: JWT token validated against the Auth Server on every request.
"""

from __future__ import annotations

import json
import logging
import secrets
import time
from typing import Any

from app.services.license import validate_license

logger = logging.getLogger(__name__)

# Active MCP sessions: token -> { user_id, email, created_at, expires_at }
_sessions: dict[str, dict[str, Any]] = {}
_SESSION_TTL = 3600  # 1 hour


class AlvoraMCPServer:
    """MCP server exposing Alvora trading tools via JSON-RPC.

    This is a lightweight implementation — no external ``mcp`` package needed.
    The server dispatches JSON-RPC method calls to handler functions and
    returns results. It can be exposed via SSE or a simple POST endpoint.
    """

    # Tool definitions exposed to MCP clients
    TOOLS: list[dict[str, Any]] = [
        {
            "name": "get_portfolio",
            "description": "Get unified portfolio overview across all connected brokers (balances, positions, exposure).",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "get_positions",
            "description": "Get all open positions across connected brokers.",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "get_balance",
            "description": "Get balances per broker with USD values.",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "place_order",
            "description": "Place an order on a connected broker. Requires confirmation.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol, e.g. BTCUSDT"},
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "quantity": {"type": "number", "description": "Order quantity"},
                    "order_type": {"type": "string", "enum": ["market", "limit"], "default": "market"},
                    "price": {"type": "number", "description": "Limit price (required for limit orders)"},
                    "broker_id": {"type": "string", "description": "Broker to use (default: first connected)"},
                    "confirm": {"type": "boolean", "description": "Must be true to execute. If false, returns a preview."},
                },
                "required": ["symbol", "side", "quantity", "confirm"],
            },
        },
        {
            "name": "close_position",
            "description": "Close an open position by symbol.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "broker_id": {"type": "string"},
                    "confirm": {"type": "boolean", "description": "Must be true to execute."},
                },
                "required": ["symbol", "confirm"],
            },
        },
        {
            "name": "get_market_data",
            "description": "Get market data: current price and/or klines for a symbol.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "e.g. BTCUSDT"},
                    "interval": {"type": "string", "description": "Kline interval (1m,5m,15m,1h,4h,1d)", "default": "1h"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["symbol"],
            },
        },
        {
            "name": "get_intelligence",
            "description": "Get AI market intelligence signals (technical analysis, fear/greed, regime).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Optional symbol for specific signals"},
                },
                "required": [],
            },
        },
        {
            "name": "get_alerts",
            "description": "Get active smart alerts for the portfolio.",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "create_alert",
            "description": "Create a price alert.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "condition": {"type": "string", "enum": ["above", "below"]},
                    "price": {"type": "number"},
                },
                "required": ["symbol", "condition", "price"],
            },
        },
        {
            "name": "get_bots",
            "description": "Get status of all trading bots (grid, DCA).",
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "start_bot",
            "description": "Start a trading bot by ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "bot_id": {"type": "integer"},
                    "bot_type": {"type": "string", "enum": ["grid", "dca"]},
                },
                "required": ["bot_id", "bot_type"],
            },
        },
        {
            "name": "stop_bot",
            "description": "Stop a trading bot by ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "bot_id": {"type": "integer"},
                    "bot_type": {"type": "string", "enum": ["grid", "dca"]},
                },
                "required": ["bot_id", "bot_type"],
            },
        },
        {
            "name": "ask_alvora",
            "description": "Send a message to the Alvora AI copilot and get a response.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Question or instruction for the AI copilot"},
                },
                "required": ["message"],
            },
        },
    ]

    # Map tool name -> handler method name
    _DISPATCH: dict[str, str] = {
        "get_portfolio": "_handle_get_portfolio",
        "get_positions": "_handle_get_positions",
        "get_balance": "_handle_get_balance",
        "place_order": "_handle_place_order",
        "close_position": "_handle_close_position",
        "get_market_data": "_handle_get_market_data",
        "get_intelligence": "_handle_get_intelligence",
        "get_alerts": "_handle_get_alerts",
        "create_alert": "_handle_create_alert",
        "get_bots": "_handle_get_bots",
        "start_bot": "_handle_start_bot",
        "stop_bot": "_handle_stop_bot",
        "ask_alvora": "_handle_ask_alvora",
    }

    # ── Session management ──────────────────────────────────────────

    @staticmethod
    def create_session(user_id: int, email: str) -> str:
        """Create a new MCP session and return the token."""
        token = secrets.token_urlsafe(32)
        _sessions[token] = {
            "user_id": user_id,
            "email": email,
            "created_at": time.time(),
            "expires_at": time.time() + _SESSION_TTL,
        }
        return token

    @staticmethod
    def close_session(token: str) -> bool:
        """Close an MCP session. Returns True if it existed."""
        return _sessions.pop(token, None) is not None

    @staticmethod
    def get_session(token: str) -> dict[str, Any] | None:
        """Get session info if valid, else None."""
        session = _sessions.get(token)
        if not session:
            return None
        if session["expires_at"] < time.time():
            _sessions.pop(token, None)
            return None
        return session

    @staticmethod
    def validate_token(token: str) -> dict[str, Any] | None:
        """Validate a JWT token against the Auth Server.

        Returns the license info dict if valid, None otherwise.
        """
        if not token:
            return None
        return validate_license(token)

    # ── JSON-RPC dispatch ───────────────────────────────────────────

    def handle_request(
        self, method: str, params: dict[str, Any] | None, token: str
    ) -> dict[str, Any]:
        """Dispatch a JSON-RPC request to the appropriate handler.

        Args:
            method: The tool/method name (e.g. "get_portfolio").
            params: Parameters dict for the tool.
            token: JWT token for authentication.

        Returns:
            JSON-RPC response dict with either "result" or "error".
        """
        # Special meta-methods
        if method == "tools/list":
            return {"result": {"tools": self.TOOLS}}
        if method == "tools/call":
            # MCP-style: params has "name" and "arguments"
            tool_name = (params or {}).get("name", "")
            tool_args = (params or {}).get("arguments", {})
            return self._dispatch_tool(tool_name, tool_args, token)

        # Direct method dispatch
        return self._dispatch_tool(method, params or {}, token)

    def _dispatch_tool(
        self, tool_name: str, args: dict[str, Any], token: str
    ) -> dict[str, Any]:
        """Dispatch to the handler for a specific tool."""
        # Validate token
        license_info = self.validate_token(token)
        if not license_info or not license_info.get("valid"):
            return {
                "error": {
                    "code": -32001,
                    "message": "Authentication failed — invalid or expired token",
                }
            }

        user_id = license_info.get("user_id", 0)

        handler_name = self._DISPATCH.get(tool_name)
        if not handler_name:
            return {
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {tool_name}",
                }
            }

        handler = getattr(self, handler_name, None)
        if not handler:
            return {
                "error": {
                    "code": -32601,
                    "message": f"Handler not implemented: {tool_name}",
                }
            }

        try:
            result = handler(user_id, args)
            return {"result": result}
        except Exception as exc:
            logger.exception("MCP tool '%s' failed", tool_name)
            return {
                "error": {
                    "code": -32000,
                    "message": str(exc),
                }
            }

    # ── Tool handlers ───────────────────────────────────────────────

    def _handle_get_portfolio(self, user_id: int, _args: dict) -> dict:
        """Get unified portfolio overview."""
        from app.services.portfolio_aggregator import get_unified_portfolio_overview

        return get_unified_portfolio_overview(user_id)

    def _handle_get_positions(self, user_id: int, _args: dict) -> dict:
        """Get open positions across all brokers."""
        from app.services.portfolio_aggregator import get_unified_positions

        return get_unified_positions(user_id)

    def _handle_get_balance(self, user_id: int, _args: dict) -> dict:
        """Get balances per broker."""
        from app.services.portfolio_aggregator import get_unified_balances

        return get_unified_balances(user_id)

    def _handle_place_order(self, user_id: int, args: dict) -> dict:
        """Place an order. Requires confirm=True to execute."""
        symbol = args.get("symbol", "")
        side = args.get("side", "buy")
        quantity = float(args.get("quantity", 0))
        order_type = args.get("order_type", "market")
        price = args.get("price")
        broker_id = args.get("broker_id")
        confirm = args.get("confirm", False)

        if not symbol or quantity <= 0:
            return {"error": "symbol and quantity are required"}

        if not confirm:
            return {
                "preview": True,
                "message": f"Preview: {side.upper()} {quantity} {symbol} @ {'market' if order_type == 'market' else price} on {broker_id or 'default broker'}",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
                "price": price,
                "broker_id": broker_id,
                "confirm_required": True,
            }

        # Execute the order
        from app.api.helpers import resolve_broker_credentials, resolve_user_broker_id
        from app.brokers.registry import get_adapter
        from app.services.auth import LocalUser

        user = LocalUser(id=user_id, email="", username="", subscription="free")
        bid = broker_id or resolve_user_broker_id(user)
        if not bid:
            return {"error": "No connected broker found"}

        creds = resolve_broker_credentials(bid, user)
        if not creds:
            return {"error": f"Could not resolve credentials for {bid}"}

        adapter = get_adapter(bid, creds)
        try:
            if order_type == "limit" and price:
                order = adapter.place_limit_order(symbol, side, quantity, float(price))
            else:
                order = adapter.place_market_order(symbol, side, quantity)
            return {"success": True, "order": _safe_order_dict(order)}
        except Exception as exc:
            return {"error": str(exc)}

    def _handle_close_position(self, user_id: int, args: dict) -> dict:
        """Close an open position."""
        symbol = args.get("symbol", "")
        broker_id = args.get("broker_id")
        confirm = args.get("confirm", False)

        if not symbol:
            return {"error": "symbol is required"}

        if not confirm:
            return {
                "preview": True,
                "message": f"Preview: close position {symbol} on {broker_id or 'default broker'}",
                "symbol": symbol,
                "broker_id": broker_id,
                "confirm_required": True,
            }

        from app.api.helpers import resolve_broker_credentials, resolve_user_broker_id
        from app.brokers.registry import get_adapter
        from app.services.auth import LocalUser

        user = LocalUser(id=user_id, email="", username="", subscription="free")
        bid = broker_id or resolve_user_broker_id(user)
        if not bid:
            return {"error": "No connected broker found"}

        creds = resolve_broker_credentials(bid, user)
        if not creds:
            return {"error": f"Could not resolve credentials for {bid}"}

        adapter = get_adapter(bid, creds)
        try:
            result = adapter.close_position(symbol)
            return {"success": True, "result": str(result)}
        except Exception as exc:
            return {"error": str(exc)}

    def _handle_get_market_data(self, _user_id: int, args: dict) -> dict:
        """Get market data (price + klines)."""
        symbol = args.get("symbol", "")
        interval = args.get("interval", "1h")
        limit = int(args.get("limit", 50))

        if not symbol:
            return {"error": "symbol is required"}

        from app.services.market_data_service import get_market_data_service

        svc = get_market_data_service()
        result: dict[str, Any] = {"symbol": symbol}

        try:
            ticker = svc.get_ticker(symbol)
            if ticker:
                result["price"] = float(ticker.last_price)
                result["volume_24h"] = float(ticker.volume) if ticker.volume else None
                result["change_24h_pct"] = float(ticker.change_pct) if ticker.change_pct else None
        except Exception as exc:
            logger.warning("MCP get_market_data ticker failed: %s", exc)

        try:
            klines = svc.get_klines(symbol, interval, limit)
            if klines:
                result["klines"] = [
                    {
                        "timestamp": k.timestamp.isoformat() if hasattr(k.timestamp, "isoformat") else str(k.timestamp),
                        "open": float(k.open),
                        "high": float(k.high),
                        "low": float(k.low),
                        "close": float(k.close),
                        "volume": float(k.volume),
                    }
                    for k in klines
                ]
        except Exception as exc:
            logger.warning("MCP get_market_data klines failed: %s", exc)

        return result

    def _handle_get_intelligence(self, _user_id: int, args: dict) -> dict:
        """Get AI intelligence signals."""
        from app.services.market_data_service import get_market_data_service

        svc = get_market_data_service()
        result: dict[str, Any] = {}

        try:
            result["fear_greed"] = svc.get_fear_greed(limit=1)
        except Exception:
            pass

        try:
            result["global_stats"] = svc.get_global_crypto_stats()
        except Exception:
            pass

        symbol = args.get("symbol")
        if symbol:
            try:
                from app.services.technical_analysis import generate_technical_signals

                result["technical"] = generate_technical_signals(symbol)
            except Exception as exc:
                logger.warning("MCP intelligence technical failed: %s", exc)

        return result

    def _handle_get_alerts(self, user_id: int, _args: dict) -> dict:
        """Get active smart alerts."""
        from app.services.smart_alerts import generate_smart_alerts

        return generate_smart_alerts(user_id)

    def _handle_create_alert(self, _user_id: int, args: dict) -> dict:
        """Create a price alert (basic implementation)."""
        symbol = args.get("symbol", "")
        condition = args.get("condition", "above")
        price = float(args.get("price", 0))

        if not symbol or price <= 0:
            return {"error": "symbol, condition, and price are required"}

        # Store alert in DB (basic — uses existing alert infrastructure if available)
        try:
            from app.database.session import SessionLocal
            from app.database.models.signal import Signal
            from datetime import UTC, datetime

            session = SessionLocal()
            try:
                alert = Signal(
                    symbol=symbol,
                    strategy="price_alert",
                    signal_type=condition,
                    price=price,
                    timestamp=datetime.now(UTC),
                )
                session.add(alert)
                session.commit()
                return {"success": True, "alert_id": alert.id, "symbol": symbol, "condition": condition, "price": price}
            finally:
                session.close()
        except Exception as exc:
            logger.warning("MCP create_alert failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def _handle_get_bots(self, user_id: int, _args: dict) -> dict:
        """Get all trading bots for the user."""
        from app.database.session import SessionLocal
        from app.database.models.grid_bot import DCABot, GridBot

        session = SessionLocal()
        try:
            grid_bots = session.query(GridBot).filter_by(user_id=user_id).all()
            dca_bots = session.query(DCABot).filter_by(user_id=user_id).all()
            return {
                "grid": [
                    {
                        "id": b.id,
                        "name": b.name,
                        "symbol": b.symbol,
                        "broker_id": b.broker_id,
                        "is_active": b.is_active,
                        "status": b.status,
                        "investment_usd": str(b.investment_usd),
                        "orders_placed": b.orders_placed,
                        "orders_filled": b.orders_filled,
                        "realized_pnl": str(b.realized_pnl),
                    }
                    for b in grid_bots
                ],
                "dca": [
                    {
                        "id": b.id,
                        "name": b.name,
                        "symbol": b.symbol,
                        "broker_id": b.broker_id,
                        "is_active": b.is_active,
                        "status": b.status,
                        "buy_amount_usd": str(b.buy_amount_usd),
                        "buys_executed": b.buys_executed,
                        "total_invested": str(b.total_invested),
                    }
                    for b in dca_bots
                ],
            }
        finally:
            session.close()

    def _handle_start_bot(self, user_id: int, args: dict) -> dict:
        """Start a trading bot."""
        bot_id = int(args.get("bot_id", 0))
        bot_type = args.get("bot_type", "grid")

        if bot_id <= 0:
            return {"error": "bot_id is required"}

        from app.database.session import SessionLocal
        from app.database.models.grid_bot import DCABot, GridBot
        from datetime import UTC, datetime

        session = SessionLocal()
        try:
            model = GridBot if bot_type == "grid" else DCABot
            bot = session.query(model).filter_by(id=bot_id, user_id=user_id).first()
            if not bot:
                return {"error": f"{bot_type} bot {bot_id} not found"}
            bot.is_active = True
            bot.status = "running"
            bot.updated_at = datetime.now(UTC)
            session.commit()
            return {"success": True, "bot_id": bot_id, "bot_type": bot_type, "status": "running"}
        finally:
            session.close()

    def _handle_stop_bot(self, user_id: int, args: dict) -> dict:
        """Stop a trading bot."""
        bot_id = int(args.get("bot_id", 0))
        bot_type = args.get("bot_type", "grid")

        if bot_id <= 0:
            return {"error": "bot_id is required"}

        from app.database.session import SessionLocal
        from app.database.models.grid_bot import DCABot, GridBot
        from datetime import UTC, datetime

        session = SessionLocal()
        try:
            model = GridBot if bot_type == "grid" else DCABot
            bot = session.query(model).filter_by(id=bot_id, user_id=user_id).first()
            if not bot:
                return {"error": f"{bot_type} bot {bot_id} not found"}
            bot.is_active = False
            bot.status = "stopped"
            bot.updated_at = datetime.now(UTC)
            session.commit()
            return {"success": True, "bot_id": bot_id, "bot_type": bot_type, "status": "stopped"}
        finally:
            session.close()

    def _handle_ask_alvora(self, user_id: int, args: dict) -> dict:
        """Send a message to the Alvora AI copilot."""
        message = args.get("message", "")
        if not message:
            return {"error": "message is required"}

        from app.ai.copilot import copilot_chat

        result = copilot_chat(user_id, message, None)
        return result

    # ── Config generation ───────────────────────────────────────────

    @staticmethod
    def generate_mcp_config(token: str, base_url: str = "http://localhost:8000") -> dict[str, Any]:
        """Generate MCP config JSON for Claude / ChatGPT / Cursor.

        Returns a config dict that can be copy-pasted into the AI client's
        MCP configuration. The token is embedded for authentication.
        """
        config = {
            "mcpServers": {
                "alvora": {
                    "url": f"{base_url}/api/mcp/rpc",
                    "transport": "http",
                    "headers": {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    "tools": [t["name"] for t in AlvoraMCPServer.TOOLS],
                }
            },
            "instructions": (
                "Alvora Trading Platform MCP connector. "
                "Use the provided tools to query portfolio, place orders, "
                "manage bots, and get market intelligence. "
                "Always set confirm=true when placing orders or closing positions. "
                "API keys are never exposed — only results are returned."
            ),
        }
        return config


def _safe_order_dict(order: Any) -> dict:
    """Convert an order object to a safe dict (no sensitive data)."""
    if isinstance(order, dict):
        return order
    result: dict[str, Any] = {}
    for attr in ("id", "symbol", "side", "type", "status", "quantity", "price", "filled_qty", "avg_fill_price"):
        val = getattr(order, attr, None)
        if val is not None:
            result[attr] = str(val) if hasattr(val, "__str__") else val
    return result

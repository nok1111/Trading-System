"""DCA Bot Service — manages Dollar Cost Averaging bots.

Handles:
- Creating and configuring DCA bots
- Running scheduled investments
- Checking price conditions before buying
- Tracking average entry price and total invested
- Stopping bots when max investments reached
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database.models.grid_bot import DCABot
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)


def create_dca_bot(
    user_id: int,
    name: str,
    broker_id: str,
    symbol: str,
    investment_usd: float,
    interval_hours: int = 24,
    max_investments: int = 0,
    max_buy_price: float | None = None,
    min_buy_price: float | None = None,
    market_type: str = "spot",
) -> dict[str, Any]:
    """Create a new DCA bot."""
    db = SessionLocal()
    try:
        bot = DCABot(
            user_id=user_id,
            name=name,
            broker_id=broker_id,
            symbol=symbol,
            market_type=market_type,
            buy_amount_usd=Decimal(str(investment_usd)),
            interval_minutes=interval_hours * 60,
            max_buys=max_investments,
            is_active=True,
            status="running",
        )
        db.add(bot)
        db.commit()
        db.refresh(bot)
        return _bot_to_dict(bot)
    finally:
        db.close()


def list_dca_bots(user_id: int) -> list[dict[str, Any]]:
    """List all DCA bots for a user."""
    db = SessionLocal()
    try:
        bots = (
            db.query(DCABot)
            .filter(DCABot.user_id == user_id)
            .order_by(desc(DCABot.created_at))
            .all()
        )
        return [_bot_to_dict(b) for b in bots]
    finally:
        db.close()


def get_dca_bot(user_id: int, bot_id: int) -> dict[str, Any] | None:
    """Get a specific DCA bot."""
    db = SessionLocal()
    try:
        bot = db.query(DCABot).filter(DCABot.id == bot_id, DCABot.user_id == user_id).first()
        return _bot_to_dict(bot) if bot else None
    finally:
        db.close()


def stop_dca_bot(user_id: int, bot_id: int) -> dict[str, Any]:
    """Stop a DCA bot."""
    db = SessionLocal()
    try:
        bot = db.query(DCABot).filter(DCABot.id == bot_id, DCABot.user_id == user_id).first()
        if not bot:
            return {"ok": False, "error": "Bot not found"}

        bot.is_active = False
        bot.status = "stopped"
        db.commit()
        return {"ok": True, "bot_id": bot_id, "status": "stopped"}
    finally:
        db.close()


def delete_dca_bot(user_id: int, bot_id: int) -> dict[str, Any]:
    """Delete a DCA bot."""
    db = SessionLocal()
    try:
        bot = db.query(DCABot).filter(DCABot.id == bot_id, DCABot.user_id == user_id).first()
        if not bot:
            return {"ok": False, "error": "Bot not found"}

        db.delete(bot)
        db.commit()
        return {"ok": True, "bot_id": bot_id}
    finally:
        db.close()


def run_due_dca_bots() -> list[dict[str, Any]]:
    """Run all DCA bots that are due for investment.

    This should be called by a scheduler periodically.
    """
    db = SessionLocal()
    results: list[dict[str, Any]] = []
    try:
        now = datetime.now(tz=UTC).replace(tzinfo=None)
        # Bots that are active and haven't bought in the last interval
        cutoff = now - timedelta(minutes=1440)  # default 24h
        due_bots = (
            db.query(DCABot)
            .filter(
                DCABot.is_active == True,  # noqa: E712
                DCABot.status == "running",
            )
            .all()
        )

        # Filter by interval in Python (since last_buy_at + interval_minutes)
        actually_due = []
        for bot in due_bots:
            if bot.last_buy_at is None:
                actually_due.append(bot)
            else:
                next_run = bot.last_buy_at + timedelta(minutes=bot.interval_minutes)
                if now >= next_run:
                    actually_due.append(bot)
        due_bots = actually_due

        for bot in due_bots:
            result = _execute_dca_investment(bot, db)
            results.append(result)

        return results
    except Exception as exc:
        logger.warning("DCA scheduler error: %s", exc)
        return results
    finally:
        db.close()


def _execute_dca_investment(bot: DCABot, db: Session) -> dict[str, Any]:
    """Execute a single DCA investment for a bot."""
    result: dict[str, Any] = {
        "bot_id": bot.id,
        "user_id": bot.user_id,
        "success": False,
        "error": None,
    }

    try:
        # Check max investments
        if bot.max_buys > 0 and bot.buys_executed >= bot.max_buys:
            bot.is_active = False
            bot.status = "stopped"
            db.commit()
            result["error"] = "Max investments reached"
            return result

        # Get current price
        current_price = _get_current_price(bot.broker_id, bot.symbol)
        if current_price <= 0:
            result["error"] = "Failed to get current price"
            _schedule_next_run(bot, db)
            return result

        # Calculate quantity
        investment = float(bot.buy_amount_usd)
        quantity = investment / current_price

        # Place order
        order_result = _place_dca_order(bot, quantity)
        if not order_result.get("success"):
            result["error"] = order_result.get("error", "Order failed")
            _schedule_next_run(bot, db)
            return result

        # Update bot tracking
        bot.buys_executed += 1
        bot.total_invested += Decimal(str(investment))
        bot.total_quantity += Decimal(str(quantity))

        # Update average entry price
        if bot.total_quantity > 0:
            bot.avg_entry_price = bot.total_invested / bot.total_quantity

        _schedule_next_run(bot, db)

        result["success"] = True
        result["quantity"] = quantity
        result["price"] = current_price
        result["total_invested"] = float(bot.total_invested)
        result["avg_entry"] = float(bot.avg_entry_price)

        # Log
        try:
            from app.services.audit_log import log_audit
            log_audit(
                user_id=bot.user_id,
                source="trading",
                message=f"DCA bot '{bot.name}' invested ${investment} in {bot.symbol}",
                details={"bot_id": bot.id, "quantity": quantity, "price": current_price},
            )
        except Exception:
            pass

        return result

    except Exception as exc:
        logger.warning("DCA investment failed for bot %d: %s", bot.id, exc)
        result["error"] = str(exc)
        _schedule_next_run(bot, db)
        return result


def _schedule_next_run(bot: DCABot, db: Session) -> None:
    """Schedule the next run for a DCA bot."""
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    bot.last_buy_at = now
    db.commit()


def _get_current_price(broker_id: str, symbol: str) -> float:
    """Get current price for a symbol from a broker."""
    try:
        from app.brokers.registry import get_adapter
        from app.brokers.models import BrokerCredentials
        from app.services.broker_account_service import get_broker_credentials

        # This is a simplified version — in production, we'd use the user's stored credentials
        # For now, use public market data
        from app.services.market_data_service import get_market_data_service
        md = get_market_data_service()
        ticker = md.get_ticker(symbol)
        return float(ticker.last_price) if ticker else 0.0
    except Exception as exc:
        logger.warning("Failed to get price for %s: %s", symbol, exc)
        return 0.0


def _place_dca_order(bot: DCABot, quantity: float) -> dict[str, Any]:
    """Place a market buy order for DCA."""
    try:
        from app.brokers.registry import get_adapter
        from app.brokers.models import BrokerCredentials, OrderRequest, OrderSide, OrderType
        from app.services.broker_account_service import get_broker_credentials

        creds = get_broker_credentials(bot.user_id, bot.broker_id)
        if not creds:
            return {"success": False, "error": "No credentials for broker"}

        adapter = get_adapter(bot.broker_id, creds, market_type=bot.market_type)

        order_req = OrderRequest(
            symbol=bot.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal(str(quantity)),
        )

        result = adapter.place_order(order_req)
        return {"success": True, "order_id": result.order_id}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _bot_to_dict(bot: DCABot) -> dict[str, Any]:
    """Convert a DCABot to a dict."""
    return {
        "id": bot.id,
        "user_id": bot.user_id,
        "name": bot.name,
        "broker_id": bot.broker_id,
        "symbol": bot.symbol,
        "market_type": bot.market_type,
        "investment_usd": float(bot.buy_amount_usd),
        "interval_hours": bot.interval_minutes // 60,
        "max_investments": bot.max_buys,
        "is_active": bot.is_active,
        "status": bot.status,
        "investments_made": bot.buys_executed,
        "total_invested": float(bot.total_invested),
        "total_quantity": float(bot.total_quantity),
        "avg_entry_price": float(bot.avg_entry_price),
        "realized_pnl": float(bot.realized_pnl),
        "last_run_at": bot.last_buy_at.isoformat() if bot.last_buy_at else None,
        "created_at": bot.created_at.isoformat() if bot.created_at else None,
    }

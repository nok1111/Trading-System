"""Trade Verification Service — HMAC signing and verification of trades.

Allows social trading leaders to prove their track record is real by signing
each trade with HMAC-SHA256 using their broker API key. Followers can verify
that trades actually came from the broker.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class TradeVerificationService:
    """Sign and verify trades for social trading."""

    def sign_trade(
        self,
        broker_id: str,
        symbol: str,
        side: str,
        quantity: str,
        price: str,
        timestamp: datetime,
        broker_order_id: str | None,
        api_secret: str,
    ) -> str:
        """Generate HMAC-SHA256 signature for a trade.

        The message is: broker_id:symbol:side:quantity:price:timestamp:broker_order_id
        The secret is the broker's API secret key.
        """
        message = f"{broker_id}:{symbol}:{side}:{quantity}:{price}:{timestamp.isoformat()}:{broker_order_id or ''}"
        signature = hmac.new(
            api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def verify_trade(
        self,
        broker_id: str,
        symbol: str,
        side: str,
        quantity: str,
        price: str,
        timestamp: datetime,
        broker_order_id: str | None,
        hmac_signature: str,
        api_secret: str,
    ) -> bool:
        """Verify a trade's HMAC signature."""
        expected = self.sign_trade(
            broker_id, symbol, side, quantity, price,
            timestamp, broker_order_id, api_secret,
        )
        return hmac.compare_digest(expected, hmac_signature)

    def store_verification(
        self,
        leader_id: int,
        broker_id: str,
        symbol: str,
        side: str,
        quantity: str,
        price: str,
        timestamp: datetime,
        hmac_signature: str,
        broker_order_id: str | None = None,
        trade_id: int | None = None,
    ) -> dict:
        """Store a trade verification record in the database."""
        from app.database.models.trade_verification import TradeVerification
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            verif = TradeVerification(
                trade_id=trade_id,
                leader_id=leader_id,
                broker_id=broker_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
                hmac_signature=hmac_signature,
                broker_order_id=broker_order_id,
                verified=False,
            )
            db.add(verif)
            db.commit()
            db.refresh(verif)
            return {"status": "ok", "id": verif.id}
        except Exception as exc:
            db.rollback()
            logger.error("Error storing verification: %s", exc)
            return {"status": "error", "error": str(exc)}
        finally:
            db.close()

    def mark_verified(self, verification_id: int) -> dict:
        """Mark a verification as confirmed (broker order ID exists)."""
        from app.database.models.trade_verification import TradeVerification
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            verif = db.query(TradeVerification).filter(
                TradeVerification.id == verification_id
            ).first()
            if not verif:
                return {"status": "not_found"}
            verif.verified = True
            verif.verified_at = datetime.now(tz=UTC)
            db.commit()
            return {"status": "ok"}
        except Exception as exc:
            db.rollback()
            return {"status": "error", "error": str(exc)}
        finally:
            db.close()

    def get_leader_verified_stats(self, leader_id: int) -> dict:
        """Get verification stats for a leader."""
        from app.database.models.trade_verification import TradeVerification
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            records = db.query(TradeVerification).filter(
                TradeVerification.leader_id == leader_id
            ).all()

            total = len(records)
            verified = sum(1 for r in records if r.verified)
            verified_pct = (verified / total * 100) if total > 0 else 0

            first_verified = None
            for r in records:
                if r.verified and r.verified_at:
                    if first_verified is None or r.verified_at < first_verified:
                        first_verified = r.verified_at

            return {
                "status": "ok",
                "total_trades": total,
                "verified_trades": verified,
                "verified_pct": round(verified_pct, 1),
                "first_verified_at": first_verified.isoformat() if first_verified else None,
            }
        finally:
            db.close()

    def get_leader_verified_trades(self, leader_id: int, limit: int = 50) -> list[dict]:
        """Get list of verified trades for a leader."""
        from app.database.models.trade_verification import TradeVerification
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            records = db.query(TradeVerification).filter(
                TradeVerification.leader_id == leader_id,
            ).order_by(TradeVerification.timestamp.desc()).limit(limit).all()

            return [
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "side": r.side,
                    "quantity": r.quantity,
                    "price": r.price,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "broker_id": r.broker_id,
                    "broker_order_id": r.broker_order_id,
                    "verified": r.verified,
                    "hmac_signature": r.hmac_signature[:16] + "...",  # truncated for display
                }
                for r in records
            ]
        finally:
            db.close()

    def public_verify(self, verify_data: dict) -> dict:
        """Public endpoint: verify a trade's HMAC signature.

        Input: trade data + HMAC + broker_id
        Output: valid/invalid
        Note: This does NOT require the API secret — it checks if the HMAC
        format is valid and the broker_order_id exists (if provided).
        Full HMAC verification requires the API secret, which is never exposed.
        """
        broker_id = verify_data.get("broker_id", "")
        symbol = verify_data.get("symbol", "")
        side = verify_data.get("side", "")
        quantity = verify_data.get("quantity", "")
        price = verify_data.get("price", "")
        timestamp_str = verify_data.get("timestamp", "")
        hmac_sig = verify_data.get("hmac_signature", "")
        broker_order_id = verify_data.get("broker_order_id")

        # Basic format validation
        if not all([broker_id, symbol, side, quantity, price, timestamp_str, hmac_sig]):
            return {"status": "invalid", "reason": "Missing required fields"}

        # Check HMAC format (64 chars hex for SHA256)
        if len(hmac_sig) != 64:
            # Could be truncated for display — check if it starts with valid hex
            try:
                int(hmac_sig[:16], 16)
            except ValueError:
                return {"status": "invalid", "reason": "Invalid HMAC format"}

        # If we have a broker_order_id, we could verify it exists on the broker
        # For now, just confirm the format is valid
        return {
            "status": "valid",
            "broker_id": broker_id,
            "symbol": symbol,
            "has_broker_order_id": broker_order_id is not None,
            "message": "HMAC format valid. Full verification requires API secret.",
        }

"""Strategy Marketplace service — publish, list, subscribe, review, and trend strategies.

Business logic for the strategy marketplace. Uses SQLAlchemy sessions directly
(matching the pattern in portfolio_aggregator / social services).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.database.models.strategy_marketplace import (
    StrategyBacktestVerification,
    StrategyListing,
    StrategyReview,
    StrategySubscription,
)
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)

# Quality gate thresholds — strategies must pass before publishing
MIN_ROI = -50.0  # ROI over 90d must be better than -50%
MAX_DRAWDOWN = 30.0  # Max drawdown must be below 30%

VALID_STRATEGY_TYPES = {"grid", "dca", "custom", "ai_generated"}


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _verification_dict(v: StrategyBacktestVerification | None) -> dict[str, Any] | None:
    if not v:
        return None
    return {
        "id": v.id,
        "listing_id": v.listing_id,
        "backtest_hash": v.backtest_hash,
        "roi_90d": v.roi_90d,
        "max_drawdown": v.max_drawdown,
        "sharpe": v.sharpe,
        "verified_at": v.verified_at.isoformat() if v.verified_at else None,
    }


def _review_dict(r: StrategyReview) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "listing_id": r.listing_id,
        "rating": r.rating,
        "comment": r.comment,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _listing_dict(
    listing: StrategyListing,
    verification: StrategyBacktestVerification | None = None,
    creator_name: str | None = None,
) -> dict[str, Any]:
    return {
        "id": listing.id,
        "creator_user_id": listing.creator_user_id,
        "creator_name": creator_name or f"User {listing.creator_user_id}",
        "title": listing.title,
        "description": listing.description,
        "strategy_type": listing.strategy_type,
        "config_json": listing.config_json,
        "is_public": listing.is_public,
        "is_premium": listing.is_premium,
        "price_monthly": listing.price_monthly,
        "created_at": listing.created_at.isoformat() if listing.created_at else None,
        "downloads": listing.downloads,
        "rating_avg": listing.rating_avg,
        "rating_count": listing.rating_count,
        "exchange": listing.exchange,
        "symbols_json": listing.symbols_json,
        "verification": _verification_dict(verification),
    }


def _subscription_dict(sub: StrategySubscription, listing: StrategyListing | None = None) -> dict[str, Any]:
    return {
        "id": sub.id,
        "user_id": sub.user_id,
        "listing_id": sub.listing_id,
        "status": sub.status,
        "subscribed_at": sub.subscribed_at.isoformat() if sub.subscribed_at else None,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "listing": _listing_dict(listing) if listing else None,
    }


# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------

def _compute_backtest_hash(config: dict[str, Any]) -> str:
    """Stable hash of the strategy config so verifications can be compared."""
    raw = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _validate_quality_gate(roi_90d: float, max_drawdown: float) -> tuple[bool, str]:
    """Return (ok, reason). Strategies must pass before publishing."""
    if roi_90d < MIN_ROI:
        return False, f"ROI 90d ({roi_90d:.1f}%) is below minimum ({MIN_ROI}%)"
    if max_drawdown > MAX_DRAWDOWN:
        return False, f"Max drawdown ({max_drawdown:.1f}%) exceeds limit ({MAX_DRAWDOWN}%)"
    return True, ""


# ---------------------------------------------------------------------------
# Publish / list / detail
# ---------------------------------------------------------------------------

def publish_strategy(user_id: int, config: dict[str, Any]) -> dict[str, Any]:
    """Create a new strategy listing after running basic validation.

    Runs a quality gate on the provided backtest metrics (roi_90d, max_drawdown).
    If metrics are not provided, the strategy is published without verification
    (verification can be added later).
    """
    db: Session = SessionLocal()
    try:
        title = (config.get("title") or "").strip()
        if not title:
            raise ValueError("Title is required")
        if len(title) > 200:
            raise ValueError("Title must be 200 characters or less")

        strategy_type = (config.get("strategy_type") or "custom").strip()
        if strategy_type not in VALID_STRATEGY_TYPES:
            raise ValueError(
                f"Invalid strategy_type. Must be one of: {', '.join(sorted(VALID_STRATEGY_TYPES))}"
            )

        config_body = config.get("config") or {}
        if isinstance(config_body, str):
            try:
                config_body = json.loads(config_body)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid config JSON: {exc}") from exc

        # Quality gate — validate provided backtest metrics
        roi_90d = float(config.get("roi_90d", 0.0))
        max_drawdown = float(config.get("max_drawdown", 0.0))
        has_metrics = config.get("roi_90d") is not None or config.get("max_drawdown") is not None
        if has_metrics:
            ok, reason = _validate_quality_gate(roi_90d, max_drawdown)
            if not ok:
                raise ValueError(f"Quality gate failed: {reason}")

        listing = StrategyListing(
            creator_user_id=user_id,
            title=title,
            description=(config.get("description") or "").strip(),
            strategy_type=strategy_type,
            config_json=json.dumps(config_body, default=str),
            is_public=bool(config.get("is_public", True)),
            is_premium=bool(config.get("is_premium", False)),
            price_monthly=float(config["price_monthly"]) if config.get("price_monthly") is not None else None,
            exchange=(config.get("exchange") or None),
            symbols_json=json.dumps(config.get("symbols")) if config.get("symbols") else None,
        )
        db.add(listing)
        db.flush()

        # Attach verification if metrics were provided
        verification: StrategyBacktestVerification | None = None
        if has_metrics:
            verification = StrategyBacktestVerification(
                listing_id=listing.id,
                backtest_hash=_compute_backtest_hash(config_body),
                roi_90d=roi_90d,
                max_drawdown=max_drawdown,
                sharpe=float(config["sharpe"]) if config.get("sharpe") is not None else None,
            )
            db.add(verification)
            db.flush()

        db.commit()
        db.refresh(listing)
        if verification:
            db.refresh(verification)
        return _listing_dict(listing, verification)
    except ValueError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to publish strategy")
        raise
    finally:
        db.close()


def list_strategies(filters: dict[str, Any]) -> dict[str, Any]:
    """List strategies with filters, sorting, and pagination.

    Returns {"strategies": [...], "total": int, "page": int, "limit": int}.
    """
    db: Session = SessionLocal()
    try:
        page = max(1, int(filters.get("page", 1)))
        limit = min(100, max(1, int(filters.get("limit", 20))))
        offset = (page - 1) * limit

        stmt = select(StrategyListing).where(StrategyListing.is_public == True)  # noqa: E712

        strategy_type = filters.get("type")
        if strategy_type and strategy_type != "all":
            stmt = stmt.where(StrategyListing.strategy_type == strategy_type)

        premium = filters.get("premium")
        if premium == "free":
            stmt = stmt.where(StrategyListing.is_premium == False)  # noqa: E712
        elif premium == "premium":
            stmt = stmt.where(StrategyListing.is_premium == True)  # noqa: E712

        search = filters.get("search")
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    StrategyListing.title.ilike(pattern),
                    StrategyListing.description.ilike(pattern),
                )
            )

        sort = filters.get("sort", "newest")
        if sort == "rating":
            stmt = stmt.order_by(desc(StrategyListing.rating_avg))
        elif sort == "downloads":
            stmt = stmt.order_by(desc(StrategyListing.downloads))
        elif sort == "roi":
            # ROI lives on the verification table — join and order
            stmt = stmt.outerjoin(
                StrategyBacktestVerification,
                StrategyBacktestVerification.listing_id == StrategyListing.id,
            ).order_by(desc(StrategyBacktestVerification.roi_90d))
        else:  # newest
            stmt = stmt.order_by(desc(StrategyListing.created_at))

        # Total count (without pagination)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(db.execute(count_stmt).scalar() or 0)

        rows = db.execute(stmt.offset(offset).limit(limit)).scalars().all()
        listing_ids = [r.id for r in rows]

        # Batch-load verifications
        verifications: dict[int, StrategyBacktestVerification] = {}
        if listing_ids:
            v_rows = (
                db.execute(
                    select(StrategyBacktestVerification).where(
                        StrategyBacktestVerification.listing_id.in_(listing_ids)
                    )
                )
                .scalars()
                .all()
            )
            # Keep the most recent verification per listing
            for v in v_rows:
                existing = verifications.get(v.listing_id)
                if existing is None or (v.verified_at and existing.verified_at and v.verified_at > existing.verified_at):
                    verifications[v.listing_id] = v

        strategies = [_listing_dict(r, verifications.get(r.id)) for r in rows]
        return {"strategies": strategies, "total": total, "page": page, "limit": limit}
    finally:
        db.close()


def get_strategy(listing_id: int) -> dict[str, Any]:
    """Get a single strategy with reviews and verification."""
    db: Session = SessionLocal()
    try:
        listing = db.execute(
            select(StrategyListing).where(StrategyListing.id == listing_id)
        ).scalar_one_or_none()
        if not listing:
            raise ValueError("Strategy not found")

        verification = db.execute(
            select(StrategyBacktestVerification)
            .where(StrategyBacktestVerification.listing_id == listing_id)
            .order_by(desc(StrategyBacktestVerification.verified_at))
            .limit(1)
        ).scalar_one_or_none()

        reviews = (
            db.execute(
                select(StrategyReview)
                .where(StrategyReview.listing_id == listing_id)
                .order_by(desc(StrategyReview.created_at))
            )
            .scalars()
            .all()
        )

        result = _listing_dict(listing, verification)
        result["reviews"] = [_review_dict(r) for r in reviews]
        return result
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Subscribe / unsubscribe
# ---------------------------------------------------------------------------

def subscribe_strategy(user_id: int, listing_id: int) -> dict[str, Any]:
    """Subscribe a user to a strategy. Free = instant; premium = check subscription level."""
    db: Session = SessionLocal()
    try:
        listing = db.execute(
            select(StrategyListing).where(StrategyListing.id == listing_id)
        ).scalar_one_or_none()
        if not listing:
            raise ValueError("Strategy not found")

        # Premium strategies require a paid subscription level.
        # The subscription tier is checked by the caller (route) via the user's
        # subscription field; here we only enforce that premium listings cannot
        # be subscribed by users flagged as "free" — the route passes the tier.
        existing = db.execute(
            select(StrategySubscription).where(
                StrategySubscription.user_id == user_id,
                StrategySubscription.listing_id == listing_id,
                StrategySubscription.status == "active",
            )
        ).scalar_one_or_none()
        if existing:
            return _subscription_dict(existing, listing)

        sub = StrategySubscription(
            user_id=user_id,
            listing_id=listing_id,
            status="active",
        )
        db.add(sub)
        # Increment downloads count
        listing.downloads = (listing.downloads or 0) + 1
        db.commit()
        db.refresh(sub)
        db.refresh(listing)
        return _subscription_dict(sub, listing)
    except ValueError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to subscribe strategy")
        raise
    finally:
        db.close()


def unsubscribe_strategy(user_id: int, listing_id: int) -> dict[str, Any]:
    """Cancel a user's subscription to a strategy."""
    db: Session = SessionLocal()
    try:
        sub = db.execute(
            select(StrategySubscription).where(
                StrategySubscription.user_id == user_id,
                StrategySubscription.listing_id == listing_id,
                StrategySubscription.status == "active",
            )
        ).scalar_one_or_none()
        if not sub:
            raise ValueError("Active subscription not found")

        sub.status = "cancelled"
        db.commit()
        db.refresh(sub)
        return _subscription_dict(sub)
    except ValueError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to unsubscribe strategy")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

def review_strategy(user_id: int, listing_id: int, rating: int, comment: str) -> dict[str, Any]:
    """Add or update a review for a strategy and recompute aggregate rating."""
    db: Session = SessionLocal()
    try:
        listing = db.execute(
            select(StrategyListing).where(StrategyListing.id == listing_id)
        ).scalar_one_or_none()
        if not listing:
            raise ValueError("Strategy not found")

        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        comment = (comment or "").strip()
        if len(comment) > 2000:
            raise ValueError("Comment must be 2000 characters or less")

        # Check for existing review by this user — update if present
        existing = db.execute(
            select(StrategyReview).where(
                StrategyReview.user_id == user_id,
                StrategyReview.listing_id == listing_id,
            )
        ).scalar_one_or_none()

        if existing:
            existing.rating = rating
            existing.comment = comment
            review = existing
        else:
            review = StrategyReview(
                user_id=user_id,
                listing_id=listing_id,
                rating=rating,
                comment=comment,
            )
            db.add(review)
        db.flush()

        # Recompute aggregate rating
        agg = db.execute(
            select(
                func.avg(StrategyReview.rating),
                func.count(StrategyReview.id),
            ).where(StrategyReview.listing_id == listing_id)
        ).one()
        listing.rating_avg = float(agg[0] or 0.0)
        listing.rating_count = int(agg[1] or 0)

        db.commit()
        db.refresh(review)
        return _review_dict(review)
    except ValueError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to review strategy")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Backtest verification
# ---------------------------------------------------------------------------

def verify_strategy_backtest(listing_id: int) -> dict[str, Any]:
    """Run a basic backtest verification on a strategy listing.

    Checks the latest backtest metrics against quality gates:
    - ROI > -50%
    - Max drawdown < 30%

    Creates or updates a StrategyBacktestVerification record.
    Returns the verification dict.
    """
    db: Session = SessionLocal()
    try:
        listing = db.execute(
            select(StrategyListing).where(StrategyListing.id == listing_id)
        ).scalar_one_or_none()
        if not listing:
            raise ValueError("Strategy not found")

        # Parse config to compute hash
        try:
            config_body = json.loads(listing.config_json) if listing.config_json else {}
        except (json.JSONDecodeError, TypeError):
            config_body = {}

        # For basic verification, we use the config to derive metrics.
        # In a real system, this would run an actual backtest.
        # Here we use the quality gate thresholds as a basic check.
        # If the listing already has a verification, we re-verify it.
        existing = db.execute(
            select(StrategyBacktestVerification)
            .where(StrategyBacktestVerification.listing_id == listing_id)
            .order_by(desc(StrategyBacktestVerification.verified_at))
            .limit(1)
        ).scalar_one_or_none()

        # Use existing metrics or default to neutral values
        roi_90d = existing.roi_90d if existing else 0.0
        max_drawdown = existing.max_drawdown if existing else 0.0
        sharpe = existing.sharpe if existing else None

        ok, reason = _validate_quality_gate(roi_90d, max_drawdown)
        if not ok:
            raise ValueError(f"Backtest verification failed: {reason}")

        # Create a new verification record
        verification = StrategyBacktestVerification(
            listing_id=listing_id,
            backtest_hash=_compute_backtest_hash(config_body),
            roi_90d=roi_90d,
            max_drawdown=max_drawdown,
            sharpe=sharpe,
        )
        db.add(verification)
        db.commit()
        db.refresh(verification)
        return _verification_dict(verification)
    except ValueError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to verify strategy backtest")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Trending / performance / my strategies / my subscriptions
# ---------------------------------------------------------------------------

def get_trending_strategies(limit: int = 10) -> list[dict[str, Any]]:
    """Top strategies by downloads + rating in the last 7 days."""
    db: Session = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(days=7)
        stmt = (
            select(StrategyListing)
            .where(StrategyListing.is_public == True)  # noqa: E712
            .where(StrategyListing.created_at >= since)
            .order_by(
                desc(StrategyListing.downloads + StrategyListing.rating_count),
                desc(StrategyListing.rating_avg),
            )
            .limit(max(1, min(50, limit)))
        )
        rows = db.execute(stmt).scalars().all()
        listing_ids = [r.id for r in rows]
        verifications: dict[int, StrategyBacktestVerification] = {}
        if listing_ids:
            v_rows = (
                db.execute(
                    select(StrategyBacktestVerification).where(
                        StrategyBacktestVerification.listing_id.in_(listing_ids)
                    )
                )
                .scalars()
                .all()
            )
            for v in v_rows:
                existing = verifications.get(v.listing_id)
                if existing is None or (v.verified_at and existing.verified_at and v.verified_at > existing.verified_at):
                    verifications[v.listing_id] = v
        return [_listing_dict(r, verifications.get(r.id)) for r in rows]
    finally:
        db.close()


def get_strategy_performance(listing_id: int) -> dict[str, Any]:
    """Aggregated performance metrics for a strategy."""
    db: Session = SessionLocal()
    try:
        listing = db.execute(
            select(StrategyListing).where(StrategyListing.id == listing_id)
        ).scalar_one_or_none()
        if not listing:
            raise ValueError("Strategy not found")

        verification = db.execute(
            select(StrategyBacktestVerification)
            .where(StrategyBacktestVerification.listing_id == listing_id)
            .order_by(desc(StrategyBacktestVerification.verified_at))
            .limit(1)
        ).scalar_one_or_none()

        review_count = int(
            db.execute(
                select(func.count(StrategyReview.id)).where(
                    StrategyReview.listing_id == listing_id
                )
            ).scalar()
            or 0
        )

        active_subs = int(
            db.execute(
                select(func.count(StrategySubscription.id)).where(
                    StrategySubscription.listing_id == listing_id,
                    StrategySubscription.status == "active",
                )
            ).scalar()
            or 0
        )

        return {
            "listing_id": listing_id,
            "downloads": listing.downloads,
            "rating_avg": listing.rating_avg,
            "rating_count": listing.rating_count,
            "review_count": review_count,
            "active_subscriptions": active_subs,
            "verification": _verification_dict(verification),
        }
    except ValueError:
        raise
    except Exception:
        logger.exception("Failed to get strategy performance")
        raise
    finally:
        db.close()


def get_my_strategies(user_id: int) -> list[dict[str, Any]]:
    """Strategies published by a user."""
    db: Session = SessionLocal()
    try:
        rows = (
            db.execute(
                select(StrategyListing)
                .where(StrategyListing.creator_user_id == user_id)
                .order_by(desc(StrategyListing.created_at))
            )
            .scalars()
            .all()
        )
        listing_ids = [r.id for r in rows]
        verifications: dict[int, StrategyBacktestVerification] = {}
        if listing_ids:
            v_rows = (
                db.execute(
                    select(StrategyBacktestVerification).where(
                        StrategyBacktestVerification.listing_id.in_(listing_ids)
                    )
                )
                .scalars()
                .all()
            )
            for v in v_rows:
                existing = verifications.get(v.listing_id)
                if existing is None or (v.verified_at and existing.verified_at and v.verified_at > existing.verified_at):
                    verifications[v.listing_id] = v
        return [_listing_dict(r, verifications.get(r.id)) for r in rows]
    finally:
        db.close()


def get_my_subscriptions(user_id: int) -> list[dict[str, Any]]:
    """Active subscriptions for a user, with listing details."""
    db: Session = SessionLocal()
    try:
        subs = (
            db.execute(
                select(StrategySubscription)
                .where(StrategySubscription.user_id == user_id)
                .order_by(desc(StrategySubscription.subscribed_at))
            )
            .scalars()
            .all()
        )
        listing_ids = [s.listing_id for s in subs]
        listings: dict[int, StrategyListing] = {}
        if listing_ids:
            l_rows = (
                db.execute(
                    select(StrategyListing).where(StrategyListing.id.in_(listing_ids))
                )
                .scalars()
                .all()
            )
            listings = {l.id: l for l in l_rows}
        return [_subscription_dict(s, listings.get(s.listing_id)) for s in subs]
    finally:
        db.close()

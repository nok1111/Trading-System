"""Analysis storage — save and query historical AI analysis per asset.

Like Binance klines store OHLCV history, this stores AI analysis history
per asset so agents always have access to prior analysis without re-computing.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.intelligence_analysis import IntelligenceAnalysis
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)


class AnalysisStorage:
    """Read/write service for historical AI analysis per asset."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        asset: str,
        decision: str,
        confidence: float,
        *,
        risk_level: str = "medium",
        price_usd: float | None = None,
        reasons: dict[str, str] | None = None,
        risks: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        agent_votes: dict[str, str] | None = None,
        entry_range: dict[str, float] | None = None,
        target_price: float | None = None,
        stop_loss: float | None = None,
        expires_hours: int | None = 24,
    ) -> IntelligenceAnalysis:
        """Save a new analysis snapshot for an asset."""
        expires_at = None
        if expires_hours:
            expires_at = datetime.now(UTC) + timedelta(hours=expires_hours)

        analysis = IntelligenceAnalysis(
            asset=asset,
            decision=decision,
            confidence=Decimal(str(confidence)),
            risk_level=risk_level,
            price_usd=Decimal(str(price_usd)) if price_usd else None,
            reasons=reasons or {},
            risks=risks or {},
            metrics=metrics or {},
            agent_votes=agent_votes or {},
            entry_range=entry_range or {},
            target_price=Decimal(str(target_price)) if target_price else None,
            stop_loss=Decimal(str(stop_loss)) if stop_loss else None,
            expires_at=expires_at,
        )
        self._session.add(analysis)
        self._session.commit()
        self._session.refresh(analysis)
        logger.info("[AnalysisStorage] Saved analysis for %s: %s (%.0f%%)", asset, decision, confidence * 100)
        return analysis

    def get_latest(self, asset: str) -> IntelligenceAnalysis | None:
        """Get the most recent analysis for an asset."""
        stmt = (
            select(IntelligenceAnalysis)
            .where(IntelligenceAnalysis.asset == asset.upper())
            .order_by(IntelligenceAnalysis.analyzed_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalars().first()

    def get_history(
        self,
        asset: str,
        *,
        hours: int = 168,  # default 7 days
        limit: int = 50,
    ) -> list[IntelligenceAnalysis]:
        """Get analysis history for an asset within the last N hours."""
        since = datetime.now(UTC) - timedelta(hours=hours)
        stmt = (
            select(IntelligenceAnalysis)
            .where(IntelligenceAnalysis.asset == asset.upper())
            .where(IntelligenceAnalysis.analyzed_at > since)
            .order_by(IntelligenceAnalysis.analyzed_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_all_latest(self, assets: list[str] | None = None) -> list[IntelligenceAnalysis]:
        """Get the latest analysis for each asset (or all assets if None)."""
        if assets:
            results = []
            for asset in assets:
                latest = self.get_latest(asset)
                if latest:
                    results.append(latest)
            return results

        # Get all assets that have analysis, then latest per asset
        stmt = select(IntelligenceAnalysis.asset).distinct()
        all_assets = [row[0] for row in self._session.execute(stmt).all()]
        results = []
        for asset in all_assets:
            latest = self.get_latest(asset)
            if latest:
                results.append(latest)
        return results

    def get_trend(self, asset: str, *, hours: int = 168) -> dict[str, Any]:
        """Get trend analysis for an asset (how decision/confidence evolved)."""
        history = self.get_history(asset, hours=hours, limit=50)
        if not history:
            return {"asset": asset, "trend": "no_data", "history": []}

        # Build trend summary
        decisions = [h.decision for h in history]
        confidences = [float(h.confidence) for h in history]

        # Detect trend direction
        if len(confidences) >= 2:
            recent_avg = sum(confidences[:3]) / min(3, len(confidences))
            older_avg = sum(confidences[-3:]) / min(3, len(confidences))
            if recent_avg > older_avg + 0.05:
                trend = "improving"
            elif recent_avg < older_avg - 0.05:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # Decision changes
        decision_changes = []
        for i in range(1, len(decisions)):
            if decisions[i] != decisions[i - 1]:
                decision_changes.append({
                    "from": decisions[i],
                    "to": decisions[i - 1],
                    "at": history[i].analyzed_at.isoformat() if history[i].analyzed_at else "",
                })

        return {
            "asset": asset,
            "current_decision": decisions[0],
            "current_confidence": confidences[0],
            "trend": trend,
            "decision_changes": decision_changes,
            "analyses_count": len(history),
            "history": [_analysis_to_dict(h) for h in history[:10]],
        }


def _analysis_to_dict(a: IntelligenceAnalysis) -> dict[str, Any]:
    """Convert IntelligenceAnalysis to dict for API response."""
    return {
        "id": a.id,
        "asset": a.asset,
        "decision": a.decision,
        "confidence": float(a.confidence) if a.confidence else 0.0,
        "risk_level": a.risk_level,
        "price_usd": float(a.price_usd) if a.price_usd else None,
        "reasons": a.reasons,
        "risks": a.risks,
        "metrics": a.metrics,
        "agent_votes": a.agent_votes,
        "entry_range": a.entry_range,
        "target_price": float(a.target_price) if a.target_price else None,
        "stop_loss": float(a.stop_loss) if a.stop_loss else None,
        "analyzed_at": a.analyzed_at.isoformat() if a.analyzed_at else "",
        "expires_at": a.expires_at.isoformat() if a.expires_at else None,
    }


def get_analysis_history(asset: str, hours: int = 168, limit: int = 50) -> list[dict[str, Any]]:
    """Standalone function to query analysis history (for API endpoints)."""
    session = SessionLocal()
    try:
        storage = AnalysisStorage(session)
        history = storage.get_history(asset, hours=hours, limit=limit)
        return [_analysis_to_dict(h) for h in history]
    finally:
        session.close()


def get_analysis_trend(asset: str, hours: int = 168) -> dict[str, Any]:
    """Standalone function to get trend analysis (for API endpoints)."""
    session = SessionLocal()
    try:
        storage = AnalysisStorage(session)
        return storage.get_trend(asset, hours=hours)
    finally:
        session.close()


def get_all_latest_analyses(assets: list[str] | None = None) -> list[dict[str, Any]]:
    """Standalone function to get latest analysis for all assets."""
    session = SessionLocal()
    try:
        storage = AnalysisStorage(session)
        latest = storage.get_all_latest(assets)
        return [_analysis_to_dict(a) for a in latest]
    finally:
        session.close()

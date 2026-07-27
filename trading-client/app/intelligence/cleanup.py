"""Cleanup job — periodically deletes old news and analysis to prevent DB bloat.

Runs on a schedule (e.g. daily) to prune:
- News older than N days (default: 7)
- Analysis snapshots older than N days (default: 30)
- Event journal entries older than N days (default: 14)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.database.models.intelligence_analysis import IntelligenceAnalysis
from app.database.models.intelligence_event import IntelligenceEvent
from app.database.models.intelligence_news import IntelligenceNews
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)

# Retention periods (days)
NEWS_RETENTION_DAYS = 7
ANALYSIS_RETENTION_DAYS = 30
EVENT_RETENTION_DAYS = 14


def cleanup_old_news(days: int = NEWS_RETENTION_DAYS) -> int:
    """Delete news articles older than N days. Returns count deleted."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    session = SessionLocal()
    try:
        # Count first
        count_stmt = select(func.count()).select_from(IntelligenceNews).where(
            IntelligenceNews.published_at < cutoff
        )
        total = session.execute(count_stmt).scalar() or 0

        # Delete
        stmt = delete(IntelligenceNews).where(IntelligenceNews.published_at < cutoff)
        result = session.execute(stmt)
        session.commit()
        logger.info("[Cleanup] Deleted %d news articles older than %d days", total, days)
        return total
    except Exception as exc:
        session.rollback()
        logger.error("[Cleanup] Failed to cleanup news: %s", exc)
        return 0
    finally:
        session.close()


def cleanup_old_analysis(days: int = ANALYSIS_RETENTION_DAYS) -> int:
    """Delete analysis snapshots older than N days. Returns count deleted."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    session = SessionLocal()
    try:
        count_stmt = select(func.count()).select_from(IntelligenceAnalysis).where(
            IntelligenceAnalysis.analyzed_at < cutoff
        )
        total = session.execute(count_stmt).scalar() or 0

        stmt = delete(IntelligenceAnalysis).where(IntelligenceAnalysis.analyzed_at < cutoff)
        result = session.execute(stmt)
        session.commit()
        logger.info("[Cleanup] Deleted %d analysis records older than %d days", total, days)
        return total
    except Exception as exc:
        session.rollback()
        logger.error("[Cleanup] Failed to cleanup analysis: %s", exc)
        return 0
    finally:
        session.close()


def cleanup_old_events(days: int = EVENT_RETENTION_DAYS) -> int:
    """Delete event journal entries older than N days. Returns count deleted."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    session = SessionLocal()
    try:
        count_stmt = select(func.count()).select_from(IntelligenceEvent).where(
            IntelligenceEvent.created_at < cutoff
        )
        total = session.execute(count_stmt).scalar() or 0

        stmt = delete(IntelligenceEvent).where(IntelligenceEvent.created_at < cutoff)
        result = session.execute(stmt)
        session.commit()
        logger.info("[Cleanup] Deleted %d event journal entries older than %d days", total, days)
        return total
    except Exception as exc:
        session.rollback()
        logger.error("[Cleanup] Failed to cleanup events: %s", exc)
        return 0
    finally:
        session.close()


def run_cleanup() -> dict[str, int]:
    """Run all cleanup tasks. Returns summary of deleted counts."""
    results = {
        "news_deleted": cleanup_old_news(),
        "analysis_deleted": cleanup_old_analysis(),
        "events_deleted": cleanup_old_events(),
    }
    logger.info("[Cleanup] Complete: %s", results)
    return results

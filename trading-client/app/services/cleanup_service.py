"""Cleanup service — periodically removes old data from the database.

Retention policy by type:
  - Notification: 30 days
  - AIRecommendation: 90 days
  - AgentLog: 7 days
  - AgentSession: 90 days (terminated only)
  - Signal: 30 days
  - RiskEvent: 30 days
  - IntelligenceEvent: 30 days
  - IntelligenceNews: 7 days
  - PredictionRecord: 90 days
  - AccountSnapshot: 30 days
  - SystemEvent: 30 days
"""

import logging
from datetime import datetime, timedelta, UTC

logger = logging.getLogger(__name__)

# Retention periods in days
RETENTION_DAYS = {
    "notifications": 30,
    "ai_recommendations": 90,
    "agent_logs": 7,
    "agent_sessions": 90,
    "signals": 30,
    "risk_events": 30,
    "intelligence_events": 30,
    "intelligence_news": 7,
    "prediction_records": 90,
    "account_snapshots": 30,
    "system_events": 30,
}


def cleanup_old_data(db, user_id: int | None = None) -> dict:
    """Delete old data from the database based on retention policy.

    Args:
        db: SQLAlchemy session
        user_id: If provided, only clean up data for this user. If None, clean all.

    Returns:
        Dict with table name -> count of deleted rows.
    """
    from app.database.models.notification import Notification
    from app.database.models.ai_recommendation import AIRecommendation
    from app.database.models.agent_log import AgentLog
    from app.database.models.agent_session import AgentSession
    from app.database.models.signal import Signal
    from app.database.models.risk_event import RiskEvent
    from app.database.models.intelligence_event import IntelligenceEvent
    from app.database.models.intelligence_news import IntelligenceNews
    from app.database.models.prediction_record import PredictionRecord
    from app.database.models.account_snapshot import AccountSnapshot
    from app.database.models.system_event import SystemEvent

    now = datetime.now(UTC)
    deleted = {}

    cleanup_tasks = [
        (Notification, "notifications", Notification.created_at),
        (AIRecommendation, "ai_recommendations", AIRecommendation.created_at),
        (AgentLog, "agent_logs", AgentLog.timestamp),
        (AgentSession, "agent_sessions", AgentSession.started_at),
        (Signal, "signals", Signal.created_at),
        (RiskEvent, "risk_events", RiskEvent.created_at),
        (IntelligenceEvent, "intelligence_events", IntelligenceEvent.created_at),
        (IntelligenceNews, "intelligence_news", IntelligenceNews.created_at),
        (PredictionRecord, "prediction_records", PredictionRecord.created_at),
        (AccountSnapshot, "account_snapshots", AccountSnapshot.created_at),
        (SystemEvent, "system_events", SystemEvent.created_at),
    ]

    for model, table_name, date_col in cleanup_tasks:
        days = RETENTION_DAYS.get(table_name, 30)
        cutoff = now - timedelta(days=days)

        query = db.query(model).filter(date_col < cutoff)

        # For agent_sessions, only clean up terminated sessions
        if model == AgentSession:
            query = query.filter(AgentSession.status != "running")

        if user_id is not None:
            query = query.filter(model.user_id == user_id)

        count = query.count()
        if count > 0:
            query.delete(synchronize_session=False)
            db.commit()
            deleted[table_name] = count
            logger.info("Cleanup: deleted %d rows from %s (older than %d days)", count, table_name, days)
        else:
            deleted[table_name] = 0

    return deleted

"""Modelos de datos del Market Knowledge Base — ai-server Fase C.

Tablas:
- market_signals: señales globales con consenso
- market_alerts: alertas de riesgo
- market_scenarios: escenarios probabilísticos
- market_reports: reportes periódicos
- signal_invalidations: invalidaciones de señales
- pending_notifications: notificaciones pendientes por usuario
"""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


# Notification states
NOTIFICATION_STATES = ["PENDING", "DELIVERED", "READ", "EXPIRED", "SUPERSEDED", "CANCELLED"]

# Signal states
SIGNAL_STATES = ["ACTIVE", "EXPIRED", "INVALIDATED", "SUPERSEDED", "CANCELLED"]


class MarketSignal(Base):
    """Señal global generada por el Consensus Agent."""

    __tablename__ = "market_signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset: Mapped[str] = mapped_column(String(32), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(20), nullable=False)  # BUY, SELL, HOLD, TAKE_PROFIT, AVOID, WAIT
    decision: Mapped[str] = mapped_column(String(50), nullable=False)  # BUY_ON_PULLBACK, etc.
    confidence: Mapped[float] = mapped_column(nullable=False)
    agreement_positive: Mapped[int] = mapped_column(nullable=False, default=0)
    agreement_neutral: Mapped[int] = mapped_column(nullable=False, default=0)
    agreement_negative: Mapped[int] = mapped_column(nullable=False, default=0)
    main_reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    main_risks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    consensus_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_market_signals_asset", "asset"),
        Index("ix_market_signals_status", "status"),
        Index("ix_market_signals_timestamp", "timestamp"),
    )


class MarketAlert(Base):
    """Alerta de riesgo de mercado."""

    __tablename__ = "market_alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset: Mapped[str] = mapped_column(String(32), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)  # crash_risk, volatility, liquidity_drop
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # low, medium, high
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_market_alerts_asset", "asset"),
        Index("ix_market_alerts_severity", "severity"),
        Index("ix_market_alerts_timestamp", "timestamp"),
    )


class MarketScenario(Base):
    """Escenario probabilístico para un activo."""

    __tablename__ = "market_scenarios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset: Mapped[str] = mapped_column(String(32), nullable=False)
    horizon: Mapped[str] = mapped_column(String(20), nullable=False)  # 1d, 7d, 30d
    current_price: Mapped[float] = mapped_column(nullable=False)
    scenarios: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # [{name, probability, range}]
    invalidation_conditions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_market_scenarios_asset", "asset"),
        Index("ix_market_scenarios_timestamp", "timestamp"),
    )


class MarketReport(Base):
    """Reporte periódico de mercado."""

    __tablename__ = "market_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset: Mapped[str] = mapped_column(String(32), nullable=False)
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)  # daily, weekly, event
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    period: Mapped[str] = mapped_column(String(30), nullable=False)  # 2025-01-15, 2025-W03, etc.
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), server_default=func.now())

    __table_args__ = (
        Index("ix_market_reports_asset", "asset"),
        Index("ix_market_reports_type", "report_type"),
        Index("ix_market_reports_timestamp", "timestamp"),
    )


class SignalInvalidation(Base):
    """Invalidación de una señal anterior."""

    __tablename__ = "signal_invalidations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    signal_id: Mapped[int] = mapped_column(
        ForeignKey("market_signals.id"), nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), server_default=func.now())

    __table_args__ = (
        Index("ix_signal_invalidations_signal_id", "signal_id"),
    )


class PendingNotification(Base):
    """Notificación pendiente para un usuario."""

    __tablename__ = "pending_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)  # signal, alert, report, recommendation
    asset: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    supersedes_id: Mapped[int | None] = mapped_column(nullable=True)  # ID de la notificación que reemplaza

    __table_args__ = (
        Index("ix_pending_notifications_user", "user_id_hash"),
        Index("ix_pending_notifications_status", "status"),
        Index("ix_pending_notifications_created", "created_at"),
    )


class HmacNonce(Base):
    """Persisted nonce for HMAC anti-replay protection (survives restarts)."""

    __tablename__ = "hmac_nonces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_hmac_nonces_expires", "expires_at"),
    )

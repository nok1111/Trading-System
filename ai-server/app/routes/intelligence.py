"""Endpoints de la Plataforma de Inteligencia de Mercado — /v1/intelligence.

Nuevos endpoints para la arquitectura autónoma 24/7:
- GET  /v1/intelligence/signals — señales globales recientes
- GET  /v1/intelligence/alerts — alertas activas
- GET  /v1/intelligence/scenarios/{asset} — escenarios probabilísticos
- GET  /v1/intelligence/pending — notificaciones pendientes del usuario
- POST /v1/intelligence/pending/{id}/read — marcar como leída
- POST /v1/intelligence/portfolio-match — personalización por usuario
- GET  /v1/intelligence/agents — listar agentes de inteligencia
- GET  /v1/intelligence/reports/{asset} — reportes periódicos
- POST /v1/intelligence/signals — guardar señal del scheduler en BD
- POST /v1/intelligence/alerts — guardar alerta del scheduler en BD
"""

from __future__ import annotations

import logging
from datetime import UTC
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.database.models import (
    MarketAlert,
    MarketReport,
    MarketScenario,
    MarketSignal,
    PendingNotification,
)
from app.services.intelligence_agents import list_intelligence_agents
from app.services.notifications import NotificationGenerator, PendingQueue
from app.services.portfolio_matcher import PortfolioMatcher, UserPortfolio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/intelligence", tags=["intelligence"])
settings = get_settings()


# --- JWT Dependency (optional, controlled by INTELLIGENCE_REQUIRE_JWT flag) ---

def _validate_jwt(jwt_token: str) -> dict | None:
    """Validate JWT against the Auth Server."""
    try:
        resp = httpx.post(
            f"{settings.AUTH_SERVER_URL}/api/license/validate",
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error(f"JWT validation failed: {exc}")
        return None


async def optional_verify_jwt(
    authorization: Annotated[str | None, Header()] = None,
) -> dict | None:
    """Verify JWT only when INTELLIGENCE_REQUIRE_JWT=True.

    When False (default for dev/testing), returns None and allows all requests.
    When True, validates the JWT against the Auth Server.
    """
    if not settings.INTELLIGENCE_REQUIRE_JWT:
        return None

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.removeprefix("Bearer ")
    payload = _validate_jwt(token)
    if not payload or not payload.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT invalid or expired",
        )
    return payload


# --- Models ---

class PortfolioMatchRequest(BaseModel):
    """Request para personalización de señales por portafolio."""

    user_id_hash: str = Field(min_length=8, max_length=128)
    signal: dict[str, Any] = Field(description="Señal global del Consensus Agent")
    portfolio: dict[str, Any] = Field(description="Portafolio del usuario")


class PortfolioMatchResponse(BaseModel):
    """Respuesta con la recomendación personalizada."""

    asset: str
    market_decision: str
    personal_recommendation: str
    reason: str
    suggested_action: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    notification: dict[str, Any] = Field(default_factory=dict)


class PendingNotificationResponse(BaseModel):
    """Respuesta con notificaciones pendientes."""

    notifications: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class SignalResponse(BaseModel):
    """Respuesta con señales globales."""

    signals: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


class AlertResponse(BaseModel):
    """Respuesta con alertas activas."""

    alerts: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


class ScenarioResponse(BaseModel):
    """Respuesta con escenarios probabilísticos."""

    asset: str
    scenarios: list[dict[str, Any]] = Field(default_factory=list)


class ReportResponse(BaseModel):
    """Respuesta con reportes de mercado."""

    asset: str
    reports: list[dict[str, Any]] = Field(default_factory=list)


class CreateSignalRequest(BaseModel):
    """Request para guardar una señal del scheduler."""

    asset: str
    signal_type: str
    decision: str
    confidence: float = Field(ge=0, le=1)
    agreement_positive: int = 0
    agreement_neutral: int = 0
    agreement_negative: int = 0
    main_reasons: list[str] = Field(default_factory=list)
    main_risks: list[str] = Field(default_factory=list)
    consensus_data: dict[str, Any] = Field(default_factory=dict)
    expires_hours: int = 24


class CreateAlertRequest(BaseModel):
    """Request para guardar una alerta del scheduler."""

    asset: str
    alert_type: str
    severity: str = Field(pattern="^(low|medium|high)$")
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    expires_hours: int = 12


class SchedulerStatusResponse(BaseModel):
    """Estado del scheduler."""

    running: bool
    symbols: list[str] = Field(default_factory=list)
    interval_seconds: int = 60


# --- Endpoints ---

@router.get("/signals", response_model=SignalResponse)
async def get_signals(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[dict | None, Depends(optional_verify_jwt)] = None,
    asset: str | None = None,
    limit: int = 20,
) -> SignalResponse:
    """Obtiene señales globales recientes del Market Knowledge Base."""
    query = (
        select(MarketSignal)
        .where(MarketSignal.status == "ACTIVE")
        .order_by(MarketSignal.timestamp.desc())
        .limit(limit)
    )
    if asset:
        query = query.where(MarketSignal.asset == asset.upper())

    result = db.execute(query)
    signals = result.scalars().all()

    return SignalResponse(
        signals=[
            {
                "id": s.id,
                "asset": s.asset,
                "signal_type": s.signal_type,
                "decision": s.decision,
                "confidence": s.confidence,
                "agreement": {
                    "positive": s.agreement_positive,
                    "neutral": s.agreement_neutral,
                    "negative": s.agreement_negative,
                },
                "main_reasons": s.main_reasons,
                "main_risks": s.main_risks,
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            }
            for s in signals
        ],
        count=len(signals),
    )


@router.get("/alerts", response_model=AlertResponse)
async def get_alerts(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[dict | None, Depends(optional_verify_jwt)] = None,
    asset: str | None = None,
    severity: str | None = None,
    limit: int = 20,
) -> AlertResponse:
    """Obtiene alertas activas del Market Knowledge Base."""
    query = (
        select(MarketAlert)
        .where(MarketAlert.status == "ACTIVE")
        .order_by(MarketAlert.timestamp.desc())
        .limit(limit)
    )
    if asset:
        query = query.where(MarketAlert.asset == asset.upper())
    if severity:
        query = query.where(MarketAlert.severity == severity.lower())

    result = db.execute(query)
    alerts = result.scalars().all()

    return AlertResponse(
        alerts=[
            {
                "id": a.id,
                "asset": a.asset,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "message": a.message,
                "details": a.details,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            }
            for a in alerts
        ],
        count=len(alerts),
    )


@router.get("/scenarios/{asset}", response_model=ScenarioResponse)
async def get_scenarios(
    asset: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[dict | None, Depends(optional_verify_jwt)] = None,
    limit: int = 5,
) -> ScenarioResponse:
    """Obtiene escenarios probabilísticos para un activo."""
    result = db.execute(
        select(MarketScenario)
        .where(MarketScenario.asset == asset.upper())
        .order_by(MarketScenario.timestamp.desc())
        .limit(limit)
    )
    scenarios = result.scalars().all()

    return ScenarioResponse(
        asset=asset.upper(),
        scenarios=[
            {
                "id": s.id,
                "horizon": s.horizon,
                "current_price": s.current_price,
                "scenarios": s.scenarios,
                "invalidation_conditions": s.invalidation_conditions,
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            }
            for s in scenarios
        ],
    )


@router.get("/pending", response_model=PendingNotificationResponse)
async def get_pending(
    user_id_hash: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[dict | None, Depends(optional_verify_jwt)] = None,
    limit: int = 50,
) -> PendingNotificationResponse:
    """Obtiene notificaciones pendientes del usuario."""
    queue = PendingQueue(db)
    pending = queue.get_pending(user_id_hash, limit=limit)
    summary = queue.get_pending_summary(user_id_hash)

    return PendingNotificationResponse(
        notifications=[
            {
                "id": n.id,
                "notification_type": n.notification_type,
                "asset": n.asset,
                "content": n.content,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "expires_at": n.expires_at.isoformat() if n.expires_at else None,
            }
            for n in pending
        ],
        summary=summary,
    )


@router.post("/pending/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notification_id: int,
    user_id_hash: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[dict | None, Depends(optional_verify_jwt)] = None,
) -> dict:
    """Marca una notificación como leída."""
    queue = PendingQueue(db)
    notif = db.get(PendingNotification, notification_id)
    if notif is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notif.user_id_hash != user_id_hash:
        raise HTTPException(status_code=403, detail="Not authorized")

    success = queue.mark_read(notification_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot mark as read")

    return {"status": "read", "notification_id": notification_id}


@router.post("/portfolio-match", response_model=PortfolioMatchResponse)
async def portfolio_match(
    req: PortfolioMatchRequest,
    _user: Annotated[dict | None, Depends(optional_verify_jwt)] = None,
) -> PortfolioMatchResponse:
    """Personaliza una señal global según el portafolio del usuario.

    NO usa IA — es puramente determinista (Portfolio Matcher).
    """
    matcher = PortfolioMatcher()
    notif_gen = NotificationGenerator()

    portfolio = UserPortfolio(
        user_id_hash=req.user_id_hash,
        broker=req.portfolio.get("broker", "binance"),
        risk_profile=req.portfolio.get("risk_profile", "intermediate"),
        max_allocation_pct=req.portfolio.get("max_allocation_pct", 40.0),
        max_risk_per_trade_pct=req.portfolio.get("max_risk_per_trade_pct", 2.0),
        positions=req.portfolio.get("positions", []),
        total_portfolio_value=req.portfolio.get("total_portfolio_value", 0.0),
        cash_pct=req.portfolio.get("cash_pct", 0.0),
    )

    recommendation = matcher.match_signals_to_user(req.signal, portfolio)
    notification = notif_gen.generate_from_recommendation({
        "personal_recommendation": recommendation.personal_recommendation,
        "asset": recommendation.asset,
        "reason": recommendation.reason,
        "confidence": recommendation.confidence,
        "suggested_action": recommendation.suggested_action,
    })

    return PortfolioMatchResponse(
        asset=recommendation.asset,
        market_decision=recommendation.market_decision,
        personal_recommendation=recommendation.personal_recommendation,
        reason=recommendation.reason,
        suggested_action=recommendation.suggested_action,
        confidence=recommendation.confidence,
        notification=notification,
    )


@router.get("/reports/{asset}", response_model=ReportResponse)
async def get_reports(
    asset: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[dict | None, Depends(optional_verify_jwt)] = None,
    report_type: str | None = None,
    limit: int = 10,
) -> ReportResponse:
    """Obtiene reportes periódicos de un activo."""
    query = (
        select(MarketReport)
        .where(MarketReport.asset == asset.upper())
        .order_by(MarketReport.timestamp.desc())
        .limit(limit)
    )
    if report_type:
        query = query.where(MarketReport.report_type == report_type)

    result = db.execute(query)
    reports = result.scalars().all()

    return ReportResponse(
        asset=asset.upper(),
        reports=[
            {
                "id": r.id,
                "report_type": r.report_type,
                "content": r.content,
                "period": r.period,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in reports
        ],
    )


@router.post("/signals", status_code=status.HTTP_201_CREATED)
async def create_signal(
    req: CreateSignalRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Guarda una señal global en el Market Knowledge Base.

    Usado por el scheduler cuando el Consensus Agent produce una nueva señal.
    """
    from datetime import datetime, timedelta

    # Marcar señales anteriores del mismo asset como SUPERSEDED
    old_signals = db.execute(
        select(MarketSignal)
        .where(MarketSignal.asset == req.asset.upper(), MarketSignal.status == "ACTIVE")
    ).scalars().all()
    for old in old_signals:
        old.status = "SUPERSEDED"

    signal = MarketSignal(
        asset=req.asset.upper(),
        signal_type=req.signal_type,
        decision=req.decision,
        confidence=req.confidence,
        agreement_positive=req.agreement_positive,
        agreement_neutral=req.agreement_neutral,
        agreement_negative=req.agreement_negative,
        main_reasons=req.main_reasons,
        main_risks=req.main_risks,
        consensus_data=req.consensus_data,
        status="ACTIVE",
        expires_at=datetime.now(UTC) + timedelta(hours=req.expires_hours),
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return {"id": signal.id, "status": "created", "asset": signal.asset}


@router.post("/alerts", status_code=status.HTTP_201_CREATED)
async def create_alert(
    req: CreateAlertRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Guarda una alerta de mercado en el Knowledge Base.

    Usado por el scheduler cuando el Crash Risk Detector detecta riesgo elevado.
    """
    from datetime import datetime, timedelta

    alert = MarketAlert(
        asset=req.asset.upper(),
        alert_type=req.alert_type,
        severity=req.severity,
        message=req.message,
        details=req.details,
        status="ACTIVE",
        expires_at=datetime.now(UTC) + timedelta(hours=req.expires_hours),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return {"id": alert.id, "status": "created", "asset": alert.asset}


@router.get("/agents")
async def list_intelligence_agents_endpoint() -> dict:
    """Lista los agentes de inteligencia disponibles."""
    return {"agents": list_intelligence_agents()}


# --- Scheduler endpoints ---

@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def scheduler_status() -> SchedulerStatusResponse:
    """Obtiene el estado del scheduler."""
    from app.services.scheduler import get_scheduler
    sched = get_scheduler()
    s = sched.status()
    return SchedulerStatusResponse(
        running=s["running"],
        symbols=s["symbols"],
        interval_seconds=s["interval_seconds"],
    )


@router.post("/scheduler/start", status_code=status.HTTP_200_OK)
async def scheduler_start() -> dict:
    """Inicia el scheduler 24/7."""
    from app.services.scheduler import get_scheduler
    sched = get_scheduler()
    success = sched.start()
    if not success:
        raise HTTPException(status_code=400, detail="Scheduler could not start (disabled or already running)")
    return {"status": "started"}


@router.post("/scheduler/stop", status_code=status.HTTP_200_OK)
async def scheduler_stop() -> dict:
    """Detiene el scheduler."""
    from app.services.scheduler import get_scheduler
    sched = get_scheduler()
    success = sched.stop()
    if not success:
        raise HTTPException(status_code=400, detail="Scheduler not running")
    return {"status": "stopped"}

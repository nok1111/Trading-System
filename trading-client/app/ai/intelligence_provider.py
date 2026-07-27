"""IntelligenceProvider — consulta la Plataforma de Inteligencia de Mercado del ai-server.

Cuando USE_INTELLIGENCE_API=True, el trading-client usa este provider para:
1. Obtener señales globales del Market Knowledge Base
2. Obtener alertas activas
3. Obtener notificaciones pendientes del usuario
4. Personalizar señales con el portafolio del usuario
5. Marcar notificaciones como leídas

NO envía prompts ni llama IA directamente — el ai-server hace el análisis
global una vez y este provider solo consume los resultados personalizados.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class IntelligenceSignal:
    """Señal global del Market Knowledge Base."""

    id: int
    asset: str
    signal_type: str
    decision: str
    confidence: float
    agreement: dict[str, int] = field(default_factory=dict)
    main_reasons: list[str] = field(default_factory=list)
    main_risks: list[str] = field(default_factory=list)
    timestamp: str = ""
    expires_at: str | None = None


@dataclass
class IntelligenceAlert:
    """Alerta de mercado activa."""

    id: int
    asset: str
    alert_type: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class PendingNotificationItem:
    """Notificación pendiente para el usuario."""

    id: int
    notification_type: str
    asset: str
    content: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    expires_at: str | None = None


@dataclass
class PersonalRecommendation:
    """Recomendación personalizada del Portfolio Matcher."""

    asset: str
    market_decision: str
    personal_recommendation: str
    reason: str
    suggested_action: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    notification: dict[str, Any] = field(default_factory=dict)


class IntelligenceProvider:
    """Cliente HTTP para los endpoints /v1/intelligence del ai-server.

    Requiere USE_INTELLIGENCE_API=True y REMOTE_AI_URL configurado.
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def get_signals(
        self,
        asset: str | None = None,
        limit: int = 20,
    ) -> list[IntelligenceSignal]:
        """Obtiene señales globales activas."""
        params: dict[str, Any] = {"limit": limit}
        if asset:
            params["asset"] = asset
        try:
            resp = httpx.get(
                f"{self._base_url}/v1/intelligence/signals",
                headers=self._headers(),
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                IntelligenceSignal(
                    id=s["id"],
                    asset=s["asset"],
                    signal_type=s["signal_type"],
                    decision=s["decision"],
                    confidence=s["confidence"],
                    agreement=s.get("agreement", {}),
                    main_reasons=s.get("main_reasons", []),
                    main_risks=s.get("main_risks", []),
                    timestamp=s.get("timestamp", ""),
                    expires_at=s.get("expires_at"),
                )
                for s in data.get("signals", [])
            ]
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to get signals: %s", exc)
            return []

    def get_alerts(
        self,
        asset: str | None = None,
        severity: str | None = None,
        limit: int = 20,
    ) -> list[IntelligenceAlert]:
        """Obtiene alertas activas."""
        params: dict[str, Any] = {"limit": limit}
        if asset:
            params["asset"] = asset
        if severity:
            params["severity"] = severity
        try:
            resp = httpx.get(
                f"{self._base_url}/v1/intelligence/alerts",
                headers=self._headers(),
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                IntelligenceAlert(
                    id=a["id"],
                    asset=a["asset"],
                    alert_type=a["alert_type"],
                    severity=a["severity"],
                    message=a["message"],
                    details=a.get("details", {}),
                    timestamp=a.get("timestamp", ""),
                )
                for a in data.get("alerts", [])
            ]
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to get alerts: %s", exc)
            return []

    def get_pending_notifications(
        self,
        user_id_hash: str,
        limit: int = 50,
    ) -> list[PendingNotificationItem]:
        """Obtiene notificaciones pendientes del usuario."""
        try:
            resp = httpx.get(
                f"{self._base_url}/v1/intelligence/pending",
                headers=self._headers(),
                params={"user_id_hash": user_id_hash, "limit": limit},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                PendingNotificationItem(
                    id=n["id"],
                    notification_type=n["notification_type"],
                    asset=n["asset"],
                    content=n.get("content", {}),
                    created_at=n.get("created_at", ""),
                    expires_at=n.get("expires_at"),
                )
                for n in data.get("notifications", [])
            ]
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to get pending notifications: %s", exc)
            return []

    def mark_notification_read(
        self,
        notification_id: int,
        user_id_hash: str,
    ) -> bool:
        """Marca una notificación como leída."""
        try:
            resp = httpx.post(
                f"{self._base_url}/v1/intelligence/pending/{notification_id}/read",
                headers=self._headers(),
                params={"user_id_hash": user_id_hash},
                timeout=self._timeout,
            )
            return resp.status_code == 200
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to mark notification read: %s", exc)
            return False

    def portfolio_match(
        self,
        user_id_hash: str,
        signal: dict[str, Any],
        portfolio: dict[str, Any],
    ) -> PersonalRecommendation | None:
        """Personaliza una señal global según el portafolio del usuario."""
        try:
            resp = httpx.post(
                f"{self._base_url}/v1/intelligence/portfolio-match",
                headers=self._headers(),
                json={
                    "user_id_hash": user_id_hash,
                    "signal": signal,
                    "portfolio": portfolio,
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return PersonalRecommendation(
                asset=data["asset"],
                market_decision=data["market_decision"],
                personal_recommendation=data["personal_recommendation"],
                reason=data["reason"],
                suggested_action=data.get("suggested_action", {}),
                confidence=data.get("confidence", 0.0),
                notification=data.get("notification", {}),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to portfolio match: %s", exc)
            return None

    def get_scenarios(
        self,
        asset: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Obtiene escenarios probabilísticos para un activo."""
        try:
            resp = httpx.get(
                f"{self._base_url}/v1/intelligence/scenarios/{asset}",
                headers=self._headers(),
                params={"limit": limit},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("scenarios", [])
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to get scenarios: %s", exc)
            return []

    def get_reports(
        self,
        asset: str,
        report_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Obtiene reportes periódicos de un activo."""
        params: dict[str, Any] = {"limit": limit}
        if report_type:
            params["report_type"] = report_type
        try:
            resp = httpx.get(
                f"{self._base_url}/v1/intelligence/reports/{asset}",
                headers=self._headers(),
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("reports", [])
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to get reports: %s", exc)
            return []

    def get_scheduler_status(self) -> dict[str, Any] | None:
        """Obtiene el estado del scheduler remoto."""
        try:
            resp = httpx.get(
                f"{self._base_url}/v1/intelligence/scheduler/status",
                headers=self._headers(),
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to get scheduler status: %s", exc)
            return None


def create_intelligence_provider(settings: Any) -> IntelligenceProvider | None:
    """Factory que crea un IntelligenceProvider desde la configuración.

    Returns None si USE_INTELLIGENCE_API=False o REMOTE_AI_URL no está configurado.
    """
    if not getattr(settings, "USE_INTELLIGENCE_API", False):
        return None
    url = getattr(settings, "REMOTE_AI_URL", None)
    if not url:
        logger.warning("USE_INTELLIGENCE_API=True but REMOTE_AI_URL not set")
        return None
    token = getattr(settings, "REMOTE_AI_TOKEN", None)
    return IntelligenceProvider(base_url=url, token=token)

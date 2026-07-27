"""Notification Generator + Pending Queue — Fase D.

Notification Generator: traduce decisiones técnicas a lenguaje claro usando
templates (NO usa IA). Agrupa notificaciones por relevancia.

Pending Queue: gestiona el ciclo de vida de notificaciones pendientes con
estados PENDING/DELIVERED/READ/EXPIRED/SUPERSEDED/CANCELLED.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database.models import PendingNotification

logger = logging.getLogger(__name__)

# Templates de notificaciones — sin IA
_TEMPLATES = {
    "BUY": "Oportunidad de compra en {asset}: {reason} (confianza: {confidence:.0%})",
    "BUY_PARTIAL": "Compra parcial recomendada en {asset}: {reason} (confianza: {confidence:.0%})",
    "SELL": "Venta recomendada en {asset}: {reason}",
    "SELL_FULL": "Venta total recomendada en {asset}: {reason}",
    "TAKE_PARTIAL_PROFIT": "Tomar ganancias parciales en {asset}: {reason}",
    "HOLD": "Mantener posición en {asset}: {reason}",
    "AVOID": "Evitar {asset}: {reason}",
    "WAIT": "Esperar confirmación en {asset}: {reason}",
    "crash_risk": "Alerta de riesgo de caída en {asset}: {message} (severidad: {severity})",
    "volatility": "Alerta de volatilidad en {asset}: {message}",
    "liquidity_drop": "Alerta de caída de liquidez en {asset}: {message}",
    "daily_report": "Reporte diario de {asset}: {summary}",
    "signal_invalidated": "Señal anterior de {asset} invalidada: {reason}",
}


class NotificationGenerator:
    """Genera notificaciones en lenguaje claro usando templates — sin IA."""

    def generate_from_recommendation(
        self,
        recommendation: dict[str, Any],
    ) -> dict[str, Any]:
        """Genera el contenido de una notificación desde una recomendación.

        Args:
            recommendation: dict con asset, personal_recommendation, reason, confidence.

        Returns:
            dict con title, message, type, asset.
        """
        rec_type = recommendation.get("personal_recommendation", "HOLD")
        asset = recommendation.get("asset", "")
        reason = recommendation.get("reason", "")
        confidence = recommendation.get("confidence", 0.0)

        template = _TEMPLATES.get(rec_type, _TEMPLATES["HOLD"])
        message = template.format(
            asset=asset,
            reason=reason,
            confidence=confidence,
        )

        return {
            "title": f"{rec_type.replace('_', ' ').title()} — {asset}",
            "message": message,
            "type": "recommendation",
            "asset": asset,
            "recommendation": rec_type,
            "suggested_action": recommendation.get("suggested_action", {}),
        }

    def generate_from_alert(
        self,
        alert: dict[str, Any],
    ) -> dict[str, Any]:
        """Genera notificación desde una alerta de mercado."""
        alert_type = alert.get("alert_type", "volatility")
        asset = alert.get("asset", "")
        message = alert.get("message", "")
        severity = alert.get("severity", "medium")

        template = _TEMPLATES.get(alert_type, _TEMPLATES["volatility"])
        formatted = template.format(
            asset=asset, message=message, severity=severity,
        )

        return {
            "title": f"Alerta — {asset}",
            "message": formatted,
            "type": "alert",
            "asset": asset,
            "severity": severity,
        }

    def generate_from_signal(
        self,
        signal: dict[str, Any],
    ) -> dict[str, Any]:
        """Genera notificación desde una señal global."""
        asset = signal.get("asset", "")
        decision = signal.get("decision", "NO_ACTION")
        confidence = signal.get("confidence", 0.0)
        reasons = signal.get("main_reasons", [])

        reason_text = "; ".join(reasons[:3]) if reasons else "Análisis de consenso"
        message = f"Nueva señal para {asset}: {decision} (confianza: {confidence:.0%}). {reason_text}"

        return {
            "title": f"Señal — {asset}",
            "message": message,
            "type": "signal",
            "asset": asset,
            "decision": decision,
            "confidence": confidence,
        }

    def generate_invalidation(
        self,
        asset: str,
        reason: str,
    ) -> dict[str, Any]:
        """Genera notificación de invalidación de señal."""
        template = _TEMPLATES["signal_invalidated"]
        message = template.format(asset=asset, reason=reason)
        return {
            "title": f"Señal invalidada — {asset}",
            "message": message,
            "type": "invalidation",
            "asset": asset,
            "reason": reason,
        }


class PendingQueue:
    """Gestiona el ciclo de vida de notificaciones pendientes."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_notification(
        self,
        user_id_hash: str,
        notification_type: str,
        content: dict[str, Any],
        asset: str = "",
        expires_at: datetime | None = None,
        supersedes_id: int | None = None,
    ) -> PendingNotification:
        """Añade una notificación pendiente.

        Si supersedes_id está set, marca la notificación anterior como SUPERSEDED.
        """
        # Marcar notificación anterior como SUPERSEDED
        if supersedes_id is not None:
            self.session.execute(
                update(PendingNotification)
                .where(PendingNotification.id == supersedes_id)
                .values(status="SUPERSEDED")
            )

        # Auto-supersede: marcar notificaciones PENDING anteriores del mismo tipo+asset
        existing = self.session.execute(
            select(PendingNotification)
            .where(
                PendingNotification.user_id_hash == user_id_hash,
                PendingNotification.status == "PENDING",
                PendingNotification.notification_type == notification_type,
                PendingNotification.asset == asset,
            )
        ).scalars().all()

        for old_notif in existing:
            old_notif.status = "SUPERSEDED"

        if expires_at is None:
            expires_at = datetime.now(UTC) + timedelta(hours=48)

        notif = PendingNotification(
            user_id_hash=user_id_hash,
            notification_type=notification_type,
            asset=asset,
            content=content,
            status="PENDING",
            expires_at=expires_at,
            supersedes_id=supersedes_id,
        )
        self.session.add(notif)
        self.session.commit()
        return notif

    def get_pending(
        self,
        user_id_hash: str,
        limit: int = 50,
    ) -> list[PendingNotification]:
        """Obtiene notificaciones pendientes de un usuario."""
        result = self.session.execute(
            select(PendingNotification)
            .where(
                PendingNotification.user_id_hash == user_id_hash,
                PendingNotification.status == "PENDING",
            )
            .order_by(PendingNotification.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def mark_delivered(self, notification_id: int) -> bool:
        """Marca una notificación como entregada."""
        notif = self.session.get(PendingNotification, notification_id)
        if notif is None or notif.status != "PENDING":
            return False
        notif.status = "DELIVERED"
        notif.delivered_at = datetime.now(UTC)
        self.session.commit()
        return True

    def mark_read(self, notification_id: int) -> bool:
        """Marca una notificación como leída."""
        notif = self.session.get(PendingNotification, notification_id)
        if notif is None:
            return False
        if notif.status not in ("PENDING", "DELIVERED"):
            return False
        notif.status = "READ"
        notif.read_at = datetime.now(UTC)
        self.session.commit()
        return True

    def expire_stale(self) -> int:
        """Marca como EXPIRED las notificaciones PENDING/DELIVERED que pasaron expires_at."""
        now = datetime.now(UTC)
        result = self.session.execute(
            update(PendingNotification)
            .where(
                PendingNotification.status.in_(["PENDING", "DELIVERED"]),
                PendingNotification.expires_at < now,
            )
            .values(status="EXPIRED")
        )
        self.session.commit()
        return result.rowcount or 0

    def cancel(self, notification_id: int) -> bool:
        """Cancela una notificación."""
        notif = self.session.get(PendingNotification, notification_id)
        if notif is None or notif.status in ("READ", "EXPIRED", "CANCELLED"):
            return False
        notif.status = "CANCELLED"
        self.session.commit()
        return True

    def get_pending_summary(
        self,
        user_id_hash: str,
    ) -> dict[str, int]:
        """Resume notificaciones pendientes por tipo."""
        pending = self.get_pending(user_id_hash)
        summary: dict[str, int] = {}
        for notif in pending:
            notif_type = notif.notification_type
            summary[notif_type] = summary.get(notif_type, 0) + 1
        return summary

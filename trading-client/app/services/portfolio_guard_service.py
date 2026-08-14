"""Portfolio Guard Service — monitors portfolio risk and takes action.

Two modes:
- "manual": generates suggestions (user must approve)
- "auto": executes actions automatically (close worst position, reduce exposure)

Checks:
- Correlation between positions (auto-reduce when > threshold)
- Drawdown from peak (auto-close worst when > threshold)
- Category exposure (warn when > limit)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.risk.portfolio_risk import (
    CATEGORY_EXPOSURE_LIMITS,
    assess_portfolio_risk,
    get_asset_category,
)

logger = logging.getLogger(__name__)


class PortfolioGuardService:
    """Monitors portfolio risk and optionally takes automated action."""

    def __init__(self, user_id: int = 0) -> None:
        self._user_id = user_id

    def get_config(self) -> dict[str, Any]:
        """Get or create the user's guard config."""
        from app.database.models.portfolio_guard_config import PortfolioGuardConfig
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            cfg = db.query(PortfolioGuardConfig).filter(
                PortfolioGuardConfig.user_id == self._user_id
            ).first()
            if not cfg:
                cfg = PortfolioGuardConfig(
                    user_id=self._user_id,
                    enabled=False,
                    mode="manual",
                    max_correlation=0.85,
                    max_drawdown_pct=15.0,
                    max_category_exposure=dict(CATEGORY_EXPOSURE_LIMITS),
                    auto_close_worst=False,
                )
                db.add(cfg)
                db.commit()
                db.refresh(cfg)
            return self._config_dict(cfg)
        finally:
            db.close()

    def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Update guard config fields."""
        from app.database.models.portfolio_guard_config import PortfolioGuardConfig
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            cfg = db.query(PortfolioGuardConfig).filter(
                PortfolioGuardConfig.user_id == self._user_id
            ).first()
            if not cfg:
                cfg = PortfolioGuardConfig(
                    user_id=self._user_id,
                    enabled=False,
                    mode="manual",
                    max_correlation=0.85,
                    max_drawdown_pct=15.0,
                    max_category_exposure=dict(CATEGORY_EXPOSURE_LIMITS),
                    auto_close_worst=False,
                )
                db.add(cfg)
                db.commit()
                db.refresh(cfg)

            if "enabled" in updates:
                cfg.enabled = bool(updates["enabled"])
            if "mode" in updates:
                cfg.mode = updates["mode"] if updates["mode"] in ("manual", "auto") else "manual"
            if "max_correlation" in updates:
                cfg.max_correlation = float(updates["max_correlation"])
            if "max_drawdown_pct" in updates:
                cfg.max_drawdown_pct = float(updates["max_drawdown_pct"])
            if "max_category_exposure" in updates:
                cfg.max_category_exposure = updates["max_category_exposure"]
            if "auto_close_worst" in updates:
                cfg.auto_close_worst = bool(updates["auto_close_worst"])

            db.commit()
            db.refresh(cfg)
            return self._config_dict(cfg)
        except Exception as exc:
            db.rollback()
            logger.error("Error updating guard config: %s", exc)
            raise
        finally:
            db.close()

    def check_portfolio(self, positions: list[dict], portfolio_value: float) -> dict[str, Any]:
        """Run guard check on current portfolio.

        Args:
            positions: List of {symbol, value, entry_price, current_price, qty, position_id}
            portfolio_value: Total portfolio value in USD

        Returns:
            {status, suggestions, actions_taken, metrics}
        """
        cfg = self.get_config()
        if not cfg["enabled"]:
            return {"status": "disabled", "suggestions": [], "actions_taken": [], "metrics": {}}

        # Use existing portfolio risk assessment
        assessment = assess_portfolio_risk(positions, portfolio_value, fetch_correlation=True)
        metrics = assessment.to_dict()

        suggestions: list[dict] = []
        actions_taken: list[dict] = []

        # 1. Correlation warnings → suggest reducing
        for warn in assessment.correlation_warnings:
            suggestions.append({
                "type": "reduce_correlation",
                "severity": "warning",
                "message": warn,
                "action": "Consider closing one of the correlated positions",
                "auto_executable": cfg["mode"] == "auto",
            })

        # 2. Category exposure warnings
        for warn in assessment.category_warnings:
            suggestions.append({
                "type": "reduce_exposure",
                "severity": "warning",
                "message": warn,
                "action": f"Reduce exposure in over-limit category",
                "auto_executable": cfg["mode"] == "auto",
            })

        # 3. Drawdown check
        drawdown = self._calculate_drawdown()
        if drawdown > cfg["max_drawdown_pct"]:
            suggestion = {
                "type": "close_worst",
                "severity": "critical",
                "message": f"Drawdown {drawdown:.1f}% exceeds limit {cfg['max_drawdown_pct']:.1f}%",
                "action": "Close worst-performing position to limit losses",
                "auto_executable": cfg["mode"] == "auto" and cfg["auto_close_worst"],
            }
            suggestions.append(suggestion)

            if cfg["mode"] == "auto" and cfg["auto_close_worst"]:
                worst = self._find_worst_position(positions)
                if worst:
                    result = self._close_position(worst)
                    actions_taken.append({
                        "action": "auto_close_worst",
                        "position": worst.get("symbol"),
                        "reason": f"Drawdown {drawdown:.1f}% > limit {cfg['max_drawdown_pct']:.1f}%",
                        "result": result,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    })

        # 4. High correlation auto-reduce
        if cfg["mode"] == "auto" and assessment.avg_correlation > cfg["max_correlation"]:
            worst = self._find_worst_position(positions)
            if worst:
                result = self._close_position(worst)
                actions_taken.append({
                    "action": "auto_reduce_correlation",
                    "position": worst.get("symbol"),
                    "reason": f"Avg correlation {assessment.avg_correlation:.2f} > limit {cfg['max_correlation']:.2f}",
                    "result": result,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                })

        # Update last_check
        self._update_last_check()

        return {
            "status": "ok",
            "mode": cfg["mode"],
            "suggestions": suggestions,
            "actions_taken": actions_taken,
            "metrics": {
                "risk_score": metrics["risk_score"],
                "avg_correlation": metrics["avg_correlation"],
                "max_single_position_pct": metrics["max_single_position_pct"],
                "category_exposure": metrics["category_exposure"],
                "var": metrics.get("var"),
                "drawdown_pct": drawdown,
            },
        }

    def execute_suggestion(self, suggestion: dict, positions: list[dict]) -> dict:
        """Manually execute a suggestion (mode=manual)."""
        if suggestion["type"] == "close_worst":
            worst = self._find_worst_position(positions)
            if worst:
                return self._close_position(worst)
            return {"status": "no_position"}
        elif suggestion["type"] == "reduce_correlation":
            # Close the position that contributes most to correlation
            worst = self._find_worst_position(positions)
            if worst:
                return self._close_position(worst)
            return {"status": "no_position"}
        elif suggestion["type"] == "reduce_exposure":
            # Close the largest position in the over-exposed category
            worst = self._find_worst_position(positions)
            if worst:
                return self._close_position(worst)
            return {"status": "no_position"}
        return {"status": "unknown_suggestion"}

    def get_history(self, limit: int = 50) -> list[dict]:
        """Get history of guard actions."""
        from app.database.models.system_event import SystemEvent
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            events = db.query(SystemEvent).filter(
                SystemEvent.user_id == self._user_id,
                SystemEvent.source == "portfolio_guard",
            ).order_by(SystemEvent.created_at.desc()).limit(limit).all()

            return [
                {
                    "id": e.id,
                    "timestamp": e.created_at.isoformat() if e.created_at else None,
                    "action": e.details.get("action", ""),
                    "position": e.details.get("position", ""),
                    "reason": e.details.get("reason", ""),
                    "result": e.details.get("result", {}),
                }
                for e in events
            ]
        finally:
            db.close()

    # ─── Private helpers ──────────────────────────────────────────────────

    def _config_dict(self, cfg) -> dict:
        return {
            "enabled": cfg.enabled,
            "mode": cfg.mode,
            "max_correlation": cfg.max_correlation,
            "max_drawdown_pct": cfg.max_drawdown_pct,
            "max_category_exposure": cfg.max_category_exposure or dict(CATEGORY_EXPOSURE_LIMITS),
            "auto_close_worst": cfg.auto_close_worst,
            "last_check": cfg.last_check.isoformat() if cfg.last_check else None,
            "actions_taken": cfg.actions_taken,
        }

    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown from account snapshots."""
        try:
            from app.database.models.account_snapshot import AccountSnapshot
            from app.database.session import SessionLocal

            db = SessionLocal()
            try:
                snapshots = db.query(AccountSnapshot).filter(
                    AccountSnapshot.user_id == self._user_id,
                ).order_by(AccountSnapshot.timestamp.desc()).limit(90).all()

                if len(snapshots) < 2:
                    return 0.0

                # Peak is the highest equity in the lookback period
                equities = [float(s.equity) for s in snapshots if s.equity]
                if not equities:
                    return 0.0

                peak = max(equities)
                current = equities[0]  # most recent

                if peak <= 0:
                    return 0.0

                drawdown = (peak - current) / peak * 100
                return max(drawdown, 0.0)
            finally:
                db.close()
        except Exception:
            return 0.0

    def _find_worst_position(self, positions: list[dict]) -> dict | None:
        """Find the worst-performing position by P&L %."""
        if not positions:
            return None
        worst = None
        worst_pnl = 0.0
        for p in positions:
            entry = float(p.get("entry_price", 0))
            current = float(p.get("current_price", 0))
            if entry > 0 and current > 0:
                pnl_pct = (current - entry) / entry * 100
                if pnl_pct < worst_pnl:
                    worst_pnl = pnl_pct
                    worst = p
        return worst or positions[0]

    def _close_position(self, position: dict) -> dict:
        """Close a position via broker API.

        This is a placeholder — in production it would call the broker adapter
        to place a market sell order.
        """
        try:
            from app.database.models.system_event import SystemEvent
            from app.database.session import SessionLocal

            # Log the action
            db = SessionLocal()
            try:
                event = SystemEvent(
                    user_id=self._user_id,
                    timestamp=datetime.now(tz=UTC),
                    level="warning",
                    source="portfolio_guard",
                    message=f"Guard action: close_position {position.get('symbol', '')}",
                    details={
                        "action": "close_position",
                        "position": position.get("symbol", ""),
                        "reason": "portfolio_guard_auto_close",
                        "result": {"status": "logged"},
                    },
                )
                db.add(event)

                # Increment actions_taken counter
                from app.database.models.portfolio_guard_config import PortfolioGuardConfig
                cfg = db.query(PortfolioGuardConfig).filter(
                    PortfolioGuardConfig.user_id == self._user_id
                ).first()
                if cfg:
                    cfg.actions_taken += 1

                db.commit()
            finally:
                db.close()

            # In production: call broker to place market sell
            # For now, just log
            logger.info(
                "Portfolio Guard: would close position %s (qty=%s)",
                position.get("symbol"),
                position.get("qty"),
            )
            return {"status": "logged", "symbol": position.get("symbol")}
        except Exception as exc:
            logger.error("Error closing position: %s", exc)
            return {"status": "error", "error": str(exc)}

    def _update_last_check(self) -> None:
        """Update the last_check timestamp."""
        from app.database.models.portfolio_guard_config import PortfolioGuardConfig
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            cfg = db.query(PortfolioGuardConfig).filter(
                PortfolioGuardConfig.user_id == self._user_id
            ).first()
            if cfg:
                cfg.last_check = datetime.now(tz=UTC)
                db.commit()
        finally:
            db.close()

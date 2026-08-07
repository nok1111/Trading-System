"""Performance Learner — evalúa predicciones pasadas y genera insights para la IA.

Hace dos cosas:
1. Auto-evaluación: predicciones >24h se marcan correct/incorrect según precio forward
2. Generación de insights: calcula win rate por factor, identifica patrones, genera texto para inyectar en el system prompt

Inspirado en Chaos366273/RL-Trading-System (regime controller + reward scaling)
y ItzSwapnil/DART (self-adaptive learning + uncertainty quantification).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


class PerformanceLearner:
    """Servicio que evalúa predicciones pasadas y genera insights de aprendizaje."""

    def __init__(self, user_id: int = 0) -> None:
        self._user_id = user_id

    def evaluate_pending_predictions(self) -> dict:
        """Evaluate predictions that are past their forward window.

        For each unevaluated prediction:
        - Get current price of the symbol
        - Compare to price_at_prediction
        - Mark correct if direction matches signal_type
        - Store result in prediction_records
        """
        from app.database.models.prediction_record import PredictionRecord
        from app.database.session import SessionLocal

        session = SessionLocal()
        evaluated_count = 0
        try:
            # Get unevaluated predictions older than their forward window
            cutoff = datetime.now(tz=UTC) - timedelta(hours=24)
            records = session.query(PredictionRecord).filter(
                PredictionRecord.user_id == self._user_id,
                PredictionRecord.evaluated == False,  # noqa: E712
                PredictionRecord.timestamp < cutoff,
                PredictionRecord.metadata_json["source"].astext == "ai_agent",
            ).limit(50).all()

            for record in records:
                try:
                    current_price = self._get_current_price(record.symbol)
                    if current_price is None or current_price <= 0:
                        continue

                    pred_price = float(record.price_at_prediction)
                    if pred_price <= 0:
                        continue

                    # Determine actual direction
                    if current_price > pred_price * 1.001:  # >0.1% up
                        actual_direction = "UP"
                    elif current_price < pred_price * 0.999:  # >0.1% down
                        actual_direction = "DOWN"
                    else:
                        actual_direction = "FLAT"

                    # For BUY predictions: correct if UP
                    # For SELL/SHORT predictions: correct if DOWN
                    signal = record.signal_type.upper()
                    if signal == "BUY":
                        correct = actual_direction == "UP"
                    elif signal in ("SELL", "SHORT"):
                        correct = actual_direction == "DOWN"
                    else:
                        correct = actual_direction == "FLAT"

                    record.evaluated = True
                    record.actual_direction = actual_direction
                    record.correct = correct
                    record.price_at_evaluation = Decimal(str(current_price))
                    record.evaluated_at = datetime.now(tz=UTC)
                    evaluated_count += 1

                except Exception as exc:
                    logger.warning(f"Error evaluating prediction {record.id}: {exc}")
                    continue

            session.commit()
            return {"evaluated": evaluated_count, "status": "ok"}
        except Exception as exc:
            session.rollback()
            logger.error(f"Error in evaluate_pending_predictions: {exc}")
            return {"evaluated": 0, "status": "error", "error": str(exc)}
        finally:
            session.close()

    def _get_current_price(self, symbol: str) -> float | None:
        """Get current price for a symbol via internal API."""
        try:
            # Try to get price from price stream
            from app.data.price_stream import get_price_stream
            stream = get_price_stream()
            if stream and stream.is_connected:
                price = stream.get_price(symbol)
                if price and price > 0:
                    return float(price)
        except Exception:
            pass

        # Fallback: try Binance API directly
        try:
            import httpx
            # Convert CCXT format (BTC/USDT) to Binance format (BTCUSDT)
            binance_symbol = symbol.replace("/", "").upper()
            resp = httpx.get(
                f"https://api.binance.com/api/v3/ticker/price",
                params={"symbol": binance_symbol},
                timeout=10,
            )
            resp.raise_for_status()
            return float(resp.json()["price"])
        except Exception:
            return None

    def get_learning_insights(self) -> dict[str, Any]:
        """Generate learning insights from evaluated predictions.

        Returns:
        - factor_stats: win rate by factor value
        - best_factors: factors with highest win rate (>65%)
        - worst_factors: factors with lowest win rate (<40%)
        - recommendations: text insights for the AI prompt
        - weekly_evolution: win rate by week
        - summary: overall stats
        """
        from app.database.models.prediction_record import PredictionRecord
        from app.database.session import SessionLocal

        session = SessionLocal()
        try:
            records = session.query(PredictionRecord).filter(
                PredictionRecord.user_id == self._user_id,
                PredictionRecord.evaluated == True,  # noqa: E712
                PredictionRecord.metadata_json["source"].astext == "ai_agent",
            ).order_by(PredictionRecord.timestamp.desc()).limit(500).all()

            if len(records) < 5:
                return {
                    "status": "insufficient_data",
                    "total": len(records),
                    "message": "Necesita más operaciones evaluadas para generar insights",
                }

            # ─── 1. Factor stats ───
            factor_stats: dict[str, dict[str, int]] = {}
            for r in records:
                factors = (r.metadata_json or {}).get("factors", {})
                if r.correct is None:
                    continue
                for fkey, fval in factors.items():
                    if fval is None or fkey in ("reason", "confidence", "sl_pct", "tp_pct"):
                        continue
                    bucket = str(fval)[:20]
                    key = f"{fkey}={bucket}"
                    if key not in factor_stats:
                        factor_stats[key] = {"wins": 0, "losses": 0}
                    if r.correct:
                        factor_stats[key]["wins"] += 1
                    else:
                        factor_stats[key]["losses"] += 1

            # Calculate win rates
            factor_results = {}
            for key, stats in factor_stats.items():
                total = stats["wins"] + stats["losses"]
                if total >= 3:
                    factor_results[key] = {
                        "win_rate": round(stats["wins"] / total, 3),
                        "total": total,
                        "wins": stats["wins"],
                        "losses": stats["losses"],
                    }

            # Sort by win rate
            sorted_factors = dict(sorted(factor_results.items(), key=lambda x: x[1]["win_rate"], reverse=True))

            # ─── 2. Best and worst factors ───
            best_factors = {k: v for k, v in sorted_factors.items() if v["win_rate"] >= 0.65}
            worst_factors = {k: v for k, v in sorted_factors.items() if v["win_rate"] <= 0.40}

            # ─── 3. Weekly evolution ───
            weekly_stats: dict[str, dict[str, int]] = {}
            for r in records:
                if r.correct is None or r.evaluated_at is None:
                    continue
                week_key = r.evaluated_at.strftime("%Y-W%U")
                if week_key not in weekly_stats:
                    weekly_stats[week_key] = {"wins": 0, "losses": 0}
                if r.correct:
                    weekly_stats[week_key]["wins"] += 1
                else:
                    weekly_stats[week_key]["losses"] += 1

            weekly_evolution = []
            for week, stats in sorted(weekly_stats.items()):
                total = stats["wins"] + stats["losses"]
                if total > 0:
                    weekly_evolution.append({
                        "week": week,
                        "win_rate": round(stats["wins"] / total, 3),
                        "total": total,
                    })

            # ─── 4. Overall summary ───
            total_evaluated = len(records)
            total_correct = sum(1 for r in records if r.correct is True)
            overall_win_rate = total_correct / total_evaluated if total_evaluated > 0 else 0

            # ─── 5. Generate recommendations text ───
            recommendations = self._generate_recommendations(best_factors, worst_factors, overall_win_rate)

            return {
                "status": "ok",
                "total_records": total_evaluated,
                "overall_win_rate": round(overall_win_rate, 3),
                "total_correct": total_correct,
                "factors": sorted_factors,
                "best_factors": best_factors,
                "worst_factors": worst_factors,
                "weekly_evolution": weekly_evolution,
                "recommendations": recommendations,
            }
        except Exception as exc:
            logger.error(f"Error in get_learning_insights: {exc}")
            return {"status": "error", "error": str(exc)}
        finally:
            session.close()

    def _generate_recommendations(self, best: dict, worst: dict, overall_wr: float) -> list[str]:
        """Generate natural language recommendations for the AI prompt."""
        recs = []

        if overall_wr < 0.40:
            recs.append(f"⚠️ Tu win rate general es {overall_wr:.0%} — considera ser más selectivo, aumentar confidence mínimo a 0.7.")
        elif overall_wr > 0.60:
            recs.append(f"✅ Tu win rate general es {overall_wr:.0%} — buen desempeño, mantén la estrategia actual.")

        for factor, stats in list(best.items())[:3]:
            recs.append(f"✅ Factor exitoso: {factor} → {stats['win_rate']:.0%} win rate ({stats['total']} muestras). Prioriza señales con este factor.")

        for factor, stats in list(worst.items())[:3]:
            recs.append(f"❌ Factor perdedor: {factor} → {stats['win_rate']:.0%} win rate ({stats['total']} muestras). Evita señales con este factor o reduce confidence.")

        if not recs:
            recs.append("Aún no hay suficientes datos para generar recomendaciones. Sigue operando para acumular historial.")

        return recs

    def get_prompt_insights(self) -> str:
        """Generate a text block to inject into the system prompt.

        This is what the AI reads each cycle to learn from past performance.
        """
        insights = self.get_learning_insights()
        if insights.get("status") != "ok":
            return ""

        lines = ["\n\nLEARNING FROM PAST PERFORMANCE (datos reales de tus operaciones):"]
        lines.append(f"Win rate general: {insights['overall_win_rate']:.0%} ({insights['total_correct']}/{insights['total_records']} operaciones)")

        best = insights.get("best_factors", {})
        if best:
            lines.append("\nFACTORES QUE FUNCIONARON (prioriza señales con estos):")
            for factor, stats in list(best.items())[:5]:
                lines.append(f"  ✅ {factor}: {stats['win_rate']:.0%} win rate ({stats['total']} ops)")

        worst = insights.get("worst_factors", {})
        if worst:
            lines.append("\nFACTORES QUE FALLARON (evita o reduce confidence):")
            for factor, stats in list(worst.items())[:5]:
                lines.append(f"  ❌ {factor}: {stats['win_rate']:.0%} win rate ({stats['total']} ops)")

        recs = insights.get("recommendations", [])
        if recs:
            lines.append("\nRECOMENDACIONES:")
            for rec in recs:
                lines.append(f"  {rec}")

        return "\n".join(lines) + "\n"

    def get_confidence_adjustment(self, factors: dict) -> float:
        """Calculate confidence adjustment based on factor history.

        Returns a delta to add/subtract from the action's confidence.
        - If factors have historically high win rate → +0.05 to +0.15
        - If factors have historically low win rate → -0.05 to -0.15
        - If no data → 0.0
        """
        insights = self.get_learning_insights()
        if insights.get("status") != "ok":
            return 0.0

        best = insights.get("best_factors", {})
        worst = insights.get("worst_factors", {})

        adjustment = 0.0

        # Check if current factors match any best/worst patterns
        for fkey, fval in factors.items():
            if fval is None or fkey in ("reason", "confidence", "sl_pct", "tp_pct"):
                continue
            bucket = str(fval)[:20]
            key = f"{fkey}={bucket}"

            if key in best:
                wr = best[key]["win_rate"]
                # Boost: up to +0.15 for 100% win rate
                boost = (wr - 0.65) / (1.0 - 0.65) * 0.15
                adjustment += boost
            elif key in worst:
                wr = worst[key]["win_rate"]
                # Penalty: up to -0.15 for 0% win rate
                penalty = (0.40 - wr) / 0.40 * 0.15
                adjustment -= penalty

        # Clamp to reasonable range
        return max(-0.20, min(0.20, adjustment))

from datetime import datetime

from sqlalchemy import JSON, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AIRecommendation(Base):
    """Recomendación del AI Agent cuando auto_trade=false.

    Se guarda para que el usuario la vea en la pestaña Reportes
    y pueda decidir manualmente si ejecutar o no.
    """

    __tablename__ = "ai_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False, default=func.now())
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)  # BUY, SELL, HOLD
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0)
    reason: Mapped[str | None] = mapped_column(nullable=True)
    stop_loss_pct: Mapped[float | None] = mapped_column(nullable=True)
    take_profit_pct: Mapped[float | None] = mapped_column(nullable=True)
    market_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    personal_recommendation: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending, executed, dismissed
    trading_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="paper")  # paper, live
    broker_name: Mapped[str | None] = mapped_column(String(30), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), server_default=func.now())

    __table_args__ = (
        Index("ix_ai_recs_timestamp", "timestamp"),
        Index("ix_ai_recs_asset", "asset"),
        Index("ix_ai_recs_status", "status"),
    )

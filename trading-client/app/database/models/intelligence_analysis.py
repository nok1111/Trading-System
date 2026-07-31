"""Intelligence Analysis model — stores AI analysis snapshots per asset historically.

Like Binance klines store price history, this table stores AI analysis history
per asset so that assigned AI agents always have access to prior analysis
without re-computing from scratch or spending tokens.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class IntelligenceAnalysis(Base):
    """Historical AI analysis snapshot for a specific asset.

    Each record is a point-in-time analysis produced by the AI agents,
    storing the decision, confidence, reasons, risks, and key metrics.
    Agents can query prior analyses to maintain continuity and trend tracking.
    """

    __tablename__ = "intelligence_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    # BTC, ETH, SOL, etc.
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    # BUY, SELL, HOLD, BUY_ON_PULLBACK, WAIT
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0"))
    # 0.0 to 1.0
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # low, medium, high

    # Price at time of analysis
    price_usd: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)

    # Structured data
    reasons: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"technical": "...", "onchain": "...", "news": "...", "macro": "...", "contrarian": "..."}
    risks: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"key_risks": [...], "invalidation_level": 100900}
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"rsi": 62, "fear_greed": 82, "funding": 0.012, "dominance": 54.3}

    # Agent voting / consensus
    agent_votes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"Technical": "BUY", "News": "BUY", "On-chain": "HOLD", "Contrarian": "SELL", "Macro": "NEUTRAL"}

    # Entry/exit suggestions (optional)
    entry_range: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"low": 102400, "high": 103100}
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(19, 8), nullable=True)

    # Timestamps
    analyzed_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # When this analysis becomes stale

    __table_args__ = (
        Index("ix_intel_analysis_asset", "asset"),
        Index("ix_intel_analysis_decision", "decision"),
        Index("ix_intel_analysis_analyzed", "analyzed_at"),
        Index("ix_intel_analysis_asset_time", "asset", "analyzed_at"),
    )

"""Modelo de reconciliación de órdenes — Fase 6.

Registra discrepancias entre el estado interno y el estado real en el broker.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class OrderReconciliation(Base):
    """Registro de reconciliación entre estado interno y broker."""

    __tablename__ = "order_reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), nullable=False,
    )
    broker_status: Mapped[str] = mapped_column(String(20), nullable=False)
    internal_status: Mapped[str] = mapped_column(String(20), nullable=False)
    diff: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    timestamp: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_order_reconciliations_order_id", "order_id"),
        Index("ix_order_reconciliations_timestamp", "timestamp"),
    )

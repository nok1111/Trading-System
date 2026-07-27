"""Broker account model — stores encrypted credentials per broker account in local SQLite."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class BrokerAccount(Base):
    """Per-user broker account with encrypted credentials.

    Credentials are encrypted with Fernet (see app.services.crypto).
    No plaintext keys are ever stored.
    The API response never includes encrypted fields — only safe metadata.
    """

    __tablename__ = "broker_accounts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    broker_id: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    api_key_enc: Mapped[str] = mapped_column(Text, nullable=False)
    api_secret_enc: Mapped[str] = mapped_column(Text, nullable=False)
    passphrase_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str] = mapped_column(String(20), default="live", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending_validation", nullable=False)
    permissions_read: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    permissions_trade: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    permissions_withdraw: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

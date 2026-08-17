"""AlvoraConversation model — chat conversations with the Alvora advisor agent."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AlvoraConversation(Base):
    """A chat conversation with Alvora (the advisor agent).

    A user can have multiple conversations. Each conversation holds
    a message history and an auto-generated title.
    """

    __tablename__ = "alvora_conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Nueva conversacion")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_alvora_conv_user_updated", "user_id", "updated_at"),
    )

"""AlvoraMessage model — individual messages in an Alvora chat conversation."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AlvoraMessage(Base):
    """A single message in an Alvora conversation.

    role: "user" | "assistant"
    content: the message text (with action markers stripped from assistant messages)
    actions_json: list of parsed action proposals (only for assistant messages)
    """

    __tablename__ = "alvora_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alvora_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_alvora_msg_conv_created", "conversation_id", "created_at"),
    )

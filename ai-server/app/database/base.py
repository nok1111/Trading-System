"""Base declarativa para SQLAlchemy 2.0 — ai-server Market Knowledge Base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa compartida por todos los modelos del ai-server."""

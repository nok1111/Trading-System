"""Base declarativa para SQLAlchemy 2.0."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa compartida por todos los modelos de datos."""

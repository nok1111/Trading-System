"""Gestión de sesiones y motor de base de datos — ai-server.

Supports both SQLite (dev) and PostgreSQL (prod) via DATABASE_URL.
- SQLite: sqlite:///./data/ai_server.db
- PostgreSQL: postgresql://user:pass@host:5432/dbname
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from app.config import get_settings

settings = get_settings()

_connect_args = {}
_pool_kwargs = {}

if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"timeout": 30, "check_same_thread": False}
    _pool_kwargs = {"poolclass": NullPool}
elif settings.DATABASE_URL.startswith("postgresql"):
    _pool_kwargs = {
        "poolclass": QueuePool,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    }

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args,
    **_pool_kwargs,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Generador de sesiones para inyección de dependencias."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

# Forzamos una base de datos de prueba aislada antes de importar app
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("TRADING_MODE", "backtest")
os.environ.setdefault("LIVE_TRADING_ENABLED", "false")
os.environ.setdefault("BROKER_PROVIDER", "mock")

from app.config import Settings  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.models import *  # noqa: F401, F403, E402
from app.database.session import engine as session_local_engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_session_local_tables():
    """Ensure tables exist on the SessionLocal engine for tests that use it directly."""
    Base.metadata.create_all(bind=session_local_engine)
    yield
    Base.metadata.drop_all(bind=session_local_engine)


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Configuración de pruebas recargada."""
    return Settings(
        _env_file=None,
        APP_ENV="testing",
        DATABASE_URL=os.environ["DATABASE_URL"],
        TRADING_MODE="backtest",
        LIVE_TRADING_ENABLED=False,
        BROKER_PROVIDER="mock",
    )


def _clean_sqlite_file(url: str) -> None:
    """Elimina archivo SQLite previo para evitar conflictos de índices."""
    import time

    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "")
        file_path = Path(path)
        if file_path.exists():
            for _ in range(5):
                try:
                    file_path.unlink(missing_ok=True)
                    break
                except PermissionError:
                    time.sleep(0.2)


@pytest.fixture(scope="session")
def engine_fixture(settings: Settings) -> Engine:
    """Motor SQLAlchemy para las pruebas."""
    _clean_sqlite_file(settings.DATABASE_URL)
    engine = create_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine_fixture: Engine) -> Generator[Session, None, None]:
    """Sesión aislada por test con rollback al finalizar."""
    connection = engine_fixture.connect()
    transaction = connection.begin_nested()
    session = Session(bind=connection, autoflush=False, autocommit=False)

    yield session

    session.close()
    transaction.rollback()
    connection.close()

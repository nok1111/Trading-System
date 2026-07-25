#!/usr/bin/env python3
"""Script auxiliar para inicializar las tablas sin pasar por Alembic."""

from app.database.base import Base
from app.database.session import engine
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    logger.info(
        "database_initialized_via_script",
        extra={"tables": list(Base.metadata.tables.keys())},
    )
    print("Base de datos inicializada.")

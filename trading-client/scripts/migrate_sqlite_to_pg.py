"""Migrate data from SQLite to PostgreSQL.

Usage: python scripts/migrate_sqlite_to_pg.py
Run on the VPS after PostgreSQL is configured and .env points to it.
"""
import sys
import os

# Add trading-client to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from app.database.models import (
    AccountSnapshot, AIRecommendation, BacktestRun, BrokerAccount,
    MarketBar, ModelVersion, IntelligenceAnalysis, IntelligenceEvent,
    IntelligenceNews, Notification, Order, OrderReconciliation, Position,
    PriceAlert, PredictionRecord, RiskEvent, Signal, StrategyRun,
    SystemEvent, Trade, UserSettings, UserProfile,
)

SQLITE_PATH = "trading.db"
PG_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg2://trading_app:Tr4d1ngApp2026!@localhost:5432/trading_system")

# All models to migrate, in dependency order (parents first)
MODELS = [
    UserProfile,
    UserSettings,
    StrategyRun,
    Signal,
    RiskEvent,
    Position,
    Order,
    Trade,
    AccountSnapshot,
    MarketBar,
    ModelVersion,
    PredictionRecord,
    BacktestRun,
    OrderReconciliation,
    SystemEvent,
    BrokerAccount,
    AIRecommendation,
    PriceAlert,
    Notification,
    IntelligenceAnalysis,
    IntelligenceEvent,
    IntelligenceNews,
]


def migrate():
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_PATH}")
    pg_engine = create_engine(PG_URL)

    sqlite_session = sessionmaker(bind=sqlite_engine)()
    pg_session = sessionmaker(bind=pg_engine)()

    # Create all tables in PostgreSQL
    from app.database.base import Base
    import app.database.models  # noqa: F401
    Base.metadata.create_all(bind=pg_engine)

    inspector = inspect(sqlite_engine)
    total_migrated = 0

    for model in MODELS:
        table_name = model.__tablename__
        if not inspector.has_table(table_name):
            print(f"  SKIP: {table_name} (not in SQLite)")
            continue

        rows = sqlite_session.query(model).all()
        if not rows:
            print(f"  SKIP: {table_name} (empty)")
            continue

        print(f"  Migrating {table_name}: {len(rows)} rows...")
        for row in rows:
            pg_session.merge(row)
        pg_session.commit()
        total_migrated += len(rows)
        print(f"    OK: {len(rows)} rows migrated")

    sqlite_session.close()
    pg_session.close()
    print(f"\nMigration complete! Total rows migrated: {total_migrated}")


if __name__ == "__main__":
    migrate()

"""Migrate data from SQLite to PostgreSQL — raw SQL approach (column-resilient).

Usage: python scripts/migrate_sqlite_to_pg.py
Run on the VPS after PostgreSQL is configured and .env points to it.
"""
import sqlite3
import psycopg2
import os

SQLITE_PATH = os.environ.get("SQLITE_PATH", "trading.db")
PG_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg2://trading_app:Tr4d1ngApp2026!@localhost:5432/trading_system")

# Parse PG URL
pg_url_clean = PG_URL.replace("postgresql+psycopg2://", "")
pg_user_pass, pg_host_db = pg_url_clean.split("@")
pg_user, pg_pass = pg_user_pass.split(":")
pg_host, pg_db = pg_host_db.split("/")
pg_host = pg_host.split(":")[0]

# Tables to migrate in dependency order
TABLES = [
    "user_profiles",
    "user_settings",
    "strategy_runs",
    "signals",
    "risk_events",
    "positions",
    "orders",
    "trades",
    "account_snapshots",
    "market_bars",
    "model_versions",
    "prediction_records",
    "backtest_runs",
    "order_reconciliations",
    "system_events",
    "broker_accounts",
    "ai_recommendations",
    "price_alerts",
    "notifications",
    "intelligence_analyses",
    "intelligence_events",
    "intelligence_news",
]


def migrate():
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    pg_conn = psycopg2.connect(
        host=pg_host, database=pg_db, user=pg_user, password=pg_pass
    )
    pg_cur = pg_conn.cursor()

    total_migrated = 0

    for table in TABLES:
        # Check if table exists in SQLite
        sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not sqlite_cur.fetchone():
            print(f"  SKIP: {table} (not in SQLite)")
            continue

        # Get SQLite columns
        sqlite_cur.execute(f"PRAGMA table_info({table})")
        sqlite_cols = [row["name"] for row in sqlite_cur.fetchall()]

        # Get PostgreSQL columns
        pg_cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s
        """, (table,))
        pg_cols = {row[0] for row in pg_cur.fetchall()}

        if not pg_cols:
            print(f"  SKIP: {table} (not in PostgreSQL)")
            continue

        # Only migrate columns that exist in BOTH databases
        common_cols = [c for c in sqlite_cols if c in pg_cols]

        # Read all rows from SQLite
        col_list = ", ".join(common_cols)
        sqlite_cur.execute(f"SELECT {col_list} FROM {table}")
        rows = sqlite_cur.fetchall()

        if not rows:
            print(f"  SKIP: {table} (empty)")
            continue

        print(f"  Migrating {table}: {len(rows)} rows (cols: {len(common_cols)})...")

        # Build INSERT with ON CONFLICT DO NOTHING (preserve existing IDs)
        placeholders = ", ".join(["%s"] * len(common_cols))
        insert_sql = f"""
            INSERT INTO {table} ({col_list})
            VALUES ({placeholders})
            ON CONFLICT (id) DO NOTHING
        """

        for row in rows:
            values = [row[col] for col in common_cols]
            pg_cur.execute(insert_sql, values)

        pg_conn.commit()
        total_migrated += len(rows)
        print(f"    OK: {len(rows)} rows migrated")

    sqlite_conn.close()
    pg_conn.close()
    print(f"\nMigration complete! Total rows migrated: {total_migrated}")


if __name__ == "__main__":
    migrate()

"""Deploy Fase 1: pull code, install deps, migrate SQLite to PostgreSQL, restart."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

commands = [
    # Pull latest code
    "cd /opt/trading-system && git pull origin main",
    # Install psycopg2-binary
    "cd /opt/trading-system && source venv/bin/activate && pip install psycopg2-binary -q 2>&1 | tail -3",
    # Run migration script (SQLite -> PostgreSQL)
    "cd /opt/trading-system/trading-client && source /opt/trading-system/venv/bin/activate && DATABASE_URL='postgresql+psycopg2://trading_app:Tr4d1ngApp2026!@localhost:5432/trading_system' python scripts/migrate_sqlite_to_pg.py 2>&1",
    # Restart trading-system service
    "systemctl restart trading-system",
    "sleep 3",
    "systemctl is-active trading-system",
    # Health checks
    "curl -s http://localhost:8080/health",
    "curl -s http://localhost:9100/health",
    "curl -s http://localhost:8000/health",
    # Check PostgreSQL tables
    "PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -c '\\dt' 2>&1 | head -40",
    # Check row counts in key tables
    "PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -c \"SELECT 'positions' as t, count(*) FROM positions UNION ALL SELECT 'orders', count(*) FROM orders UNION ALL SELECT 'trades', count(*) FROM trades UNION ALL SELECT 'notifications', count(*) FROM notifications UNION ALL SELECT 'ai_recommendations', count(*) FROM ai_recommendations UNION ALL SELECT 'price_alerts', count(*) FROM price_alerts UNION ALL SELECT 'broker_accounts', count(*) FROM broker_accounts UNION ALL SELECT 'user_settings', count(*) FROM user_settings;\" 2>&1",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

for cmd in commands:
    print(f"\n>>> {cmd[:100]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")

ssh.close()
print("\nDone!")

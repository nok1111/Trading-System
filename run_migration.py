"""Run SQLite to PostgreSQL migration on VPS."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

commands = [
    # Pull latest code
    "cd /opt/trading-system && git pull origin main",
    # Run migration (SQLite is at trading-client/trading.db, PG is configured in .env)
    "cd /opt/trading-system/trading-client && /opt/trading-system/venv/bin/python scripts/migrate_sqlite_to_pg.py 2>&1",
    # Check row counts after migration
    "PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -c \"SELECT 'positions' as t, count(*) FROM positions UNION ALL SELECT 'orders', count(*) FROM orders UNION ALL SELECT 'trades', count(*) FROM trades UNION ALL SELECT 'notifications', count(*) FROM notifications UNION ALL SELECT 'ai_recommendations', count(*) FROM ai_recommendations UNION ALL SELECT 'price_alerts', count(*) FROM price_alerts UNION ALL SELECT 'broker_accounts', count(*) FROM broker_accounts UNION ALL SELECT 'user_profiles', count(*) FROM user_profiles UNION ALL SELECT 'user_settings', count(*) FROM user_settings UNION ALL SELECT 'signals', count(*) FROM signals;\" 2>&1",
    # Restart service to pick up migrated data
    "systemctl restart trading-system",
    "sleep 3",
    "systemctl is-active trading-system",
    "curl -s http://localhost:8080/health",
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

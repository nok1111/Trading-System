"""Fix .env loading on VPS — symlink or copy .env to trading-client dir."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

commands = [
    # Check if .env exists in trading-client
    "ls -la /opt/trading-system/trading-client/.env 2>/dev/null || echo 'NOT_FOUND'",
    # Create symlink to parent .env
    "ln -sf /opt/trading-system/.env /opt/trading-system/trading-client/.env",
    # Verify
    "ls -la /opt/trading-system/trading-client/.env",
    # Check DATABASE_URL now
    "cd /opt/trading-system/trading-client && /opt/trading-system/venv/bin/python -c \"from app.config import get_settings; s=get_settings(); print('DATABASE_URL:', s.DATABASE_URL[:50])\" 2>&1",
    # Restart service
    "systemctl restart trading-system",
    "sleep 3",
    "systemctl is-active trading-system",
    "curl -s http://localhost:8080/health",
    # Check new tables
    "PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -c \"SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('risk_configs','agent_logs','agent_sessions');\" 2>&1",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

for cmd in commands:
    print(f"\n>>> {cmd[:80]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")

ssh.close()
print("\nDone!")

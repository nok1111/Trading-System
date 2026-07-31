"""Check and fix new tables on VPS."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

commands = [
    # Check all tables
    "PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -c '\\dt' 2>&1",
    # Check startup logs for create_all
    "journalctl -u trading-system --no-pager -n 50 2>&1 | grep -i 'create\\|migrat\\|error\\|fail' | tail -10",
    # Check if the .env is loaded properly
    "cd /opt/trading-system/trading-client && /opt/trading-system/venv/bin/python -c \"from app.config import get_settings; s=get_settings(); print('DATABASE_URL:', s.DATABASE_URL[:50])\" 2>&1",
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

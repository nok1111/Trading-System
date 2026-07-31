"""Check VPS status after deploy."""
import paramiko
import time

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

# Wait for service to be ready
time.sleep(5)

commands = [
    "systemctl is-active trading-system",
    "curl -s http://localhost:8080/health",
    # Check if new tables were created
    "PGPASSWORD=Tr4d1ngApp2026! psql -U trading_app -d trading_system -c \"SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('risk_configs','agent_logs','agent_sessions');\" 2>&1",
    # Check service logs for errors
    "journalctl -u trading-system --no-pager -n 20 2>&1",
]

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

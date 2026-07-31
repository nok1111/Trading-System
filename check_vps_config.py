"""Find .env and DATABASE_URL config on VPS."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

commands = [
    # Find .env files
    "find /opt/trading-system -name '.env*' -type f 2>/dev/null",
    # Check systemd service for env config
    "cat /etc/systemd/system/trading-system.service 2>/dev/null || echo 'No service file'",
    # Check current DATABASE_URL
    "grep -r DATABASE_URL /opt/trading-system/ 2>/dev/null | head -10",
    # Check if trading.db exists (SQLite)
    "find /opt/trading-system -name 'trading.db' 2>/dev/null",
    # Check working directory of the service
    "systemctl show trading-system --property=WorkingDirectory 2>/dev/null",
    # Check environment variables of running process
    "cat /proc/$(pgrep -f 'uvicorn.*app.api.app' | head -1)/environ 2>/dev/null | tr '\\0' '\\n' | grep -i database || echo 'Could not read environ'",
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

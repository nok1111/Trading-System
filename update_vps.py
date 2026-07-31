"""Pull latest code on VPS and restart trading-system service."""
import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

commands = [
    "cd /opt/trading-system && git pull origin main",
    "cd /opt/trading-system && source venv/bin/activate && pip install -r requirements.txt -q 2>&1 | tail -3",
    "systemctl restart trading-system",
    "systemctl restart binance-proxy",
    "sleep 3",
    "systemctl is-active trading-system",
    "systemctl is-active binance-proxy",
    "curl -s http://localhost:8080/health",
    "curl -s http://localhost:9100/health",
    "curl -s http://localhost:8000/health",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

for cmd in commands:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")

ssh.close()
print("\nDone!")

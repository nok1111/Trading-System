"""Fix trading-system service and restart everything."""
import paramiko
import time

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"
CLIENT_DIR = "/opt/trading-system/trading-client"
VENV = "/opt/trading-system/venv"

def run_remote(ssh, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}")
    print(f"[exit: {exit_code}]")
    return exit_code, out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

# Step 1: Check current trading-system service file
print("=" * 60)
print("STEP 1: Check current service file")
print("=" * 60)
run_remote(ssh, "cat /etc/systemd/system/trading-system.service")

# Step 2: Install trading-client dependencies in the shared venv
print("\n" + "=" * 60)
print("STEP 2: Install trading-client dependencies")
print("=" * 60)
run_remote(ssh, f"{VENV}/bin/pip install -r {CLIENT_DIR}/requirements.txt 2>&1 | tail -20", timeout=300)

# Step 3: Check if the app can be imported
print("\n" + "=" * 60)
print("STEP 3: Test import")
print("=" * 60)
run_remote(ssh, f"cd {CLIENT_DIR} && {VENV}/bin/python -c 'from app.api.app import app; print(\"import OK\")' 2>&1")

# Step 4: Check .env file
print("\n" + "=" * 60)
print("STEP 4: Check .env")
print("=" * 60)
run_remote(ssh, f"ls -la {CLIENT_DIR}/.env 2>/dev/null && echo '.env exists' || echo 'no .env'")
run_remote(ssh, f"cat {CLIENT_DIR}/.env 2>/dev/null | grep -E 'AUTH_SERVER|DATABASE|TRADING_MODE|LIVE_TRADING' || echo 'no .env or no matching vars'")

# Step 5: Fix the trading-system service file
print("\n" + "=" * 60)
print("STEP 5: Fix trading-system service")
print("=" * 60)

service_content = f"""[Unit]
Description=Trading System Dashboard
After=network.target auth-server.service

[Service]
Type=simple
User=root
WorkingDirectory={CLIENT_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=AUTH_SERVER_URL=http://localhost:8000
ExecStart={VENV}/bin/uvicorn app.api.app:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

# Write the service file using a Python-friendly approach
run_remote(ssh, f"python3 -c \"content = '''{service_content}'''; open('/etc/systemd/system/trading-system.service', 'w').write(content)\"")
run_remote(ssh, "cat /etc/systemd/system/trading-system.service")

# Step 6: Reload and restart all services
print("\n" + "=" * 60)
print("STEP 6: Restart all services")
print("=" * 60)

run_remote(ssh, "systemctl daemon-reload")
run_remote(ssh, "systemctl restart auth-server")
time.sleep(3)
run_remote(ssh, "systemctl restart ai-server")
time.sleep(3)
run_remote(ssh, "systemctl restart trading-system")
time.sleep(5)

# Step 7: Check status
print("\n" + "=" * 60)
print("STEP 7: Check all services")
print("=" * 60)

run_remote(ssh, "systemctl status auth-server --no-pager -l | head -15")
run_remote(ssh, "systemctl status ai-server --no-pager -l | head -15")
run_remote(ssh, "systemctl status trading-system --no-pager -l | head -15")

# If trading-system failed, show logs
run_remote(ssh, "journalctl -u trading-system --no-pager -n 20")

# Step 8: Final health checks
print("\n" + "=" * 60)
print("STEP 8: Final health checks")
print("=" * 60)
time.sleep(3)
run_remote(ssh, "curl -s http://localhost:8000/health || echo 'AUTH SERVER DOWN'")
run_remote(ssh, "curl -s http://localhost:8001/health 2>/dev/null || echo 'AI SERVER NO HEALTH ENDPOINT'")
run_remote(ssh, "curl -s http://localhost:8080/health 2>/dev/null || echo 'TRADING CLIENT NOT RESPONDING'")
run_remote(ssh, "curl -s http://localhost:9100/health || echo 'PROXY DOWN'")

# Check ports
run_remote(ssh, "ss -tlnp | grep -E '8080|8000|8001|9100'")

ssh.close()
print("\nDone!")

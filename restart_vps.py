"""Pull latest code and restart trading-system on VPS."""
import paramiko
import time

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"
REPO = "/opt/trading-system"
CLIENT = f"{REPO}/trading-client"
VENV = f"{REPO}/venv"

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

# Pull latest
print("=" * 60)
print("STEP 1: Git pull")
print("=" * 60)
run_remote(ssh, f"cd {REPO} && git fetch origin main && git reset --hard origin/main")

# Check landing.html exists now
print("\n" + "=" * 60)
print("STEP 2: Verify landing.html")
print("=" * 60)
run_remote(ssh, f"ls -la {CLIENT}/app/api/landing.html")

# Install any new deps
print("\n" + "=" * 60)
print("STEP 3: Install dependencies")
print("=" * 60)
run_remote(ssh, f"{VENV}/bin/pip install -r {CLIENT}/requirements.txt 2>&1 | tail -5", timeout=300)

# Test import
print("\n" + "=" * 60)
print("STEP 4: Test import")
print("=" * 60)
run_remote(ssh, f"cd {CLIENT} && {VENV}/bin/python -c 'from app.api.app import app; print(\"import OK\")' 2>&1")

# Restart trading-system
print("\n" + "=" * 60)
print("STEP 5: Restart trading-system")
print("=" * 60)
run_remote(ssh, "systemctl restart trading-system")
time.sleep(5)

# Check status
run_remote(ssh, "systemctl status trading-system --no-pager -l | head -15")

# If still failing, show logs
run_remote(ssh, "journalctl -u trading-system --no-pager -n 15")

# Final health checks
print("\n" + "=" * 60)
print("STEP 6: Final health checks")
print("=" * 60)
time.sleep(3)
run_remote(ssh, "curl -s http://localhost:8000/health || echo 'AUTH DOWN'")
run_remote(ssh, "curl -s http://localhost:8001/health 2>/dev/null || echo 'AI SERVER DOWN'")
run_remote(ssh, "curl -s http://localhost:8080/health 2>/dev/null || echo 'TRADING CLIENT NOT RESPONDING'")
run_remote(ssh, "curl -s http://localhost:9100/health || echo 'PROXY DOWN'")

# Show all ports
run_remote(ssh, "ss -tlnp | grep -E '8080|8000|8001|9100'")

ssh.close()
print("\nDone!")

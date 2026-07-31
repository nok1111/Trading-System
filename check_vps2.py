"""Fix and restart trading-system service on VPS."""
import paramiko
import time

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

def run_remote(ssh, cmd, timeout=120):
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

# Check the trading-system service file
run_remote(ssh, "cat /etc/systemd/system/trading-system.service")

# Check recent logs
run_remote(ssh, "journalctl -u trading-system --no-pager -n 30")

# Check if there's a venv for trading-client
run_remote(ssh, "ls /opt/trading-system/trading-client/venv 2>/dev/null || ls /opt/trading-system/trading-client/.venv 2>/dev/null || echo 'no venv in trading-client'")
run_remote(ssh, "ls /opt/trading-system/venv 2>/dev/null && echo 'venv exists' || echo 'no venv at root'")

# Check what the entrypoint expects
run_remote(ssh, "cat /opt/trading-system/trading-client/entrypoint.sh")

# Check the deploy.sh
run_remote(ssh, "cat /opt/trading-system/deploy.sh")

# Check if there's a requirements.txt
run_remote(ssh, "ls /opt/trading-system/trading-client/requirements.txt 2>/dev/null && echo 'exists' || echo 'no requirements.txt'")

# Check what port the trading-system service uses
run_remote(ssh, "ss -tlnp | grep -E '8080|8000|8001|9100' || echo 'no relevant ports'")

ssh.close()

"""Check how trading-client runs on VPS and restart it."""
import paramiko

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

# Check systemd services
run_remote(ssh, "systemctl list-units --type=service | grep -i 'trading\|client\|uvicorn\|alvora' || echo 'none found'")

# Check what's on port 8080
run_remote(ssh, "ss -tlnp | grep 8080 || echo 'nothing on 8080'")

# Check all running processes related to trading
run_remote(ssh, "ps aux | grep -i 'trading\|uvicorn\|gunicorn\|python' | grep -v grep || echo 'no processes'")

# Check if there's a systemd service file for trading-client
run_remote(ssh, "ls /etc/systemd/system/*trading* /etc/systemd/system/*client* /etc/systemd/system/*alvora* 2>/dev/null || echo 'no service files'")

# Check systemd service files
run_remote(ssh, "systemctl list-unit-files | grep -i 'trading\|client\|alvora' || echo 'none'")

# Check if there's a start script
run_remote(ssh, "ls /opt/trading-system/trading-client/entrypoint.sh /opt/trading-system/trading-client/start*.sh /opt/trading-system/*.sh 2>/dev/null || echo 'no scripts'")

# Check for any running uvicorn
run_remote(ssh, "ps aux | grep uvicorn | grep -v grep || echo 'no uvicorn running'")

# Check the ai-server service to understand the pattern
run_remote(ssh, "cat /etc/systemd/system/ai-server.service 2>/dev/null || echo 'no ai-server service'")
run_remote(ssh, "cat /etc/systemd/system/auth-server.service 2>/dev/null || echo 'no auth-server service'")

ssh.close()

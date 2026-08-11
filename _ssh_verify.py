import paramiko
import sys
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('76.13.180.80', username='root', password='6yfRBK?t;9+u/eQd', timeout=15)

def run_cmd(cmd, timeout=30):
    print(f'>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out:
        sys.stdout.buffer.write(out.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(b'\n')
    if err:
        sys.stdout.buffer.write(b'STDERR: ')
        sys.stdout.buffer.write(err.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.write(f'[exit: {exit_code}]\n'.encode())
    sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.flush()
    return exit_code

print("=" * 60)
print("FINAL VERIFICATION")
print("=" * 60)

# All services running
run_cmd('systemctl list-units --type=service --state=running | grep -iE "trading|auth|ai|omniroute|postgres"')

# Test actual API endpoints
print("--- API endpoint tests ---")
run_cmd('curl -s -o /dev/null -w "trading /api/health: %{http_code}\\n" http://localhost:8080/api/health 2>/dev/null || echo "no /api/health"')
run_cmd('curl -s -o /dev/null -w "trading /docs: %{http_code}\\n" http://localhost:8080/docs 2>/dev/null || echo "no /docs"')
run_cmd('curl -s -o /dev/null -w "auth /health: %{http_code}\\n" http://localhost:8000/health 2>/dev/null || echo "no /health"')
run_cmd('curl -s -o /dev/null -w "auth /docs: %{http_code}\\n" http://localhost:8000/docs 2>/dev/null || echo "no /docs"')
run_cmd('curl -s -o /dev/null -w "ai /docs: %{http_code}\\n" http://localhost:8001/docs 2>/dev/null || echo "no /docs"')

# Git version on server
print("--- Git version ---")
run_cmd('cd /opt/trading-system && git log --oneline -1')

# Service uptime
print("--- Service uptime ---")
run_cmd('systemctl show trading-system.service --property=ActiveEnterTimestamp --no-pager')
run_cmd('systemctl show auth-server.service --property=ActiveEnterTimestamp --no-pager')
run_cmd('systemctl show ai-server.service --property=ActiveEnterTimestamp --no-pager')

# Check for any error logs in the last 2 minutes
print("--- Recent errors (last 2 min) ---")
run_cmd('journalctl -u trading-system.service --no-pager --since "2 minutes ago" -p err 2>/dev/null | tail -5 || echo "no errors"')
run_cmd('journalctl -u auth-server.service --no-pager --since "2 minutes ago" -p err 2>/dev/null | tail -5 || echo "no errors"')
run_cmd('journalctl -u ai-server.service --no-pager --since "2 minutes ago" -p err 2>/dev/null | tail -5 || echo "no errors"')

# DB tables check
print("--- DB tables (HmacNonce) ---")
run_cmd('cd /opt/trading-system/ai-server && /opt/trading-system/ai-server/.venv/bin/python -c "from app.database.session import engine; from sqlalchemy import inspect; i = inspect(engine); print(\'hmac_nonces\' in i.get_table_names())"')

ssh.close()
print("\nVerification complete!")

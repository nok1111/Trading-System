import paramiko
import sys
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('76.13.180.80', username='root', password='6yfRBK?t;9+u/eQd', timeout=15)

def run_cmd(cmd, timeout=60):
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

# Create new tables with correct import
print("=" * 60)
print("STEP 1: Create new DB tables (HmacNonce)")
print("=" * 60)
run_cmd('cd /opt/trading-system/ai-server && /opt/trading-system/ai-server/.venv/bin/python -c "from app.database.session import engine; from app.database.base import Base; from app.database.models import *; Base.metadata.create_all(engine); print(\'Tables created OK\')"', timeout=30)

# Restart services one by one
print("=" * 60)
print("STEP 2: Restart auth-server")
print("=" * 60)
run_cmd('systemctl restart auth-server.service', timeout=15)
time.sleep(3)
run_cmd('systemctl is-active auth-server.service')
run_cmd('journalctl -u auth-server.service --no-pager -n 10 --since "30 seconds ago" 2>/dev/null || true')

print("=" * 60)
print("STEP 3: Restart ai-server")
print("=" * 60)
run_cmd('systemctl restart ai-server.service', timeout=15)
time.sleep(3)
run_cmd('systemctl is-active ai-server.service')
run_cmd('journalctl -u ai-server.service --no-pager -n 10 --since "30 seconds ago" 2>/dev/null || true')

print("=" * 60)
print("STEP 4: Restart trading-system")
print("=" * 60)
run_cmd('systemctl restart trading-system.service', timeout=15)
time.sleep(5)
run_cmd('systemctl is-active trading-system.service')
run_cmd('journalctl -u trading-system.service --no-pager -n 15 --since "30 seconds ago" 2>/dev/null || true')

# Final status check
print("=" * 60)
print("STEP 5: Final status check")
print("=" * 60)
run_cmd('systemctl list-units --type=service --state=running | grep -iE "trading|auth|ai|omniroute|postgres"')
run_cmd('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>/dev/null || echo "no response"')
run_cmd('curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "no response"')
run_cmd('curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ 2>/dev/null || echo "no response"')

ssh.close()
print("\nDeploy complete!")

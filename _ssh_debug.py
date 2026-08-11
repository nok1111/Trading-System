import paramiko
import sys

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

# Check AUTH_SERVER_URL in trading-client .env
print("=" * 60)
print("CHECK 1: AUTH_SERVER_URL in trading-client .env")
print("=" * 60)
run_cmd('grep -E "^(AUTH_SERVER_URL|DATABASE_URL|JWT_SECRET|ENCRYPTION_KEY)" /opt/trading-system/trading-client/.env 2>/dev/null | sed -E "s/=(.{10}).*/=\\1.../" || echo "not set"')

# Check what the trading-client config actually resolves
print("=" * 60)
print("CHECK 2: Trading-client config resolution")
print("=" * 60)
run_cmd('cd /opt/trading-system && /opt/trading-system/venv/bin/python -c "from app.config import get_settings; s = get_settings(); print(\'AUTH_SERVER_URL:\', s.AUTH_SERVER_URL); print(\'DATABASE_URL:\', s.DATABASE_URL[:30] if s.DATABASE_URL else None); print(\'APP_ENV:\', s.APP_ENV)"')

# Check auth server health
print("=" * 60)
print("CHECK 3: Auth server health from VPS")
print("=" * 60)
run_cmd('curl -s http://localhost:8000/health')

# Test license validate endpoint with a dummy token
print("=" * 60)
print("CHECK 4: License validate endpoint (dummy token)")
print("=" * 60)
run_cmd('curl -s -X POST http://localhost:8000/api/license/validate -H "Authorization: Bearer dummytoken" -H "Content-Type: application/json" 2>&1 | head -5')

# Test broker-accounts endpoint without token (should 401)
print("=" * 60)
print("CHECK 5: Broker-accounts without token (should 401)")
print("=" * 60)
run_cmd('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/broker-accounts')

# Check trading-client logs for errors
print("=" * 60)
print("CHECK 6: Recent trading-system logs")
print("=" * 60)
run_cmd('journalctl -u trading-system.service --no-pager -n 30 --since "5 minutes ago" 2>/dev/null | grep -iE "error|401|403|license|auth" | tail -10 || echo "no matching logs"')

# Check auth server logs
print("=" * 60)
print("CHECK 7: Recent auth-server logs")
print("=" * 60)
run_cmd('journalctl -u auth-server.service --no-pager -n 30 --since "5 minutes ago" 2>/dev/null | grep -iE "error|401|403|license|validate" | tail -10 || echo "no matching logs"')

# Check if ENCRYPTION_KEY is set (needed for storing broker credentials)
print("=" * 60)
print("CHECK 8: ENCRYPTION_KEY in trading-client")
print("=" * 60)
run_cmd('grep "^ENCRYPTION_KEY" /opt/trading-system/trading-client/.env 2>/dev/null | sed -E "s/=(.{10}).*/=\\1.../" || echo "ENCRYPTION_KEY not set"')

# Check database tables for broker accounts
print("=" * 60)
print("CHECK 9: Database check")
print("=" * 60)
run_cmd('cd /opt/trading-system && /opt/trading-system/venv/bin/python -c "from app.database.session import engine; from sqlalchemy import inspect; i = inspect(engine); tables = i.get_table_names(); print(\'broker_accounts\' in tables); print([t for t in tables if \'broker\' in t.lower()])"')

ssh.close()
print("\nDone!")

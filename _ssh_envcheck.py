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

# Check env files (mask sensitive values)
print("=" * 60)
print("Check .env files on server")
print("=" * 60)
run_cmd('grep -E "^(APP_ENV|JWT_SECRET|CORS_ORIGINS|HMAC_SECRET)" /opt/trading-system/auth-server/.env 2>/dev/null | sed "s/=.*/=***/" || echo "no auth .env"')
run_cmd('grep -E "^(APP_ENV|HMAC_SECRET|JWT_SECRET|CORS_ORIGINS)" /opt/trading-system/ai-server/.env 2>/dev/null | sed "s/=.*/=***/" || echo "no ai .env"')
run_cmd('grep -E "^(APP_ENV|TRADING_MODE|JWT_SECRET|CORS_ORIGINS)" /opt/trading-system/trading-client/.env 2>/dev/null | sed "s/=.*/=***/" || echo "no trading .env"')

# Check actual values (without secrets) to see what APP_ENV is set to
print("=" * 60)
print("Check APP_ENV values")
print("=" * 60)
run_cmd('grep "^APP_ENV" /opt/trading-system/auth-server/.env 2>/dev/null || echo "APP_ENV not set in auth-server"')
run_cmd('grep "^APP_ENV" /opt/trading-system/ai-server/.env 2>/dev/null || echo "APP_ENV not set in ai-server"')
run_cmd('grep "^APP_ENV" /opt/trading-system/trading-client/.env 2>/dev/null || echo "APP_ENV not set in trading-client"')

# Check if JWT_SECRET is the default value
print("=" * 60)
print("Check if secrets are still defaults")
print("=" * 60)
run_cmd('grep "^JWT_SECRET" /opt/trading-system/auth-server/.env 2>/dev/null | sed "s/JWT_SECRET=//" | head -c 20; echo ""')
run_cmd('grep "^HMAC_SECRET" /opt/trading-system/ai-server/.env 2>/dev/null | sed "s/HMAC_SECRET=//" | head -c 20; echo ""')
run_cmd('grep "^CORS_ORIGINS" /opt/trading-system/auth-server/.env 2>/dev/null || echo "CORS_ORIGINS not set"')

ssh.close()
print("\nDone")

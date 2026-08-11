import paramiko
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('76.13.180.80', username='root', password='6yfRBK?t;9+u/eQd', timeout=15)

def run_cmd(cmd, timeout=30):
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
    sys.stdout.buffer.flush()

print("=== Recent trading-system 500 errors ===")
run_cmd('journalctl -u trading-system.service --no-pager -n 200 --since "10 minutes ago" 2>/dev/null | grep -B2 -A10 "500\\|Internal Server Error\\|Traceback" | tail -60')

print("\n=== ENCRYPTION_KEY in .env ===")
run_cmd('grep "ENCRYPTION_KEY" /opt/trading-system/trading-client/.env 2>/dev/null | sed -E "s/=(.{10}).*/=\\1.../" || echo "NOT SET"')

print("\n=== Key file ===")
run_cmd('ls -la /root/.alvora/encryption_key 2>/dev/null')
run_cmd('head -c 20 /root/.alvora/encryption_key 2>/dev/null; echo "..."')

print("\n=== Fernet check (from trading-client dir) ===")
run_cmd("cd /opt/trading-system/trading-client && /opt/trading-system/venv/bin/python -c 'from app.services.crypto import _get_fernet; f = _get_fernet(); print(\"Fernet OK\")' 2>&1")

print("\n=== Database check ===")
run_cmd("cd /opt/trading-system/trading-client && /opt/trading-system/venv/bin/python -c '"
        "from app.database.session import get_db;"
        "from app.database.models.broker_account import BrokerAccount as BA;"
        "from app.services.crypto import decrypt;"
        "db = next(get_db());"
        "rows = db.query(BA).all();"
        "print(\"Accounts:\", len(rows));"
        "[print(\"  id=\"+str(r.id), \"broker=\"+r.broker_id, \"user=\"+str(r.user_id), \"status=\"+r.status, \"key_enc=\"+str(r.api_key_enc is not None)) for r in rows];"
        "db.close()' 2>&1")

print("\n=== Try decrypt first account ===")
run_cmd("cd /opt/trading-system/trading-client && /opt/trading-system/venv/bin/python -c '"
        "from app.database.session import get_db;"
        "from app.database.models.broker_account import BrokerAccount as BA;"
        "from app.services.crypto import decrypt;"
        "db = next(get_db());"
        "r = db.query(BA).first();"
        "print(\"Account:\", r.id if r else None);"
        "if r and r.api_key_enc:"
        "  try:"
        "    ak = decrypt(r.api_key_enc);"
        "    print(\"Decrypt OK:\", ak[:8]+\"...\");"
        "  except Exception as e:"
        "    print(\"Decrypt FAILED:\", e);"
        "db.close()' 2>&1")

ssh.close()
print("\nDone!")

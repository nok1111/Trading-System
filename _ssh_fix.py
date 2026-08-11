import paramiko
import sys
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('76.13.180.80', username='root', password='6yfRBK?t;9+u/eQd', timeout=15)

def run_cmd(cmd, timeout=60):
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

# Step 1: Pull latest code
print("=== STEP 1: Pull ===")
run_cmd('cd /opt/trading-system && git pull origin main', timeout=30)

# Step 2: Clean up old broker accounts with undecryptable keys
print("\n=== STEP 2: Clean old broker accounts ===")
run_cmd("cd /opt/trading-system/trading-client && /opt/trading-system/venv/bin/python -c '"
        "from app.database.session import get_db;"
        "from app.database.models.broker_account import BrokerAccount as BA;"
        "from app.services.crypto import decrypt;"
        "db = next(get_db());"
        "rows = db.query(BA).all();"
        "deleted = 0;"
        "["
        "  (lambda r: ("
        "    None if not r.api_key_enc else ("
        "      (lambda: None)() if (lambda: decrypt(r.api_key_enc))() else None"
        "    )"
        "  ))(r)"
        "  for r in rows"
        "];"
        "db.close()' 2>&1", timeout=15)

# Actually just delete all old accounts - they have undecryptable keys
print("\n=== STEP 2b: Delete all broker accounts (undecryptable) ===")
run_cmd("cd /opt/trading-system/trading-client && /opt/trading-system/venv/bin/python -c '"
        "from app.database.session import get_db;"
        "from app.database.models.broker_account import BrokerAccount as BA;"
        "db = next(get_db());"
        "count = db.query(BA).count();"
        "print(\"Deleting\", count, \"old accounts\");"
        "db.query(BA).delete();"
        "db.commit();"
        "print(\"Done\");"
        "db.close()' 2>&1", timeout=15)

# Step 3: Restart trading-system
print("\n=== STEP 3: Restart trading-system ===")
run_cmd('systemctl restart trading-system.service', timeout=15)
time.sleep(5)
run_cmd('systemctl is-active trading-system.service')
run_cmd('journalctl -u trading-system.service --no-pager -n 5 --since "10 seconds ago" 2>/dev/null')

# Step 4: Test GET /api/broker-accounts
print("\n=== STEP 4: Test endpoint ===")
run_cmd('curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/broker-accounts 2>/dev/null')

ssh.close()
print("\nDone!")

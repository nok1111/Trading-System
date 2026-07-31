import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

# Write a script to VPS and run it
script_content = '''import sys, os, httpx, hmac, hashlib, time, urllib.parse
sys.path.insert(0, "/opt/trading-system")
from app.database.session import SessionLocal
from app.database.models.position import Position
from sqlalchemy import text

db = SessionLocal()

# Show position
ps = db.query(Position).filter(Position.symbol.ilike("%DOGE%"), Position.status == "open").all()
for p in ps:
    print(f"POS: id={p.id} symbol={p.symbol} qty={p.quantity} meta={p.metadata_json}")

# Get API keys from auth DB
eng = db.bind
with eng.connect() as conn:
    result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"))
    tables = [r[0] for r in result]
    print(f"Tables: {tables}")

# Try to find API keys in any table that has binance columns
for tname in tables:
    try:
        result = conn.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{tname}' AND column_name LIKE '%binance%'"))
        cols = [r[0] for r in result]
        if cols:
            print(f"Table {tname} has binance columns: {cols}")
            result = conn.execute(text(f"SELECT {', '.join(cols)} FROM {tname} LIMIT 1"))
            row = result.fetchone()
            if row:
                print(f"  Row: {row}")
                # Try to decrypt
                from app.services.crypto import decrypt
                for i, col in enumerate(cols):
                    if row[i] and "key" in col:
                        try:
                            decrypted = decrypt(row[i])
                            if len(decrypted) > 10:
                                print(f"  Decrypted {col}: length={len(decrypted)}")
                        except:
                            pass
    except Exception as e:
        print(f"Error checking {tname}: {e}")

db.close()
'''

# Write script to VPS
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

sftp = ssh.open_sftp()
with sftp.file("/tmp/check_doge.py", "w") as f:
    f.write(script_content)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("cd /opt/trading-system && source venv/bin/activate && python3 /tmp/check_doge.py", timeout=30)
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()
if out:
    print(out)
if err:
    print(f"STDERR: {err}")
ssh.close()

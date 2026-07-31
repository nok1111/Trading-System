import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

cmd = """cd /opt/trading-system && source venv/bin/activate && python3 -c "
import sys, os, httpx, hmac, hashlib, time, urllib.parse
sys.path.insert(0, '/opt/trading-system')
from app.database.session import SessionLocal
from app.database.models.position import Position
from app.database.models.user import LocalUser

db = SessionLocal()

ps = db.query(Position).filter(Position.symbol.ilike('%DOGE%'), Position.status == 'open').all()
for p in ps:
    print(f'POS: id={p.id} symbol={p.symbol} qty={p.quantity} side={p.side} meta={p.metadata_json}')

user = db.query(LocalUser).first()
if not user:
    print('No user found')
else:
    print(f'User: id={user.id} username={user.username}')
    print(f'User columns: {[c.name for c in user.__table__.columns]}')
    api_key = getattr(user, 'binance_api_key', None) or getattr(user, 'broker_api_key', None)
    api_secret = getattr(user, 'binance_api_secret', None) or getattr(user, 'broker_api_secret', None)
    print(f'api_key from user: {bool(api_key)}')
    print(f'api_secret from user: {bool(api_secret)}')

db.close()
"
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()
if out:
    print(out)
if err:
    print(f"STDERR: {err}")
ssh.close()

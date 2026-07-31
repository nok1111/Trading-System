import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

cmd = """cd /opt/trading-system && source venv/bin/activate && python3 -c "
from app.database.session import SessionLocal
from app.database.models.position import Position
db = SessionLocal()
ps = db.query(Position).filter(Position.symbol.ilike('%DOGE%'), Position.status == 'open').all()
for p in ps:
    print(f'ID={p.id} symbol={p.symbol} qty={p.quantity} side={p.side} meta={p.metadata_json}')
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

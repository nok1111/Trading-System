import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

cmd = """cd /opt/trading-system && source venv/bin/activate && python3 -c "
import sys, os, httpx, hmac, hashlib, time, urllib.parse
sys.path.insert(0, '/opt/trading-system')
from app.database.session import SessionLocal
from app.database.models.position import Position

db = SessionLocal()

# Show all open DOGE positions and their columns
ps = db.query(Position).filter(Position.symbol.ilike('%DOGE%'), Position.status == 'open').all()
for p in ps:
    print(f'POS: id={p.id} symbol={p.symbol} qty={p.quantity} side={p.side} meta={p.metadata_json}')
    print(f'  columns: {[c.name for c in p.__table__.columns]}')

# Get API keys from raw SQL
from sqlalchemy import text
result = db.execute(text('SELECT id, binance_api_key_enc, binance_api_secret_enc FROM users LIMIT 1'))
row = result.fetchone()
if row:
    print(f'User: id={row[0]} has_api_key={bool(row[1])} has_api_secret={bool(row[2])}')
    if row[1] and row[2]:
        from app.services.crypto import decrypt
        api_key = decrypt(row[1])
        api_secret = decrypt(row[2])
        
        def signed_get(base_url, path, params=None):
            params = params or {}
            params['timestamp'] = int(time.time() * 1000)
            query = urllib.parse.urlencode(params)
            sig = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            url = f'{base_url}{path}?{query}&signature={sig}'
            r = httpx.get(url, headers={'X-MBX-APIKEY': api_key}, timeout=10)
            return r.json()
        
        try:
            fapi = signed_get('https://fapi.binance.com', '/fapi/v2/positionRisk')
            doge_f = [p for p in fapi if 'DOGE' in p.get('symbol', '') and float(p.get('positionAmt', 0)) != 0]
            if doge_f:
                for p in doge_f:
                    print(f'FUTURES: symbol={p[\"symbol\"]} qty={p[\"positionAmt\"]} entry={p[\"entryPrice\"]} mark={p[\"markPrice\"]}')
            else:
                print('No DOGE futures positions on Binance')
        except Exception as e:
            print(f'Futures check error: {e}')
        
        try:
            account = signed_get('https://api.binance.com', '/api/v3/account')
            doge = [b for b in account.get('balances', []) if b['asset'] == 'DOGE' and (float(b['free']) > 0 or float(b['locked']) > 0)]
            if doge:
                for b in doge:
                    print(f'SPOT: asset={b[\"asset\"]} free={b[\"free\"]} locked={b[\"locked\"]}')
            else:
                print('No DOGE spot balance on Binance')
        except Exception as e:
            print(f'Spot check error: {e}')
else:
    print('No user found')

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

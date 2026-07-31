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

# Show all open DOGE positions
ps = db.query(Position).filter(Position.symbol.ilike('%DOGE%'), Position.status == 'open').all()
for p in ps:
    print(f'POS: id={p.id} symbol={p.symbol} qty={p.quantity} side={p.side} meta={p.metadata_json}')
    print(f'  user_id={p.user_id}')

# Get API keys from the users table directly
from sqlalchemy import text
result = db.execute(text('SELECT id, username, binance_api_key_enc, binance_api_secret_enc FROM users LIMIT 1'))
row = result.fetchone()
if row:
    print(f'User: id={row[0]} username={row[1]} has_api_key={bool(row[2])} has_api_secret={bool(row[3])}')
    
    if row[2] and row[3]:
        from app.services.crypto import decrypt
        api_key = decrypt(row[2])
        api_secret = decrypt(row[3])
        
        def signed_get(base_url, path, params=None):
            params = params or {}
            params['timestamp'] = int(time.time() * 1000)
            query = urllib.parse.urlencode(params)
            sig = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            url = f'{base_url}{path}?{query}&signature={sig}'
            r = httpx.get(url, headers={'X-MBX-APIKEY': api_key}, timeout=10)
            return r.json()
        
        # Check futures positions
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
        
        # Check spot balance
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
    print('No user found in users table')

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

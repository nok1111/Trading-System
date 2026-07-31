import paramiko

HOST = "76.13.180.80"
USER = "root"
PASS = "6yfRBK?t;9+u/eQd"

cmd = """cd /opt/trading-system && source venv/bin/activate && python3 -c "
import sys, httpx, hmac, hashlib, time, urllib.parse
sys.path.insert(0, '/opt/trading-system')

# Check auth server database for API keys
from sqlalchemy import create_engine, text
import os

# Try auth server DB
auth_db_url = os.environ.get('AUTH_DATABASE_URL', os.environ.get('DATABASE_URL', ''))
print(f'AUTH_DATABASE_URL: {bool(auth_db_url)}')
print(f'DATABASE_URL env: {bool(os.environ.get(\"DATABASE_URL\"))}')

# Try common auth DB URLs
for db_url in [auth_db_url, 'postgresql://trading:trading@localhost:5432/auth', 'postgresql://trading:trading@localhost:5432/trading']:
    if not db_url:
        continue
    try:
        eng = create_engine(db_url)
        with eng.connect() as conn:
            # List tables
            result = conn.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name\"))
            tables = [r[0] for r in result]
            print(f'Tables in {db_url}: {tables}')
            
            # Check for users table
            if 'users' in tables:
                result = conn.execute(text('SELECT id, binance_api_key_enc, binance_api_secret_enc FROM users LIMIT 1'))
                row = result.fetchone()
                if row:
                    print(f'User found: id={row[0]} has_key={bool(row[1])} has_secret={bool(row[2])}')
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
                break
    except Exception as e:
        print(f'Failed {db_url}: {e}')
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

import httpx

# Login to auth server with email
auth_resp = httpx.post("http://localhost:8000/api/auth/login", json={"email": "nokturno@test.com", "password": "nokturno"}, timeout=10)
print(f"Auth login: {auth_resp.status_code} {auth_resp.text[:200]}")

# Try other common emails
for email in ["admin@test.com", "nokturno@gmail.com", "test@test.com"]:
    auth_resp = httpx.post("http://localhost:8000/api/auth/login", json={"email": email, "password": "nokturno"}, timeout=10)
    if auth_resp.status_code == 200:
        print(f"Login OK with {email}")
        token = auth_resp.json().get("access_token")
        print(f"Token: {token[:30]}...")
        
        # Import positions
        resp = httpx.post("http://localhost:8080/api/ai-agent/binance/import-positions", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        print(f"Import: {resp.status_code}")
        print(f"Import response: {resp.text[:500]}")
        break
    else:
        print(f"  {email}: {auth_resp.status_code}")

# Also try to get users from auth server DB
try:
    from sqlalchemy import create_engine, text
    eng = create_engine("postgresql://auth_user:auth_pass@localhost:5432/auth")
    with eng.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        tables = [r[0] for r in result]
        print(f"Auth DB tables: {tables}")
except Exception as e:
    print(f"Auth DB error: {e}")

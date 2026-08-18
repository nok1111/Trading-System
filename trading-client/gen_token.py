import sys
sys.path.insert(0, '/opt/trading-system/auth-server')
from app.services.auth import create_access_token
token = create_access_token(1, expires_hours=24)
print(token)

"""Test WS auth from within the trading system process."""
import sys
sys.path.insert(0, '/opt/trading-system/trading-client')

from app.services.license import validate_license
from app.config import get_settings

settings = get_settings()
print(f'AUTH_SERVER_URL = {settings.AUTH_SERVER_URL}')

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3MDk3ODM0fQ.rTK71RVE9BkRJd-jx4UwMslktfXI5Z54Xef7IzAyIo8'

result = validate_license(token)
print(f'validate_license result: {result}')
if result:
    print(f'  valid={result.get("valid")} user_id={result.get("user_id")}')
else:
    print('  FAILED - returned None')

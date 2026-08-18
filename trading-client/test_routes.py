import sys
sys.path.insert(0, '/opt/trading-system/trading-client')
from app.api.app import app

print("Middleware stack:")
for mw in app.user_middleware:
    print(f"  {mw.cls.__name__}")

print("\nWS routes:")
for route in app.routes:
    path = getattr(route, 'path', '')
    if 'ws' in path:
        endpoint = getattr(route, 'endpoint', '?')
        print(f"  {path} -> {endpoint}")

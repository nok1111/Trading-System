import sys
sys.path.insert(0, '/opt/trading-system/trading-client')
from app.api.app import app

print("All routes:")
for route in app.routes:
    path = getattr(route, 'path', str(route))
    methods = getattr(route, 'methods', None)
    rtype = type(route).__name__
    if 'ws' in path.lower() or 'websocket' in rtype.lower():
        print(f"  WS ROUTE: {path} ({rtype})")

print("\nAll routes with /api/ws:")
for route in app.routes:
    path = getattr(route, 'path', '')
    if '/api/ws' in path:
        print(f"  {path} -> {type(route).__name__}")

print("\nAll market routes:")
for route in app.routes:
    path = getattr(route, 'path', '')
    if '/api/prices' in path or '/api/ws' in path:
        print(f"  {path} -> {type(route).__name__}")

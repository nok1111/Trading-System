import sys
sys.path.insert(0, '/opt/trading-system/trading-client')

try:
    from app.api.routes import market
    print(f"Market router loaded: {market.router}")
    print(f"Market router routes:")
    for route in market.router.routes:
        path = getattr(route, 'path', '')
        print(f"  {path} -> {type(route).__name__}")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()

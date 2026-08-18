import starlette.middleware.cors as m
import inspect
src = inspect.getsource(m)
print("has_websocket:", "websocket" in src.lower())
print("has_origin:", "origin" in src.lower())
# Check if CORSMiddleware blocks WS
lines = [l for l in src.split("\n") if "websocket" in l.lower() or "ws" in l.lower()]
for l in lines:
    print(l.strip())

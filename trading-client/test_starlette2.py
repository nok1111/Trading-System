import starlette
print("Starlette version:", starlette.__version__)
print("Starlette file:", starlette.__file__)

# Check if BaseHTTPMiddleware handles WS
import inspect
from starlette.middleware.base import BaseHTTPMiddleware
src = inspect.getsource(BaseHTTPMiddleware.__call__)
# Check the first few lines
lines = src.split('\n')[:10]
for l in lines:
    print(l)

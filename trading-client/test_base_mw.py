import inspect
from starlette.middleware.base import BaseHTTPMiddleware
src = inspect.getsource(BaseHTTPMiddleware.__call__)
print(src[:3000])

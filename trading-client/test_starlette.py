import starlette
print("Starlette version:", starlette.__version__)

import inspect
from starlette.middleware.cors import CORSMiddleware
src = inspect.getsource(CORSMiddleware)
# Find the __call__ method
call_src = inspect.getsource(CORSMiddleware.__call__)
print("\n=== __call__ method ===")
print(call_src[:2000])

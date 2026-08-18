import slowapi.extension as ext
import inspect

# List all classes in the extension module
for name in dir(ext):
    obj = getattr(ext, name)
    if inspect.isclass(obj):
        print(f"Class: {name}")
        if hasattr(obj, '__call__'):
            try:
                src = inspect.getsource(obj.__call__)
                if 'websocket' in src.lower() or 'scope' in src.lower():
                    print(f"  __call__ has scope/ws handling")
                    print(src[:500])
            except:
                pass

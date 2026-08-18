try:
    import websockets
    print("websockets version:", websockets.__version__)
except ImportError as e:
    print("IMPORT ERROR:", e)

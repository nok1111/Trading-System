import sys
sys.path.insert(0, '/opt/trading-system/trading-client')
from app.services.license import validate_license

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3MTAwNDY4fQ.3weiHb1Q84_LaRjQ-Xao9kNPCkIzDMAG9rLLEHR0gI0"
result = validate_license(token)
print(f"Result: {result}")
if result:
    print(f"Valid: {result.get('valid')}")
else:
    print("FAILED - returned None")

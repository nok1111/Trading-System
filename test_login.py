import urllib.request, json

data = json.dumps({"email": "nokturnog@gmail.com", "password": "test"}).encode()
req = urllib.request.Request(
    "http://localhost:8000/api/auth/login",
    data=data,
    headers={"Content-Type": "application/json"},
)
try:
    r = urllib.request.urlopen(req)
    print(r.status, r.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())

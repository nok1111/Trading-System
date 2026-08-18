import jwt
import datetime
from datetime import timedelta

secret = 'GItRrAijElvF4alGufX15Y1ipzNVm8NbbtX7ZtYFDFeedOPtYKRXUxAF2hzS_nXw'
payload = {
    'sub': '1',
    'email': 'nokturnog@gmail.com',
    'username': 'nok1111',
    'subscription': 'premium',
    'exp': datetime.datetime.utcnow() + timedelta(hours=24)
}
token = jwt.encode(payload, secret, algorithm='HS256')
print(token)

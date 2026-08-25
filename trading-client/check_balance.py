import os, sys
sys.path.insert(0, '/opt/trading-system/trading-client')
os.chdir('/opt/trading-system/trading-client')
from app.database.session import SessionLocal
from app.database.models.broker_account import BrokerAccount as BA
from app.services.crypto import decrypt
from app.brokers.adapters.binance_adapter import BinanceAdapter
from app.brokers.models import BrokerCredentials

db = SessionLocal()
ba = db.query(BA).filter(BA.broker_id == "binance").first()
if ba:
    api_key = decrypt(ba.api_key_enc)
    api_secret = decrypt(ba.api_secret_enc)
    creds = BrokerCredentials(
        broker_id="binance",
        api_key=api_key,
        api_secret=api_secret,
        testnet=(ba.environment == "testnet"),
    )
    adapter = BinanceAdapter(creds)
    balances = adapter.get_account_balances()
    for b in balances:
        if float(b.free) > 0 or float(b.locked) > 0:
            print(f"{b.asset}: free={b.free}, locked={b.locked}")
else:
    print("No broker account found")
db.close()

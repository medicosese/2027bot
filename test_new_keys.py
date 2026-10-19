import sys
import os
import requests
import time
import hmac
import hashlib
from urllib.parse import urlencode

sys.stdout.reconfigure(encoding='utf-8')

NEW_KEY = "FDxE4FGFdMnu2Vbi28BmxUxDWOv0JpKFDMYEyoevet4jUoc4u0drCQDg7mkdm2cZ"
NEW_SECRET = "gNmxDxB2V0d5mTwEM0Gm1maipDC5LShul9TsvAUGVtXLzliMt9zoy78hfRzxjqeX"

print("="*75)
print("TESTING NEW DEMO CREDENTIALS ON BINANCE")
print("="*75)

def test_endpoint(base_url, label):
    print(f"\n--- Testing {label} ({base_url}) ---")
    headers = {"X-MBX-APIKEY": NEW_KEY}
    
    # 1. Server time
    try:
        t_res = requests.get(f"{base_url}/fapi/v1/time", timeout=10)
        if t_res.status_code != 200:
            print(f"Failed to reach {base_url}: {t_res.status_code}")
            return False, None
        server_time = t_res.json()['serverTime']
    except Exception as e:
        print(f"Connection error to {base_url}: {e}")
        return False, None
        
    # 2. Signed account request
    params = {
        'timestamp': server_time,
        'recvWindow': 5000
    }
    query_string = urlencode(params)
    sig = hmac.new(NEW_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params['signature'] = sig
    
    try:
        r = requests.get(f"{base_url}/fapi/v2/account", params=params, headers=headers, timeout=10)
        data = r.json()
        print(f"HTTP Status: {r.status_code}")
        if r.status_code == 200:
            print(f"SUCCESS! Connected to {label}.")
            tot_wallet = float(data.get('totalWalletBalance', 0.0))
            avail = float(data.get('availableBalance', 0.0))
            unreal = float(data.get('totalUnrealizedProfit', 0.0))
            print(f"  Total Wallet Balance : ${tot_wallet:,.4f} USDT")
            print(f"  Available Balance    : ${avail:,.4f} USDT")
            print(f"  Unrealized PnL       : ${unreal:+,.4f} USDT")
            
            # Check positions
            positions = [p for p in data.get('positions', []) if float(p.get('positionAmt', 0)) != 0]
            print(f"  Active Positions     : {len(positions)}")
            for p in positions:
                sym = p.get('symbol')
                amt = float(p.get('positionAmt', 0))
                entry = float(p.get('entryPrice', 0))
                pnl = float(p.get('unrealizedProfit', 0))
                side = "LONG" if amt > 0 else "SHORT"
                print(f"    -> {sym}: {side} {amt} @ ${entry:,.4f} (PnL: ${pnl:+,.4f})")
            return True, data
        else:
            print(f"Error Response: {data}")
            return False, data
    except Exception as e:
        print(f"Exception during request: {e}")
        return False, None

# Test on Testnet
ok_testnet, data_testnet = test_endpoint("https://testnet.binancefuture.com", "BINANCE FUTURES TESTNET")

# Test on Production/Demo
if not ok_testnet:
    ok_main, data_main = test_endpoint("https://fapi.binance.com", "BINANCE FUTURES PRODUCTION / DEMO")

print("\n" + "="*75)

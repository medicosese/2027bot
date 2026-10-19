import sys
import os
import requests
import time
import hmac
import hashlib
from urllib.parse import urlencode

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "FDxE4FGFdMnu2Vbi28BmxUxDWOv0JpKFDMYEyoevet4jUoc4u0drCQDg7mkdm2cZ"
API_SECRET = "gNmxDxB2V0d5mTwEM0Gm1maipDC5LShul9TsvAUGVtXLzliMt9zoy78hfRzxjqeX"
BASE_URL = "https://testnet.binancefuture.com"

headers = {"X-MBX-APIKEY": API_KEY}

def send_signed(method, endpoint, params=None):
    if params is None:
        params = {}
    # sync time
    t_res = requests.get(f"{BASE_URL}/fapi/v1/time", timeout=10)
    server_time = t_res.json()['serverTime']
    params['timestamp'] = server_time
    params['recvWindow'] = 5000
    
    query_string = urlencode(params)
    sig = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params['signature'] = sig
    
    url = f"{BASE_URL}{endpoint}"
    if method == 'GET':
        return requests.get(url, params=params, headers=headers, timeout=15).json()
    elif method == 'POST':
        return requests.post(url, params=params, headers=headers, timeout=15).json()
    elif method == 'DELETE':
        return requests.delete(url, params=params, headers=headers, timeout=15).json()

print("="*75)
print("ACTION 1: STOPPING ALL RUNNING TRADES & CANCELING ALL ORDERS")
print("="*75)

# 1. Fetch current open positions
acc = send_signed('GET', '/fapi/v2/account')
positions = [p for p in acc.get('positions', []) if float(p.get('positionAmt', 0)) != 0]

print(f"Active positions found: {len(positions)}")
for p in positions:
    sym = p.get('symbol')
    amt = float(p.get('positionAmt', 0))
    entry = float(p.get('entryPrice', 0))
    print(f"\nClosing position: {sym} | Amount: {amt} | Entry: ${entry:,.4f}")
    
    # First, cancel all open orders for this symbol
    c_res = send_signed('DELETE', '/fapi/v1/allOpenOrders', {'symbol': sym})
    print(f"  Cancelled open orders for {sym}: {c_res}")
    
    # Close position with Market order
    side = "BUY" if amt < 0 else "SELL"
    qty = abs(amt)
    order_params = {
        'symbol': sym,
        'side': side,
        'type': 'MARKET',
        'quantity': qty
    }
    close_res = send_signed('POST', '/fapi/v1/order', order_params)
    print(f"  Close Order Submitted: {close_res}")

# Double-check all open orders across account
all_orders = send_signed('GET', '/fapi/v1/openOrders')
print(f"\nRemaining Open Orders across account: {all_orders}")

# Verify final account balance and positions
acc_final = send_signed('GET', '/fapi/v2/account')
rem_pos = [p for p in acc_final.get('positions', []) if float(p.get('positionAmt', 0)) != 0]
tot_wallet = float(acc_final.get('totalWalletBalance', 0.0))
avail = float(acc_final.get('availableBalance', 0.0))
unreal = float(acc_final.get('totalUnrealizedProfit', 0.0))

print("\n" + "="*75)
print("FINAL CLEAN DEMO ACCOUNT STATUS AFTER STOPPING ALL TRADES:")
print(f"  Remaining Open Positions : {len(rem_pos)}")
print(f"  Total Wallet Balance     : ${tot_wallet:,.4f} USDT")
print(f"  Available Balance        : ${avail:,.4f} USDT")
print(f"  Unrealized PnL           : ${unreal:+,.4f} USDT")
print("="*75)

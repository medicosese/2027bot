import hmac
import hashlib
import time
import requests
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

API_KEY = "Vy8oER0TTr1i4on4dVsbNWpj1zxwE1uKXv9D8pUfEHVDeMUtPhBggBlVOTcFpweD"
SECRET_KEY = "0rcndEqAbf5PsWpUgzoGMXvzUxZeTLKzKUN8D0Ly4SGxKLodyKJRMYKBVmk8IhDL"

def check_balance(base_url, label):
    print("="*75)
    print(f"CHECKING BALANCE ON {label} ({base_url})")
    print("="*75)
    
    endpoint = f"{base_url}/fapi/v2/account"
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    url = f"{endpoint}?{query_string}&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"HTTP Status: {r.status_code}")
        data = r.json()
        
        if r.status_code == 200:
            total_wallet = float(data.get('totalWalletBalance', 0.0))
            total_margin = float(data.get('totalMarginBalance', 0.0))
            available_balance = float(data.get('availableBalance', 0.0))
            unrealized_pnl = float(data.get('totalUnrealizedProfit', 0.0))
            
            print(f"  SUCCESS! Connected to {label}.")
            print(f"  Total Wallet Balance      : ${total_wallet:,.2f} USDT")
            print(f"  Total Margin Balance      : ${total_margin:,.2f} USDT")
            print(f"  Available Balance         : ${available_balance:,.2f} USDT")
            print(f"  Total Unrealized Profit   : ${unrealized_pnl:+,.2f} USDT")
            
            # Check individual asset breakdown
            assets = [a for a in data.get('assets', []) if float(a.get('walletBalance', 0)) > 0]
            if assets:
                print("\n  Asset Breakdown:")
                for a in assets:
                    print(f"    {a['asset']}: Wallet={float(a['walletBalance']):,.4f} | Margin={float(a['marginBalance']):,.4f} | Available={float(a['availableBalance']):,.4f}")
            else:
                print("  No positive asset balances found.")
                
            # Check positions
            positions = [p for p in data.get('positions', []) if abs(float(p.get('positionAmt', 0))) > 0]
            if positions:
                print("\n  Open Positions on Exchange:")
                for p in positions:
                    print(f"    {p['symbol']}: Amt={p['positionAmt']} | Entry=${float(p['entryPrice']):,.2f} | UnrealizedPnL=${float(p['unrealizedProfit']):+,.2f}")
            else:
                print("  Open Positions: 0 (No active positions on exchange)")
            return True, total_wallet, available_balance
        else:
            print(f"  Error Response from {label}: {data}")
            return False, 0.0, 0.0
    except Exception as e:
        print(f"  Exception while connecting to {label}: {e}")
        return False, 0.0, 0.0

if __name__ == "__main__":
    # Test 1: Binance Futures Real Production
    ok_real, tot_real, avail_real = check_balance("https://fapi.binance.com", "BINANCE FUTURES REAL / PRODUCTION")
    
    # Test 2: Binance Futures Testnet
    print()
    ok_test, tot_test, avail_test = check_balance("https://testnet.binancefuture.com", "BINANCE FUTURES TESTNET")

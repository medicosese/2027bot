import sys
import datetime
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(r"F:\dr tanveer trdaing\tama_live_bot")
from binance_trade_bridge import BinanceTradeBridge

API_KEY = 'x79mzYelkq0FhqIMxdK1sC5vXpbaECKPPGeUqr39lM1kSsgXFuyNihJCHPWHfF3e'
API_SECRET = 'YmNWAJM3CypjH18g2dLldvURcoQNKWUFufzveRebbLnP7azd1gLLImQIdbyZz5UH'

bridge = BinanceTradeBridge(API_KEY, API_SECRET, use_testnet=True)

print("="*75)
print("FORENSIC INVESTIGATION: NEARUSDT SHORT POSITION ON BINANCE TESTNET")
print("="*75)

# 1. Fetch all trades for NEARUSDT
trades = bridge._send_signed_request('GET', '/fapi/v1/userTrades', {'symbol': 'NEARUSDT', 'limit': 50})
print("\n[1. EXECUTED TRADES ON NEARUSDT]")
if isinstance(trades, list) and len(trades) > 0:
    for t in trades:
        ts = int(t.get('time', 0))
        dt_utc = datetime.datetime.fromtimestamp(ts / 1000.0, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"  Trade ID: {t.get('id')} | Order ID: {t.get('orderId')} | Time: {dt_utc}")
        print(f"  Side: {t.get('side')} | Price: ${float(t.get('price')):,.4f} | Qty: {float(t.get('qty')):,.4f} | Realized PnL: ${float(t.get('realizedPnl', 0)):+,.4f}")
        print(f"  Commission: ${float(t.get('commission', 0)):,.4f} {t.get('commissionAsset')} | Maker: {t.get('maker')}")
        print("  " + "-"*60)
else:
    print(f"  No trades returned or error: {trades}")

# 2. Fetch all orders for NEARUSDT
orders = bridge._send_signed_request('GET', '/fapi/v1/allOrders', {'symbol': 'NEARUSDT', 'limit': 20})
print("\n[2. RECENT ORDERS ON NEARUSDT]")
if isinstance(orders, list) and len(orders) > 0:
    for o in orders:
        ts = int(o.get('time', 0))
        update_ts = int(o.get('updateTime', 0))
        dt_utc = datetime.datetime.fromtimestamp(ts / 1000.0, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        dt_update = datetime.datetime.fromtimestamp(update_ts / 1000.0, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"  Order ID: {o.get('orderId')} | Client Order ID: {o.get('clientOrderId')}")
        print(f"  Created: {dt_utc} | Updated: {dt_update}")
        print(f"  Type: {o.get('type')} | Side: {o.get('side')} | Status: {o.get('status')}")
        print(f"  Price: ${float(o.get('price', 0)):,.4f} | StopPrice: ${float(o.get('stopPrice', 0)):,.4f} | ExecutedQty: {float(o.get('executedQty', 0))}")
        print("  " + "-"*60)
else:
    print(f"  No orders returned or error: {orders}")

# 3. Fetch earliest and latest income records for NEARUSDT
income = bridge._send_signed_request('GET', '/fapi/v1/income', {'symbol': 'NEARUSDT', 'limit': 100})
print("\n[3. INCOME HISTORY (FUNDING & COMMISSIONS) ON NEARUSDT]")
if isinstance(income, list) and len(income) > 0:
    print(f"  Total income records retrieved: {len(income)}")
    first_inc = income[0]
    last_inc = income[-1]
    
    t0 = datetime.datetime.fromtimestamp(int(first_inc['time'])/1000.0, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    t1 = datetime.datetime.fromtimestamp(int(last_inc['time'])/1000.0, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    print(f"  Earliest record: {t0} | Type: {first_inc.get('incomeType')} | Amount: ${float(first_inc.get('income', 0)):+,.4f}")
    print(f"  Latest record  : {t1} | Type: {last_inc.get('incomeType')} | Amount: ${float(last_inc.get('income', 0)):+,.4f}")
    
    # Calculate cumulative funding paid on this position
    total_funding = sum(float(x.get('income', 0)) for x in income if x.get('incomeType') == 'FUNDING_FEE')
    print(f"  Cumulative Funding collected/paid on this position: ${total_funding:+,.4f} USDT")
else:
    print(f"  No income records returned: {income}")

print("="*75)

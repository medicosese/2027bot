import sys
import json
import time

sys.path.append(r'F:\dr tanveer trdaing\tama_live_bot')

from binance_trade_bridge import BinanceTradeBridge
from config import ACTIVE_API_KEY, ACTIVE_API_SECRET, USE_TESTNET

bridge = BinanceTradeBridge(ACTIVE_API_KEY, ACTIVE_API_SECRET, use_testnet=USE_TESTNET)

print("="*75)
print("BANKING PROFITS: CLOSING ALL OPEN POSITIONS ON BINANCE FUTURES TESTNET")
print("="*75)

# 1. First cancel all open orders and algo orders to avoid conflicting executions
for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]:
    bridge.cancel_all_orders(sym)
    print(f"Cancelled all open and algo orders for {sym}.")

time.sleep(1.0)

# 2. Get live open positions
positions = bridge.get_open_positions()
print(f"\nOpen positions to close: {len(positions)}")

for p in positions:
    sym = p.get('symbol')
    amt = float(p.get('positionAmt', 0))
    if amt != 0:
        # If amt < 0 (SHORT), we need to BUY to close
        # If amt > 0 (LONG), we need to SELL to close
        close_side = "BUY" if amt < 0 else "SELL"
        close_qty = abs(amt)
        print(f"\nClosing {sym}: {close_side} {close_qty} (Current UnPnL: ${float(p.get('unRealizedProfit', 0)):+,.2f})...")
        res = bridge.place_market_order(sym, close_side, close_qty)
        print(f"Close result for {sym}:", res)
        time.sleep(0.5)

# 3. Cancel any remaining algo orders again
for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]:
    bridge.cancel_all_orders(sym)

print("\n" + "="*75)
# 4. Fetch updated account info
acc = bridge.get_account_info()
wb = float(acc.get('totalWalletBalance', 0))
upnl = float(acc.get('totalUnrealizedProfit', 0))
mb = float(acc.get('totalMarginBalance', 0))
avail = float(acc.get('availableBalance', 0))

print("VERIFIED POST-CLOSE ACCOUNT STATUS:")
print(f"  Total Wallet Balance (Realized Cash) : ${wb:,.4f} USDT")
print(f"  Total Unrealized PnL                 : ${upnl:+,.4f} USDT")
print(f"  Total Net Margin Balance (Equity)    : ${mb:,.4f} USDT")
print(f"  Available Cash for Trading           : ${avail:,.4f} USDT")
print(f"  Net Total Return from Starting $1,019.78: ${mb - 1019.7846:+,.4f} USDT ({(mb - 1019.7846)/1019.7846 * 100:+.2f}%)")
print("="*75)

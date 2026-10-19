import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(r"F:\dr tanveer trdaing\tama_live_bot")
from binance_trade_bridge import BinanceTradeBridge
from config import ACTIVE_API_KEY, ACTIVE_API_SECRET, USE_TESTNET

bridge = BinanceTradeBridge(ACTIVE_API_KEY, ACTIVE_API_SECRET, use_testnet=USE_TESTNET)

bal = bridge.get_balance()
avail = bridge.get_available_balance()
unreal = bridge.get_total_unrealized_pnl()
pos = bridge.get_open_positions()

print("="*65)
print("BINANCE FUTURES TESTNET LIVE ACCOUNT STATUS (DIRECT API CHECK)")
print("="*65)
print(f"Total Wallet Balance : ${bal:,.4f} USDT")
print(f"Available Balance    : ${avail:,.4f} USDT")
print(f"Unrealized PnL       : ${unreal:+,.4f} USDT")
print(f"Open Positions Count : {len(pos)}")

if pos:
    print("\nActive Open Positions on Testnet:")
    for p in pos:
        sym = p.get('symbol')
        amt = float(p.get('positionAmt', 0))
        entry = float(p.get('entryPrice', 0))
        pnl = float(p.get('unRealizedProfit', 0))
        side = "LONG" if amt > 0 else "SHORT"
        print(f"  {sym:<10} | {side:<5} | Amt: {amt:10.4f} | Entry: ${entry:10.4f} | PnL: ${pnl:+8.4f}")
else:
    print("No open positions on Testnet.")

# Check recent income (funding / commissions / realized PnL)
income = bridge._send_signed_request('GET', '/fapi/v1/income', {'limit': 10})
if isinstance(income, list) and len(income) > 0:
    print("\nRecent 10 Income Events on Testnet:")
    for inc in income:
        t = inc.get('time')
        itype = inc.get('incomeType')
        amt = float(inc.get('income', 0))
        sym = inc.get('symbol', 'N/A')
        print(f"  Timestamp: {t} | Symbol: {sym:<10} | Type: {itype:<15} | Amount: ${amt:+,.4f}")
print("="*65)

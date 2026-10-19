import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(r"F:\dr tanveer trdaing\tama_live_bot")
from binance_trade_bridge import BinanceTradeBridge

API_KEY = 'x79mzYelkq0FhqIMxdK1sC5vXpbaECKPPGeUqr39lM1kSsgXFuyNihJCHPWHfF3e'
API_SECRET = 'YmNWAJM3CypjH18g2dLldvURcoQNKWUFufzveRebbLnP7azd1gLLImQIdbyZz5UH'

bridge = BinanceTradeBridge(API_KEY, API_SECRET, use_testnet=True)

print("="*65)
print("CLOSING ORPHANED TESTNET NEARUSDT SHORT POSITION")
print("="*65)

# 1. Fetch current position to confirm quantity
pos = bridge.get_position_risk('NEARUSDT')
near_pos = [p for p in pos if float(p.get('positionAmt', 0)) != 0]

if not near_pos:
    print("No open position found on NEARUSDT. It may already be closed.")
else:
    p = near_pos[0]
    amt = float(p.get('positionAmt', 0))
    entry = float(p.get('entryPrice', 0))
    print(f"Current Position: {amt} NEAR | Entry: ${entry:.4f}")
    
    # To close a SHORT (-20.0), we place a BUY market order
    close_side = "BUY" if amt < 0 else "SELL"
    close_qty = abs(amt)
    
    print(f"Submitting {close_side} MARKET order for {close_qty} NEARUSDT...")
    resp = bridge.place_market_order('NEARUSDT', close_side, close_qty)
    print(f"Exchange Response: {resp}")
    
    # Verify balance after closing
    new_bal = bridge.get_balance()
    print(f"\nNew Wallet Balance: ${new_bal:,.4f} USDT")
    print("="*65)

import os
import sys
import time
import datetime
from state_manager import StateManager
from config import EXECUTION_ENV, CAPITAL_MODE, ORDER_EXECUTION_MODE

def format_row(label, val, width=35):
    return f"  {label:<30} : {val}"

def run_dashboard():
    state = StateManager()
    
    while True:
        try:
            stats = state.get_summary_stats()
            ex_bal = stats['exchange_balance']
            init_bal = stats['initial_balance']
            cash_bal = stats['cash_balance']
            equity = stats['total_equity']
            net_pnl = stats['net_pnl']
            roi = stats['roi_pct']
            exp = stats['gross_exposure']
            lev = stats['portfolio_leverage']
            closed = stats['total_closed_trades']
            wr = stats['win_rate']
            pf = stats['profit_factor']
            fees = stats['total_fees']
            funding = stats['total_funding']
            open_pos = stats['open_positions']
            
            # Clear terminal
            os.system('cls' if os.name == 'nt' else 'clear')
            
            now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            
            print("="*75)
            print(f"             TAMA ENGINE — 24/7 AUTONOMOUS LIVE MONITOR")
            print(f"             System Time: {now_utc}")
            print(f"             Env: {EXECUTION_ENV} | Execution: {ORDER_EXECUTION_MODE} | Mode: {CAPITAL_MODE}")
            print("="*75)
            
            print("\n[EXCHANGE MARGIN & CAPITAL LEDGER]")
            print(format_row("Live Exchange Wallet Balance", f"${ex_bal:,.2f} USDT"))
            print(format_row("Strategy Working Capital (Base)", f"${init_bal:,.2f} USDT"))
            print(format_row("Current Working Cash Balance", f"${cash_bal:,.2f} USDT"))
            print(format_row("Current Strategy Total Equity", f"${equity:,.2f} USDT"))
            print(format_row("Total Realized Net PnL", f"${net_pnl:+,.2f} ({roi:+,.2f}%)"))
            print(format_row("Current Gross Exposure", f"${exp:,.2f}"))
            print(format_row("Portfolio Leverage", f"{lev:.3f}x / 3.000x Max Cap"))
            
            print("\n[HISTORICAL PERFORMANCE & FRICTION METRICS]")
            print(format_row("Total Closed Trades", f"{closed:,}"))
            print(format_row("Win Rate", f"{wr:.2f}%"))
            print(format_row("Profit Factor", f"{pf:.3f}"))
            print(format_row("Total Trading Fees Paid", f"${fees:,.2f}"))
            print(format_row("Total Funding Paid", f"${funding:,.2f}"))
            
            print("\n[ACTIVE OPEN POSITIONS (" + str(len(open_pos)) + "/5)]")
            if not open_pos:
                print("  No active positions currently open. Engine scanning 15m candle closes...")
            else:
                print(f"  {'Symbol':<10} {'Side':<6} {'Qty':<10} {'Entry Price':<12} {'Notional':<10} {'Stop Loss':<12}")
                print("  " + "-"*65)
                for p in open_pos:
                    print(f"  {p['symbol']:<10} {p['side']:<6} {p['qty']:<10.4f} ${p['entry_price']:<11.2f} ${p['notional']:<9.2f} ${p['stop_loss']:<11.2f}")
            
            print("\n" + "="*75)
            print("  Press Ctrl+C to exit dashboard view (Bot continues running in background)")
            print("="*75)
            
            time.sleep(2.0)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Dashboard error: {e}")
            time.sleep(2.0)

if __name__ == "__main__":
    run_dashboard()

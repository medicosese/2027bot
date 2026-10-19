import sys
import os
import sqlite3
import datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(r"F:\dr tanveer trdaing\tama_live_bot")
from config import DB_PATH, DATA_DIR

STARTING_BALANCE = 1019.7846

print("="*65)
print("INITIALIZING FRESH CLEAN STATE DATABASE FOR TAMA LIVE BOT")
print(f"Target DB: {DB_PATH}")
print(f"Verified Starting Margin Balance: ${STARTING_BALANCE:,.4f} USDT")
print("="*65)

# Backup old db if exists
if os.path.exists(DB_PATH):
    backup_path = DB_PATH.replace(".db", f"_backup_{int(datetime.datetime.now().timestamp())}.db")
    try:
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"Backed up previous state DB to: {os.path.basename(backup_path)}")
    except Exception as e:
        print(f"Backup warning: {e}")

# Remove or clean db
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

from state_manager import StateManager
sm = StateManager()

sm.sync_capital_state(
    exchange_balance=STARTING_BALANCE,
    working_capital=STARTING_BALANCE,
    env="TESTNET",
    capital_mode="EXCHANGE_DYNAMIC"
)

summary = sm.get_summary_stats()
print("\nVerified DB State Summary:")
for k, v in summary.items():
    print(f"  {k:<25}: {v}")
print("="*65)

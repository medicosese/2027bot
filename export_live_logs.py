import os
import sqlite3
import pandas as pd
from config import DB_PATH, DATA_DIR

def export_logs():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return
        
    conn = sqlite3.connect(DB_PATH)
    
    # Export Trades
    trades_df = pd.read_sql_query("SELECT * FROM trades ORDER BY rowid ASC", conn)
    trades_csv = os.path.join(DATA_DIR, "live_trades.csv")
    trades_df.to_csv(trades_csv, index=False)
    print(f"Exported {len(trades_df)} trades to: {trades_csv}")
    
    # Export Events
    events_df = pd.read_sql_query("SELECT * FROM events ORDER BY rowid ASC", conn)
    events_csv = os.path.join(DATA_DIR, "live_events.csv")
    events_df.to_csv(events_csv, index=False)
    print(f"Exported {len(events_df)} events to: {events_csv}")
    
    # Export Snapshots
    snaps_df = pd.read_sql_query("SELECT * FROM account_snapshots ORDER BY rowid ASC", conn)
    snaps_csv = os.path.join(DATA_DIR, "live_snapshots.csv")
    snaps_df.to_csv(snaps_csv, index=False)
    print(f"Exported {len(snaps_df)} snapshots to: {snaps_csv}")
    
    conn.close()

if __name__ == "__main__":
    export_logs()

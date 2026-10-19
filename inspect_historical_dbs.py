import sqlite3
import os
import glob

db_files = [
    r"F:\dr tanveer trdaing\aws cloud v27\v27_bot_state_live_current.db",
    r"F:\dr tanveer trdaing\aws cloud v27\v27_bot_state_live_today_3.db",
    r"F:\dr tanveer trdaing\glm_15m_live_bot\v27_aws_state_july24_night.db",
    r"F:\dr tanveer trdaing\glm_15m_live_bot\v27_aws_state_latest.db",
    r"F:\dr tanveer trdaing\glm_15m_live_bot\v27_aws_state.db"
]

for db in db_files:
    if not os.path.exists(db):
        continue
    print("="*75)
    print(f"DATABASE: {os.path.basename(db)}")
    print("="*75)
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        
        # List tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"  Tables: {tables}")
        
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            cnt = cur.fetchone()[0]
            print(f"    Table {t}: {cnt} rows")
            if cnt > 0:
                cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 3")
                sample = cur.fetchall()
                # Get column names
                cur.execute(f"PRAGMA table_info({t})")
                cols = [c[1] for c in cur.fetchall()]
                print(f"      Columns: {cols}")
                for row in sample:
                    print(f"      Sample Row: {dict(zip(cols, row))}")
        conn.close()
    except Exception as e:
        print(f"  Error reading {db}: {e}")

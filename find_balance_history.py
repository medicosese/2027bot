import sqlite3
import glob
import os
import re

print("="*75)
print("SEARCHING HISTORICAL DATABASES AND LOGS FOR ACCOUNT BALANCE RECORDS")
print("="*75)

# 1. Search SQLite databases
dbs = glob.glob(r"F:\dr tanveer trdaing\**\*.db", recursive=True)
for d in dbs:
    try:
        conn = sqlite3.connect(d)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        for t in tables:
            cur.execute(f"PRAGMA table_info({t})")
            cols = [c[1].lower() for c in cur.fetchall()]
            if any('balance' in c or 'wallet' in c or 'equity' in c or 'capital' in c for c in cols):
                cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 5")
                rows = cur.fetchall()
                print(f"\n[DB: {os.path.basename(d)} | Table: {t}]")
                print(f"  Columns: {cols}")
                for r in rows:
                    print(f"  Row: {r}")
        conn.close()
    except Exception as e:
        pass

# 2. Search log files and markdown reports for balance keywords
log_files = glob.glob(r"F:\dr tanveer trdaing\**\*.log", recursive=True) + \
            glob.glob(r"F:\dr tanveer trdaing\**\*.txt", recursive=True) + \
            glob.glob(r"F:\dr tanveer trdaing\**\*.md", recursive=True)

print("\n" + "="*75)
print("SEARCHING TEXT/LOG FILES FOR BALANCE / CAPITAL VALUES")
print("="*75)

balance_pattern = re.compile(r"(initial[_\s]balance|wallet[_\s]balance|account[_\s]balance|balance\s*[:=]\s*\$?[0-9]+|capital\s*[:=]\s*\$?[0-9]+)", re.IGNORECASE)

found_snippets = set()
for lf in log_files:
    if os.path.getsize(lf) > 5 * 1024 * 1024:
        continue
    try:
        with open(lf, 'r', encoding='utf-8', errors='ignore') as f:
            for line_no, line in enumerate(f, 1):
                if balance_pattern.search(line):
                    snip = f"{os.path.basename(lf)}:{line_no} -> {line.strip()}"
                    if snip not in found_snippets:
                        found_snippets.add(snip)
                        if len(found_snippets) <= 25:
                            print(snip)
    except Exception as e:
        pass

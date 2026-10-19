import subprocess
import time
import sys
import datetime
import os

print("="*70)
print(f"TAMA WATCHDOG SUPERVISOR DAEMON STARTED")
print(f"Timestamp: {datetime.datetime.now(datetime.timezone.utc)}")
print("="*70)

script_dir = os.path.dirname(os.path.abspath(__file__))
engine_script = os.path.join(script_dir, "tama_engine.py")

while True:
    print(f"\n[{datetime.datetime.now(datetime.timezone.utc)}] Launching TAMA Live Engine...")
    try:
        proc = subprocess.Popen([sys.executable, "-u", engine_script], cwd=script_dir)
        proc.wait()
        exit_code = proc.returncode
        print(f"[{datetime.datetime.now(datetime.timezone.utc)}] Engine exited with code {exit_code}.")
    except Exception as e:
        print(f"[{datetime.datetime.now(datetime.timezone.utc)}] Watchdog caught exception: {e}")
        
    print("Restarting engine in 5 seconds...")
    time.sleep(5.0)

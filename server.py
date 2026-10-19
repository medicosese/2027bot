import os
import sys
import time
import json
import threading
import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tama_engine import TamaLiveEngine
from state_manager import StateManager
from config import EXECUTION_ENV, CAPITAL_MODE, ORDER_EXECUTION_MODE, SYMBOLS

PORT = int(os.getenv("PORT", "8080"))

class TamaHealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy HTTP request logs
        return

    def do_GET(self):
        try:
            sm = StateManager()
            stats = sm.get_summary_stats()
            now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            payload = {
                "status": "HEALTHY_ONLINE",
                "system_time": now_utc,
                "environment": EXECUTION_ENV,
                "capital_mode": CAPITAL_MODE,
                "order_execution_mode": ORDER_EXECUTION_MODE,
                "monitored_universe": SYMBOLS,
                "account_metrics": {
                    "exchange_wallet_balance_usdt": stats.get("exchange_balance", 0.0),
                    "strategy_working_equity_usdt": stats.get("total_equity", 0.0),
                    "cash_balance_usdt": stats.get("cash_balance", 0.0),
                    "realized_net_pnl_usdt": stats.get("net_pnl", 0.0),
                    "roi_pct": stats.get("roi_pct", 0.0),
                    "portfolio_leverage": stats.get("portfolio_leverage", 0.0),
                    "gross_exposure_usdt": stats.get("gross_exposure", 0.0)
                },
                "performance_metrics": {
                    "total_closed_trades": stats.get("total_closed_trades", 0),
                    "win_rate_pct": stats.get("win_rate", 0.0),
                    "profit_factor": stats.get("profit_factor", 0.0),
                    "total_fees_paid_usdt": stats.get("total_fees", 0.0),
                    "total_funding_paid_usdt": stats.get("total_funding", 0.0)
                },
                "active_open_positions": stats.get("open_positions", [])
            }
            
            body = json.dumps(payload, indent=2).encode('utf-8')
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Internal Server Error: {e}".encode('utf-8'))

def run_http_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, TamaHealthHandler)
    print(f"[HTTP SERVER] Listening for health checks & monitor pings on port {PORT}...")
    httpd.serve_forever()

def start_cloud_runner():
    print("="*75)
    print("STARTING TAMA LIVE CLOUD RUNNER (CONTAINERIZED / 24/7 PAAS)")
    print(f"Timestamp: {datetime.datetime.now(datetime.timezone.utc)}")
    print(f"Port: {PORT}")
    print("="*75)
    
    # 1. Start HTTP Health & Monitor server in background thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    # 2. Start TAMA Live Trading Engine
    engine = TamaLiveEngine()
    engine.start()

if __name__ == "__main__":
    start_cloud_runner()

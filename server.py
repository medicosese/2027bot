import os
import sys
import time
import glob
import json
import threading
import datetime
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tama_engine import TamaLiveEngine
from state_manager import StateManager
from config import (
    EXECUTION_ENV, CAPITAL_MODE, ORDER_EXECUTION_MODE, SYMBOLS,
    LOGS_DIR, ACTIVE_API_KEY, ACTIVE_API_SECRET
)

PORT = int(os.getenv("PORT", "8080"))
GLOBAL_ENGINE: Optional[TamaLiveEngine] = None

class TamaHealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy HTTP request logs
        return

    def do_GET(self):
        try:
            if self.path == "/logs":
                self._handle_logs()
                return

            sm = StateManager()
            stats = sm.get_summary_stats()
            now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # Extract live engine telemetry if active
            ws_live = bool(GLOBAL_ENGINE and GLOBAL_ENGINE.running)
            bridge_live = bool(GLOBAL_ENGINE and GLOBAL_ENGINE.bridge is not None)
            kline_count = GLOBAL_ENGINE.kline_messages_received if GLOBAL_ENGINE else 0
            last_kline = GLOBAL_ENGINE.last_kline_time if GLOBAL_ENGINE else None
            live_prices = dict(GLOBAL_ENGINE.latest_prices) if GLOBAL_ENGINE else {}
            pending = {s: o for s, o in GLOBAL_ENGINE.pending_orders.items() if o is not None} if GLOBAL_ENGINE else {}
            ex_bal = GLOBAL_ENGINE.exchange_balance if GLOBAL_ENGINE and GLOBAL_ENGINE.exchange_balance > 0 else stats.get("exchange_balance", 0.0)
            
            payload = {
                "status": "HEALTHY_ONLINE",
                "system_time": now_utc,
                "environment": EXECUTION_ENV,
                "capital_mode": CAPITAL_MODE,
                "order_execution_mode": ORDER_EXECUTION_MODE,
                "monitored_universe": SYMBOLS,
                "telemetry": {
                    "websocket_connected": ws_live,
                    "api_bridge_connected": bridge_live,
                    "kline_messages_received": kline_count,
                    "last_kline_timestamp": last_kline,
                    "staged_pending_orders_count": len(pending)
                },
                "account_metrics": {
                    "exchange_wallet_balance_usdt": ex_bal,
                    "strategy_working_equity_usdt": stats.get("total_equity", 0.0),
                    "cash_balance_usdt": stats.get("cash_balance", 0.0),
                    "realized_net_pnl_usdt": stats.get("net_pnl", 0.0),
                    "roi_pct": stats.get("roi_pct", 0.0),
                    "portfolio_leverage": stats.get("portfolio_leverage", 0.0),
                    "gross_exposure_usdt": stats.get("gross_exposure", 0.0)
                },
                "market_state": {
                    "latest_prices": live_prices,
                    "pending_orders": pending,
                    "active_open_positions": stats.get("open_positions", [])
                },
                "performance_metrics": {
                    "total_closed_trades": stats.get("total_closed_trades", 0),
                    "win_rate_pct": stats.get("win_rate", 0.0),
                    "profit_factor": stats.get("profit_factor", 0.0),
                    "total_fees_paid_usdt": stats.get("total_fees", 0.0),
                    "total_funding_paid_usdt": stats.get("total_funding", 0.0)
                }
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

    def _handle_logs(self):
        try:
            log_files = glob.glob(os.path.join(LOGS_DIR, "tama_live_*.log"))
            if not log_files:
                output = "No log files found in logs directory."
            else:
                latest_log = max(log_files, key=os.path.getmtime)
                with open(latest_log, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                last_lines = lines[-60:] if len(lines) > 60 else lines
                output = f"=== TAMA LIVE BOT LOG TAIL ({os.path.basename(latest_log)}) ===\n" + "".join(last_lines)
            body = output.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error fetching logs: {e}".encode('utf-8'))

def run_http_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, TamaHealthHandler)
    print(f"[HTTP SERVER] Listening for health checks & monitor pings on port {PORT}...")
    httpd.serve_forever()

def start_cloud_runner():
    global GLOBAL_ENGINE
    print("="*75)
    print("STARTING TAMA LIVE CLOUD RUNNER (CONTAINERIZED / 24/7 PAAS)")
    print(f"Timestamp: {datetime.datetime.now(datetime.timezone.utc)}")
    print(f"Port: {PORT}")
    print("="*75)
    
    # 1. Start HTTP Health & Monitor server in background thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    # 2. Start TAMA Live Trading Engine
    GLOBAL_ENGINE = TamaLiveEngine()
    GLOBAL_ENGINE.start()

if __name__ == "__main__":
    start_cloud_runner()

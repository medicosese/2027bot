import os
import sqlite3
import datetime
import threading
import pandas as pd
from typing import Dict, List, Optional, Any
from config import (
    DB_PATH, DATA_DIR, RISK_PER_TRADE, MAX_PORTFOLIO_LEVERAGE,
    EXECUTION_ENV, CAPITAL_MODE, ALLOCATED_BUDGET
)

class StateManager:
    """Thread-safe SQLite State Manager and Double-Entry Event Ledger for TAMA Live Bot."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.lock = threading.Lock()
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.lock:
            conn = self._get_connection()
            cur = conn.cursor()
            
            # 1. Config Metadata
            cur.execute("""
            CREATE TABLE IF NOT EXISTS config_meta (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
            """)
            
            # 2. Account Snapshots
            cur.execute("""
            CREATE TABLE IF NOT EXISTS account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cash_balance REAL NOT NULL,
                total_equity REAL NOT NULL,
                margin_used REAL NOT NULL,
                unrealized_pnl REAL NOT NULL,
                gross_exposure REAL NOT NULL,
                portfolio_leverage REAL NOT NULL,
                open_positions_count INTEGER NOT NULL
            )
            """)
            
            # 3. Trades Ledger
            cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                status TEXT NOT NULL, -- 'OPEN' or 'CLOSED'
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                entry_price REAL NOT NULL,
                exit_price REAL,
                qty REAL NOT NULL,
                notional REAL NOT NULL,
                stop_loss REAL NOT NULL,
                entry_fee REAL NOT NULL,
                exit_fee REAL DEFAULT 0.0,
                cum_funding REAL DEFAULT 0.0,
                gross_pnl REAL DEFAULT 0.0,
                net_pnl REAL DEFAULT 0.0,
                balance_after REAL,
                bars_held INTEGER DEFAULT 0,
                is_intrabar INTEGER DEFAULT 0,
                exit_reason TEXT
            )
            """)
            
            # 4. Granular Event Ledger
            cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL, -- 'INITIAL_DEPOSIT', 'BALANCE_SYNC', 'ORDER_STAGED', 'ORDER_ENTRY', 'FUNDING_FEE', 'TRAILING_UPDATE', 'ORDER_EXIT'
                trade_id TEXT,
                symbol TEXT,
                side TEXT,
                price REAL,
                qty REAL,
                notional REAL,
                fee REAL DEFAULT 0.0,
                funding REAL DEFAULT 0.0,
                realized_pnl REAL DEFAULT 0.0,
                cash_balance REAL NOT NULL,
                total_equity REAL NOT NULL,
                gross_exposure REAL NOT NULL,
                portfolio_leverage REAL NOT NULL,
                message TEXT
            )
            """)
            conn.commit()
            conn.close()

    def sync_capital_state(self, exchange_balance: float, working_capital: float, env: str, capital_mode: str):
        """Records verified initial capital from exchange and working test budget."""
        with self.lock:
            conn = self._get_connection()
            cur = conn.cursor()
            now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            cur.execute("INSERT OR REPLACE INTO config_meta (key, value, updated_at) VALUES ('exchange_wallet_balance', ?, ?)", (str(exchange_balance), now_str))
            cur.execute("INSERT OR REPLACE INTO config_meta (key, value, updated_at) VALUES ('working_capital', ?, ?)", (str(working_capital), now_str))
            cur.execute("INSERT OR REPLACE INTO config_meta (key, value, updated_at) VALUES ('initial_balance', ?, ?)", (str(working_capital), now_str))
            cur.execute("INSERT OR REPLACE INTO config_meta (key, value, updated_at) VALUES ('environment', ?, ?)", (env, now_str))
            cur.execute("INSERT OR REPLACE INTO config_meta (key, value, updated_at) VALUES ('capital_mode', ?, ?)", (capital_mode, now_str))
            
            # Check if an initial deposit event already exists
            cur.execute("SELECT COUNT(*) FROM events WHERE event_type IN ('INITIAL_DEPOSIT', 'BALANCE_SYNC')")
            if cur.fetchone()[0] == 0:
                cur.execute("""
                INSERT INTO events (
                    event_id, timestamp, event_type, trade_id, symbol, side, price, qty, notional,
                    fee, funding, realized_pnl, cash_balance, total_equity, gross_exposure, portfolio_leverage, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "EVT-0000000", now_str, "BALANCE_SYNC", "NONE", "ACCOUNT", "NONE", 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, working_capital, working_capital, 0.0, 0.0,
                    f"Initialized {capital_mode} with ${working_capital:,.2f} working capital (Exchange Wallet: ${exchange_balance:,.2f} USDT on {env})"
                ))
                
                cur.execute("""
                INSERT INTO account_snapshots (
                    timestamp, cash_balance, total_equity, margin_used, unrealized_pnl,
                    gross_exposure, portfolio_leverage, open_positions_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (now_str, working_capital, working_capital, 0.0, 0.0, 0.0, 0.0, 0))
                
            conn.commit()
            conn.close()

    def get_initial_balance(self) -> float:
        with self.lock:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT value FROM config_meta WHERE key = 'initial_balance'")
            row = cur.fetchone()
            conn.close()
            return float(row[0]) if row else ALLOCATED_BUDGET

    def get_latest_cash_balance(self) -> float:
        with self.lock:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT cash_balance FROM events ORDER BY rowid DESC LIMIT 1")
            row = cur.fetchone()
            conn.close()
            return float(row[0]) if row else ALLOCATED_BUDGET

    def record_event(self, event_type: str, trade_id: str, symbol: str, side: str,
                     price: float, qty: float, notional: float, fee: float, funding: float,
                     realized_pnl: float, cash_balance: float, total_equity: float,
                     gross_exposure: float, portfolio_leverage: float, message: str = ""):
        with self.lock:
            conn = self._get_connection()
            cur = conn.cursor()
            now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            cur.execute("SELECT COUNT(*) FROM events")
            next_id = cur.fetchone()[0]
            evt_id = f"EVT-{next_id:07d}"
            
            cur.execute("""
            INSERT INTO events (
                event_id, timestamp, event_type, trade_id, symbol, side, price, qty, notional,
                fee, funding, realized_pnl, cash_balance, total_equity, gross_exposure, portfolio_leverage, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evt_id, now_str, event_type, trade_id, symbol, side, price, qty, notional,
                fee, funding, realized_pnl, cash_balance, total_equity, gross_exposure, portfolio_leverage, message
            ))
            conn.commit()
            conn.close()

    def record_trade_entry(self, trade_dict: Dict[str, Any]):
        with self.lock:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO trades (
                trade_id, symbol, side, status, entry_time, entry_price, qty, notional,
                stop_loss, entry_fee, bars_held
            ) VALUES (?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, 0)
            """, (
                trade_dict['trade_id'], trade_dict['symbol'], trade_dict['side'],
                trade_dict['entry_time'], trade_dict['entry_price'], trade_dict['qty'],
                trade_dict['notional'], trade_dict['stop_loss'], trade_dict['entry_fee']
            ))
            conn.commit()
            conn.close()

    def update_trade_funding(self, trade_id: str, funding_cost: float):
        with self.lock:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
            UPDATE trades SET cum_funding = cum_funding + ? WHERE trade_id = ?
            """, (funding_cost, trade_id))
            conn.commit()
            conn.close()

    def record_trade_exit(self, exit_dict: Dict[str, Any]):
        with self.lock:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
            UPDATE trades SET
                status = 'CLOSED',
                exit_time = ?,
                exit_price = ?,
                exit_fee = ?,
                gross_pnl = ?,
                net_pnl = ?,
                balance_after = ?,
                bars_held = ?,
                is_intrabar = ?,
                exit_reason = ?
            WHERE trade_id = ?
            """, (
                exit_dict['exit_time'], exit_dict['exit_price'], exit_dict['exit_fee'],
                exit_dict['gross_pnl'], exit_dict['net_pnl'], exit_dict['balance_after'],
                exit_dict['bars_held'], 1 if exit_dict.get('is_intrabar') else 0,
                exit_dict['exit_reason'], exit_dict['trade_id']
            ))
            conn.commit()
            conn.close()

    def record_snapshot(self, cash_balance: float, total_equity: float, margin_used: float,
                        unrealized_pnl: float, gross_exposure: float, portfolio_leverage: float,
                        open_count: int):
        with self.lock:
            conn = self._get_connection()
            cur = conn.cursor()
            now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cur.execute("""
            INSERT INTO account_snapshots (
                timestamp, cash_balance, total_equity, margin_used, unrealized_pnl,
                gross_exposure, portfolio_leverage, open_positions_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now_str, cash_balance, total_equity, margin_used, unrealized_pnl,
                gross_exposure, portfolio_leverage, open_count
            ))
            conn.commit()
            conn.close()

    def get_summary_stats(self) -> Dict[str, Any]:
        with self.lock:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT value FROM config_meta WHERE key = 'initial_balance'")
            row_ib = cur.fetchone()
            init_val = float(row_ib[0]) if row_ib else ALLOCATED_BUDGET
            
            cur.execute("SELECT value FROM config_meta WHERE key = 'exchange_wallet_balance'")
            row_ex = cur.fetchone()
            ex_val = float(row_ex[0]) if row_ex else init_val
            
            cur.execute("SELECT cash_balance, total_equity, gross_exposure, portfolio_leverage FROM events ORDER BY rowid DESC LIMIT 1")
            latest_ev = cur.fetchone()
            curr_cash = float(latest_ev[0]) if latest_ev else init_val
            curr_eq = float(latest_ev[1]) if latest_ev else init_val
            curr_exp = float(latest_ev[2]) if latest_ev else 0.0
            curr_lev = float(latest_ev[3]) if latest_ev else 0.0
            
            cur.execute("SELECT COUNT(*), SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END), SUM(gross_pnl), SUM(entry_fee + exit_fee), SUM(cum_funding), SUM(net_pnl) FROM trades WHERE status = 'CLOSED'")
            row = cur.fetchone()
            total_closed = row[0] or 0
            wins = row[1] or 0
            gross_pnl = row[2] or 0.0
            fees = row[3] or 0.0
            funding = row[4] or 0.0
            net_pnl = row[5] or 0.0
            
            cur.execute("SELECT SUM(net_pnl) FROM trades WHERE status = 'CLOSED' AND net_pnl > 0")
            gw = cur.fetchone()[0] or 0.0
            cur.execute("SELECT ABS(SUM(net_pnl)) FROM trades WHERE status = 'CLOSED' AND net_pnl <= 0")
            gl = cur.fetchone()[0] or 0.0
            pf = (gw / gl) if gl > 0 else (99.0 if gw > 0 else 0.0)
            wr = (wins / total_closed * 100.0) if total_closed > 0 else 0.0
            
            # Active positions
            cur.execute("SELECT * FROM trades WHERE status = 'OPEN'")
            open_trades = [dict(r) for r in cur.fetchall()]
            
            conn.close()
            
            return {
                'exchange_balance': ex_val,
                'initial_balance': init_val,
                'cash_balance': curr_cash,
                'total_equity': curr_eq,
                'gross_exposure': curr_exp,
                'portfolio_leverage': curr_lev,
                'net_pnl': net_pnl,
                'roi_pct': ((curr_eq - init_val) / init_val) * 100.0 if init_val > 0 else 0.0,
                'total_closed_trades': total_closed,
                'win_rate': wr,
                'profit_factor': pf,
                'total_fees': fees,
                'total_funding': funding,
                'open_positions': open_trades
            }

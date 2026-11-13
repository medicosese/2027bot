import os
import sys
import time
import json
import logging
import datetime
import threading
import requests
import websocket
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any

from config import (
    SYMBOLS, RISK_PER_TRADE, MAX_PORTFOLIO_LEVERAGE,
    LEVERAGE_HEADROOM_CAP, COOLDOWN_BARS, FILL_PENETRATION_ATR, MIN_NOTIONAL,
    MAX_NOTIONAL_CAP, MAKER_FEE_RATE, TAKER_FEE_RATE, BASE_FUNDING_RATE,
    SLIPPAGE_MAP, TIMEFRAME, ATR_PERIOD, ADX_PERIOD, ADX_THRESHOLD,
    EMA_FAST, EMA_SLOW, SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER, WARMUP_BARS,
    LOGS_DIR, EXECUTION_ENV, ORDER_EXECUTION_MODE, CAPITAL_MODE,
    ALLOCATED_BUDGET, ACTIVE_API_KEY, ACTIVE_API_SECRET, USE_TESTNET
)
from state_manager import StateManager
from binance_trade_bridge import BinanceTradeBridge

# Setup Logging
os.makedirs(LOGS_DIR, exist_ok=True)
log_file = os.path.join(LOGS_DIR, f"tama_live_{datetime.datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("TAMA_ENGINE")

class TamaLiveEngine:
    def __init__(self):
        self.state = StateManager()
        self.running = False
        
        # Initialize Exchange Bridge
        self.bridge = None
        if ACTIVE_API_KEY and ACTIVE_API_SECRET:
            self.bridge = BinanceTradeBridge(ACTIVE_API_KEY, ACTIVE_API_SECRET, use_testnet=USE_TESTNET)
            logger.info(f"Initialized Binance Trade Bridge for {EXECUTION_ENV} environment.")
        else:
            logger.info("Running in local shadow mode without exchange API credentials.")
            
        # Discover and Synchronize Account Capital
        self.exchange_balance = 0.0
        self.working_capital = ALLOCATED_BUDGET
        self._sync_initial_capital()
        
        # In-memory indicator & bar cache
        self.bars: Dict[str, pd.DataFrame] = {}
        self.positions: Dict[str, Optional[Dict[str, Any]]] = {s: None for s in SYMBOLS}
        self.pending_orders: Dict[str, Optional[Dict[str, Any]]] = {s: None for s in SYMBOLS}
        self.last_exit_bar: Dict[str, int] = {s: -999 for s in SYMBOLS}
        self.bar_index: Dict[str, int] = {s: 0 for s in SYMBOLS}
        self.latest_prices: Dict[str, float] = {s: 0.0 for s in SYMBOLS}
        self.last_kline_time: Optional[str] = None
        self.kline_messages_received: int = 0
        self.unrealized_pnl: float = 0.0
        self.total_margin_balance: float = 0.0
        
        # Recover open positions from SQLite if resuming
        self._recover_state()
        
    def _sync_initial_capital(self):
        """Discovers exact balance from Binance API and sets working capital."""
        if self.bridge:
            try:
                b = self.bridge.get_balance()
                if b is not None and b > 0:
                    self.exchange_balance = float(b)
                    logger.info(f"Verified Live Binance Balance: ${self.exchange_balance:,.2f} USDT on {EXECUTION_ENV}")
                else:
                    logger.warning("Could not fetch balance from exchange API; falling back to allocated budget.")
                    self.exchange_balance = ALLOCATED_BUDGET
            except Exception as e:
                logger.error(f"Error querying balance from exchange: {e}")
                self.exchange_balance = ALLOCATED_BUDGET
        else:
            self.exchange_balance = ALLOCATED_BUDGET
            
        if CAPITAL_MODE == "EXCHANGE_DYNAMIC":
            self.working_capital = self.exchange_balance
            logger.info(f"Capital Mode: EXCHANGE_DYNAMIC -> Working Capital set to ${self.working_capital:,.2f} USDT")
        else:
            self.working_capital = ALLOCATED_BUDGET
            logger.info(f"Capital Mode: ALLOCATED_SANDBOX -> Pinned Working Capital to ${self.working_capital:,.2f} USDT (Exchange has ${self.exchange_balance:,.2f})")
            
        # Record into SQLite
        self.state.sync_capital_state(
            exchange_balance=self.exchange_balance,
            working_capital=self.working_capital,
            env=EXECUTION_ENV,
            capital_mode=CAPITAL_MODE
        )
        
    def _recover_state(self):
        summary = self.state.get_summary_stats()
        open_pos = summary['open_positions']
        for p in open_pos:
            s = p['symbol']
            self.positions[s] = {
                'trade_id': p['trade_id'],
                'symbol': s,
                'side': p['side'],
                'entry_time': p['entry_time'],
                'entry_price': p['entry_price'],
                'qty': p['qty'],
                'notional': p['notional'],
                'sl': p['stop_loss'],
                'entry_fee': p['entry_fee'],
                'cum_funding': p['cum_funding'],
                'bars_held': p['bars_held'],
                'exchange_order_id': None,
                'stop_order_id': None
            }
            logger.info(f"Recovered active position from DB: {s} {p['side']} {p['qty']} @ ${p['entry_price']:.2f}")

    def fetch_warmup_candles(self, symbol: str, limit: int = WARMUP_BARS) -> pd.DataFrame:
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {"symbol": symbol, "interval": TIMEFRAME, "limit": limit}
        for attempt in range(5):
            try:
                r = requests.get(url, params=params, timeout=10)
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    rows = []
                    for row in data:
                        rows.append({
                            'timestamp': int(row[0]),
                            'open': float(row[1]),
                            'high': float(row[2]),
                            'low': float(row[3]),
                            'close': float(row[4]),
                            'volume': float(row[5])
                        })
                    df = pd.DataFrame(rows)
                    return df
            except Exception as e:
                logger.warning(f"Error fetching warmup for {symbol} (attempt {attempt+1}): {e}")
                time.sleep(1.0)
        raise RuntimeError(f"Failed to fetch warmup candles for {symbol}")

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        high = df['high'].values.astype(np.float64)
        low = df['low'].values.astype(np.float64)
        close = df['close'].values.astype(np.float64)
        n = len(df)
        
        # 1. ATR (Wilder's 14)
        tr = np.zeros(n, dtype=np.float64)
        tr[0] = high[0] - low[0]
        for i in range(1, n):
            tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        atr = np.zeros(n, dtype=np.float64)
        atr[ATR_PERIOD-1] = np.mean(tr[:ATR_PERIOD])
        for i in range(ATR_PERIOD, n):
            atr[i] = (atr[i-1] * (ATR_PERIOD - 1) + tr[i]) / ATR_PERIOD
            
        # 2. ADX (14)
        up_move = high[1:] - high[:-1]
        down_move = low[:-1] - low[1:]
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        plus_di = np.zeros(n, dtype=np.float64)
        minus_di = np.zeros(n, dtype=np.float64)
        dx = np.zeros(n, dtype=np.float64)
        adx = np.zeros(n, dtype=np.float64)
        
        if n >= ADX_PERIOD * 2:
            pdm_smooth = np.zeros(n, dtype=np.float64)
            mdm_smooth = np.zeros(n, dtype=np.float64)
            pdm_smooth[ADX_PERIOD] = np.sum(plus_dm[:ADX_PERIOD])
            mdm_smooth[ADX_PERIOD] = np.sum(minus_dm[:ADX_PERIOD])
            
            for i in range(ADX_PERIOD + 1, n):
                pdm_smooth[i] = pdm_smooth[i-1] - (pdm_smooth[i-1] / ADX_PERIOD) + plus_dm[i-1]
                mdm_smooth[i] = mdm_smooth[i-1] - (mdm_smooth[i-1] / ADX_PERIOD) + minus_dm[i-1]
                
            for i in range(ADX_PERIOD, n):
                if atr[i] > 0:
                    plus_di[i] = 100.0 * (pdm_smooth[i] / (atr[i] * ADX_PERIOD))
                    minus_di[i] = 100.0 * (mdm_smooth[i] / (atr[i] * ADX_PERIOD))
                    di_sum = plus_di[i] + minus_di[i]
                    if di_sum > 0:
                        dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / di_sum
                        
            start_adx = ADX_PERIOD * 2 - 1
            if start_adx < n:
                adx[start_adx] = np.mean(dx[ADX_PERIOD:start_adx+1])
                for i in range(start_adx + 1, n):
                    adx[i] = (adx[i-1] * (ADX_PERIOD - 1) + dx[i]) / ADX_PERIOD
                    
        # 3. EMA 50 & EMA 200
        ema50 = pd.Series(close).ewm(span=EMA_FAST, adjust=False).mean().values
        ema200 = pd.Series(close).ewm(span=EMA_SLOW, adjust=False).mean().values
        
        # 4. Supertrend (10, 2.5)
        st = np.zeros(n, dtype=np.float64)
        st_dir = np.zeros(n, dtype=np.int32)
        hl2 = (high + low) / 2.0
        upper_band = hl2 + (SUPERTREND_MULTIPLIER * atr)
        lower_band = hl2 - (SUPERTREND_MULTIPLIER * atr)
        
        final_upper = np.copy(upper_band)
        final_lower = np.copy(lower_band)
        st_dir[0] = 1
        st[0] = final_lower[0]
        
        for i in range(1, n):
            if lower_band[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
                final_lower[i] = lower_band[i]
            else:
                final_lower[i] = final_lower[i-1]
                
            if upper_band[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
                final_upper[i] = upper_band[i]
            else:
                final_upper[i] = final_upper[i-1]
                
            if st_dir[i-1] == 1:
                if close[i] < final_lower[i]:
                    st_dir[i] = -1
                    st[i] = final_upper[i]
                else:
                    st_dir[i] = 1
                    st[i] = final_lower[i]
            else:
                if close[i] > final_upper[i]:
                    st_dir[i] = 1
                    st[i] = final_lower[i]
                else:
                    st_dir[i] = -1
                    st[i] = final_upper[i]
                    
        df['atr'] = atr
        df['adx'] = adx
        df['ema50'] = ema50
        df['ema200'] = ema200
        df['st'] = st
        df['st_dir'] = st_dir
        return df

    def initialize_warmup(self):
        logger.info(f"Initializing 250 warmup bars for trading universe: {SYMBOLS}...")
        for sym in SYMBOLS:
            df = self.fetch_warmup_candles(sym, limit=WARMUP_BARS)
            df = self.compute_indicators(df)
            self.bars[sym] = df
            self.bar_index[sym] = len(df)
            self.latest_prices[sym] = df['close'].iloc[-1]
            logger.info(f"[{sym}] Loaded {len(df)} bars. Last Close: ${df['close'].iloc[-1]:,.2f} | ST: ${df['st'].iloc[-1]:,.2f} (Dir: {df['st_dir'].iloc[-1]})")

    def on_tick_price(self, symbol: str, price: float, high: float, low: float):
        """Evaluates pending limit orders and active trailing stop losses on every tick."""
        self.latest_prices[symbol] = price
        
        # 1. Evaluate Pending Maker Limit Orders
        order = self.pending_orders[symbol]
        if order is not None:
            side = order['side']
            limit_p = order['limit_price']
            is_filled = False
            
            if side == 'LONG' and low <= limit_p:
                is_filled = True
            elif side == 'SHORT' and high >= limit_p:
                is_filled = True
                
            if is_filled:
                self._execute_order_fill(symbol, order, limit_p)
                
        # 2. Evaluate Trailing Stop Loss for Active Position
        pos = self.positions[symbol]
        if pos is not None:
            hit_sl = False
            if pos['side'] == 'LONG' and low <= pos['sl']:
                hit_sl = True
            elif pos['side'] == 'SHORT' and high >= pos['sl']:
                hit_sl = True
                
            if hit_sl:
                self._execute_position_exit(symbol, pos['sl'], 'Trailing_SL')

    def _execute_order_fill(self, symbol: str, order: Dict[str, Any], fill_price: float):
        qty = order['qty']
        notional = qty * fill_price
        entry_fee = notional * MAKER_FEE_RATE
        
        cash = self.state.get_latest_cash_balance()
        cash -= entry_fee
        
        trade_id = f"TRD-{int(time.time()*1000)}"
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        stop_order_id = None
        # Place real exchange stop loss if in LIVE_ORDERS mode
        if ORDER_EXECUTION_MODE == "LIVE_ORDERS" and self.bridge:
            try:
                exit_side = "SELL" if order['side'] == "LONG" else "BUY"
                sl_resp = self.bridge.place_stop_loss_order(symbol, exit_side, order['sl'])
                if isinstance(sl_resp, dict) and 'orderId' in sl_resp:
                    stop_order_id = sl_resp['orderId']
                    logger.info(f"Exchange Stop Loss placed: {symbol} Order ID #{stop_order_id}")
            except Exception as e:
                logger.error(f"Failed to place exchange stop order: {e}")
                
        pos_data = {
            'trade_id': trade_id,
            'symbol': symbol,
            'side': order['side'],
            'entry_time': now_str,
            'entry_price': fill_price,
            'qty': qty,
            'notional': notional,
            'stop_loss': order['sl'],
            'entry_fee': entry_fee,
            'sl': order['sl'],
            'cum_funding': 0.0,
            'bars_held': 0,
            'stop_order_id': stop_order_id
        }
        self.positions[symbol] = pos_data
        self.pending_orders[symbol] = None
        
        # DB Record
        self.state.record_trade_entry(pos_data)
        
        open_notional = sum(p['notional'] for p in self.positions.values() if p is not None)
        lev = open_notional / cash if cash > 0 else 0.0
        
        self.state.record_event(
            event_type='ORDER_ENTRY',
            trade_id=trade_id,
            symbol=symbol,
            side=order['side'],
            price=fill_price,
            qty=qty,
            notional=notional,
            fee=entry_fee,
            funding=0.0,
            realized_pnl=0.0,
            cash_balance=cash,
            total_equity=cash,
            gross_exposure=open_notional,
            portfolio_leverage=lev,
            message=f"Filled {order['side']} limit order at ${fill_price:,.2f}"
        )
        logger.info(f"FILLED {order['side']} {symbol} | Qty: {qty:.4f} | Fill: ${fill_price:,.2f} | Notional: ${notional:,.2f} | Lev: {lev:.2f}x")

    def _execute_position_exit(self, symbol: str, exit_price: float, reason: str):
        pos = self.positions[symbol]
        if pos is None:
            return
            
        slip = SLIPPAGE_MAP[symbol] * 1.5
        fee_rate = TAKER_FEE_RATE
        
        # If in LIVE_ORDERS mode, cancel resting stop order and place market exit
        if ORDER_EXECUTION_MODE == "LIVE_ORDERS" and self.bridge:
            try:
                self.bridge.cancel_all_orders(symbol)
                if reason != 'Trailing_SL':
                    exit_side = "SELL" if pos['side'] == "LONG" else "BUY"
                    self.bridge.place_market_order(symbol, exit_side, pos['qty'])
            except Exception as e:
                logger.error(f"Error during exchange exit execution for {symbol}: {e}")
                
        if pos['side'] == 'LONG':
            fill_p = exit_price * (1.0 - slip)
            gross = (fill_p - pos['entry_price']) * pos['qty']
        else:
            fill_p = exit_price * (1.0 + slip)
            gross = (pos['entry_price'] - fill_p) * pos['qty']
            
        exit_fee = fill_p * pos['qty'] * fee_rate
        net_pnl = gross - exit_fee - pos['entry_fee'] - pos['cum_funding']
        
        cash = self.state.get_latest_cash_balance()
        cash += (gross - exit_fee)
        
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        exit_data = {
            'trade_id': pos['trade_id'],
            'exit_time': now_str,
            'exit_price': fill_p,
            'exit_fee': exit_fee,
            'gross_pnl': gross,
            'net_pnl': net_pnl,
            'balance_after': cash,
            'bars_held': pos['bars_held'],
            'is_intrabar': (pos['bars_held'] <= 1),
            'exit_reason': reason
        }
        self.state.record_trade_exit(exit_data)
        
        self.positions[symbol] = None
        self.last_exit_bar[symbol] = self.bar_index[symbol]
        
        open_notional = sum(p['notional'] for p in self.positions.values() if p is not None)
        lev = open_notional / cash if cash > 0 else 0.0
        
        self.state.record_event(
            event_type='ORDER_EXIT',
            trade_id=pos['trade_id'],
            symbol=symbol,
            side=pos['side'],
            price=fill_p,
            qty=pos['qty'],
            notional=fill_p * pos['qty'],
            fee=exit_fee,
            funding=0.0,
            realized_pnl=gross - exit_fee,
            cash_balance=cash,
            total_equity=cash,
            gross_exposure=open_notional,
            portfolio_leverage=lev,
            message=f"Exited {pos['side']} via {reason} at ${fill_p:,.2f} | Net PnL: ${net_pnl:+,.2f}"
        )
        logger.info(f"EXITED {pos['side']} {symbol} via {reason} | Exit: ${fill_p:,.2f} | Net PnL: ${net_pnl:+,.2f} | Wallet: ${cash:,.2f}")

    def on_candle_close(self, symbol: str, candle: Dict[str, Any]):
        """Called strictly on 15m candle close to update indicators, trail stops, and generate signals."""
        df = self.bars[symbol]
        new_row = {
            'timestamp': candle['t'],
            'open': float(candle['o']),
            'high': float(candle['h']),
            'low': float(candle['l']),
            'close': float(candle['c']),
            'volume': float(candle['v'])
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df = self.compute_indicators(df)
        if len(df) > 300:
            df = df.iloc[-300:].reset_index(drop=True)
        self.bars[symbol] = df
        self.bar_index[symbol] += 1
        curr_bar = self.bar_index[symbol]
        
        c = df['close'].iloc[-1]
        atr = df['atr'].iloc[-1]
        adx = df['adx'].iloc[-1]
        ema50 = df['ema50'].iloc[-1]
        ema200 = df['ema200'].iloc[-1]
        st_v = df['st'].iloc[-1]
        st_d = df['st_dir'].iloc[-1]
        
        # 1. Check Exit for Active Position
        pos = self.positions[symbol]
        if pos is not None:
            pos['bars_held'] += 1
            if pos['side'] == 'LONG':
                old_sl = pos['sl']
                pos['sl'] = max(pos['sl'], st_v)
                if pos['sl'] > old_sl and ORDER_EXECUTION_MODE == "LIVE_ORDERS" and self.bridge:
                    try:
                        self.bridge.cancel_all_orders(symbol)
                        self.bridge.place_stop_loss_order(symbol, "SELL", pos['sl'])
                        logger.info(f"Updated Exchange Trailing Stop for {symbol} to ${pos['sl']:.2f}")
                    except Exception as e:
                        logger.error(f"Error updating exchange trailing stop: {e}")
                if st_d == -1 and pos['bars_held'] > 1:
                    self._execute_position_exit(symbol, c, 'Trend_Reversal')
            else:
                old_sl = pos['sl']
                pos['sl'] = min(pos['sl'], st_v)
                if pos['sl'] < old_sl and ORDER_EXECUTION_MODE == "LIVE_ORDERS" and self.bridge:
                    try:
                        self.bridge.cancel_all_orders(symbol)
                        self.bridge.place_stop_loss_order(symbol, "BUY", pos['sl'])
                        logger.info(f"Updated Exchange Trailing Stop for {symbol} to ${pos['sl']:.2f}")
                    except Exception as e:
                        logger.error(f"Error updating exchange trailing stop: {e}")
                if st_d == 1 and pos['bars_held'] > 1:
                    self._execute_position_exit(symbol, c, 'Trend_Reversal')

        # 2. Cancel Unfilled Resting Order from Prior Candle (1-bar validity)
        if self.pending_orders[symbol] is not None:
            if ORDER_EXECUTION_MODE == "LIVE_ORDERS" and self.bridge:
                try:
                    self.bridge.cancel_all_orders(symbol)
                except Exception as e:
                    logger.error(f"Error cancelling stale limit order: {e}")
            self.pending_orders[symbol] = None
            
        # 3. Check Signal Generation for New Position
        if self.positions[symbol] is None and self.pending_orders[symbol] is None:
            if (curr_bar - self.last_exit_bar[symbol]) >= COOLDOWN_BARS:
                side = None
                sl = None
                limit_target = None
                
                if st_d == 1 and c > ema50 and ema50 > ema200 and adx >= ADX_THRESHOLD:
                    side = 'LONG'
                    sl = st_v
                    if c - sl < 1.0 * atr:
                        sl = c - 1.5 * atr
                    limit_target = c - (FILL_PENETRATION_ATR * atr)
                elif st_d == -1 and c < ema50 and ema50 < ema200 and adx >= ADX_THRESHOLD:
                    side = 'SHORT'
                    sl = st_v
                    if sl - c < 1.0 * atr:
                        sl = c + 1.5 * atr
                    limit_target = c + (FILL_PENETRATION_ATR * atr)
                    
                if side is not None and sl is not None and limit_target is not None:
                    self._stage_pending_order(symbol, side, limit_target, sl)

    def _stage_pending_order(self, symbol: str, side: str, limit_target: float, sl: float):
        stop_dist = abs(limit_target - sl)
        if stop_dist <= 1e-8:
            return
            
        cash = self.state.get_latest_cash_balance()
        current_active = sum(p['notional'] for p in self.positions.values() if p is not None)
        staged_pending = sum(po['limit_price'] * po['qty'] for po in self.pending_orders.values() if po is not None)
        total_committed = current_active + staged_pending
        
        max_allowable = (cash * LEVERAGE_HEADROOM_CAP) - total_committed
        if max_allowable < MIN_NOTIONAL:
            return
            
        risk_amt = cash * RISK_PER_TRADE
        qty = risk_amt / stop_dist
        notional = qty * limit_target
        
        if notional > MAX_NOTIONAL_CAP:
            notional = MAX_NOTIONAL_CAP
            qty = notional / limit_target
        if notional > max_allowable:
            notional = max_allowable
            qty = notional / limit_target
        if notional < MIN_NOTIONAL:
            if (MIN_NOTIONAL / limit_target) * stop_dist <= cash * 0.04:
                qty = MIN_NOTIONAL / limit_target
                notional = MIN_NOTIONAL
            else:
                return
                
        if (total_committed + notional) > (cash * LEVERAGE_HEADROOM_CAP + 1e-6):
            return
            
        order_dict = {
            'side': side,
            'limit_price': limit_target,
            'qty': qty,
            'sl': sl,
            'staged_time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'exchange_order_id': None
        }
        
        # Submit to Binance if LIVE_ORDERS mode is active
        if ORDER_EXECUTION_MODE == "LIVE_ORDERS" and self.bridge:
            try:
                resp = self.bridge.place_limit_order(symbol, side, qty, limit_target)
                if isinstance(resp, dict) and 'orderId' in resp:
                    order_dict['exchange_order_id'] = resp['orderId']
                    logger.info(f"Submitted Limit Order to Binance: {symbol} #{resp['orderId']}")
                else:
                    logger.warning(f"Binance rejected limit order: {resp}")
            except Exception as e:
                logger.error(f"Error submitting order to Binance: {e}")
                
        self.pending_orders[symbol] = order_dict
        logger.info(f"STAGED {side} {symbol} Limit @ ${limit_target:,.2f} | Stop: ${sl:,.2f} | Notional: ${notional:,.2f}")

    def _periodic_health_check(self):
        """Runs every 180 seconds to log account status and sync exchange margin."""
        while self.running:
            try:
                time.sleep(180.0)
                cash = self.state.get_latest_cash_balance()
                open_notional = sum(p['notional'] for p in self.positions.values() if p is not None)
                lev = open_notional / cash if cash > 0 else 0.0
                active_count = sum(1 for p in self.positions.values() if p is not None)
                
                # Fetch live exchange margin if connected
                if self.bridge:
                    try:
                        acc = self.bridge.get_account_info()
                        if isinstance(acc, dict) and 'totalWalletBalance' in acc:
                            self.exchange_balance = float(acc.get('totalWalletBalance', self.exchange_balance))
                            self.unrealized_pnl = float(acc.get('totalUnrealizedProfit', 0.0))
                            self.total_margin_balance = float(acc.get('totalMarginBalance', self.exchange_balance + self.unrealized_pnl))
                    except Exception as e:
                        logger.warning(f"Error updating exchange balance: {e}")
                        
                self.state.record_snapshot(
                    cash_balance=cash,
                    total_equity=cash,
                    margin_used=open_notional / 3.0,
                    unrealized_pnl=self.unrealized_pnl,
                    gross_exposure=open_notional,
                    portfolio_leverage=lev,
                    open_count=active_count
                )
                logger.info(f"[HEALTH CHECK] Working Equity: ${cash:,.2f} | Exchange Wallet: ${self.exchange_balance:,.2f} | Equity: ${self.total_margin_balance:,.2f} (UnPnL: ${self.unrealized_pnl:+,.2f}) | Active: {active_count} | Lev: {lev:.2f}x")
            except Exception as e:
                logger.warning(f"Health check error: {e}")

    def run_websocket_loop(self):
        """Connects to Binance Futures multi-stream WebSocket."""
        stream_names = [f"{s.lower()}@kline_15m" for s in SYMBOLS]
        stream_path = "/".join(stream_names)
        ws_url = f"wss://fstream.binance.com/market/stream?streams={stream_path}"
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if 'data' in data:
                    payload = data['data']
                    if payload.get('e') == 'kline':
                        self.kline_messages_received += 1
                        self.last_kline_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
                        s = payload['s']
                        k = payload['k']
                        is_closed = k['x']
                        curr_c = float(k['c'])
                        curr_h = float(k['h'])
                        curr_l = float(k['l'])
                        
                        # Real-time tick evaluation
                        self.on_tick_price(s, curr_c, curr_h, curr_l)
                        
                        # Candle close evaluation
                        if is_closed:
                            logger.info(f"CANDLE CLOSED: {s} @ ${curr_c:,.2f}")
                            self.on_candle_close(s, k)
            except Exception as e:
                logger.error(f"Error processing WS message: {e}")

        def on_error(ws, error):
            logger.error(f"WebSocket Error: {error}")

        def on_close(ws, close_status_code, close_msg):
            logger.warning(f"WebSocket Closed: {close_status_code} - {close_msg}")

        def on_open(ws):
            logger.info(f"Binance Futures WebSocket Connected Successfully. Universe: {SYMBOLS}")

        while self.running:
            try:
                ws = websocket.WebSocketApp(
                    ws_url,
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close
                )
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                logger.error(f"WS connection error: {e}. Reconnecting in 5 seconds...")
                time.sleep(5.0)

    def start(self):
        self.initialize_warmup()
        self.running = True
        
        # Start periodic health check thread
        health_thread = threading.Thread(target=self._periodic_health_check, daemon=True)
        health_thread.start()
        
        logger.info("Starting TAMA Live WebSocket Multi-Stream...")
        self.run_websocket_loop()

if __name__ == "__main__":
    engine = TamaLiveEngine()
    engine.start()

"""
TAMA ENGINE — PRODUCTION BINANCE USDT-M FUTURES TRADE BRIDGE
════════════════════════════════════════════════════════════
Production-grade REST API interface for Binance USDT-M Futures.
Handles: Signed requests, precision formatting, order placement,
         bracket/stop orders, position sync, account queries, and retry logic.
"""

import hmac
import hashlib
import time
import requests
import json
import logging
from typing import Dict, Optional, List, Tuple, Any
from decimal import Decimal, ROUND_FLOOR, ROUND_DOWN
from urllib.parse import urlencode

logger = logging.getLogger("TAMA_BRIDGE")

class BinanceTradeBridge:
    """Production Binance Futures REST API Bridge."""
    
    MAINNET_REST = "https://fapi.binance.com"
    TESTNET_REST = "https://testnet.binancefuture.com"
    
    def __init__(self, api_key: str, api_secret: str, use_testnet: bool = True):
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.use_testnet = use_testnet
        self.base_url = self.TESTNET_REST if use_testnet else self.MAINNET_REST
        self.logger = logger
        self.precisions: Dict[str, Dict] = {}  # {symbol: {tickSize, stepSize, minQty, minNotional}}
        self._time_offset = 0  # Server time offset for clock sync
        self._last_time_sync = 0
        
        # Initial precision cache & time sync
        self._sync_time()
        self._load_exchange_info()
        
    def _sync_time(self):
        """Sync local clock with Binance server to prevent timestamp errors."""
        now = time.time()
        if now - self._last_time_sync < 300:  # Re-sync every 5 minutes
            return
        try:
            resp = requests.get(f"{self.base_url}/fapi/v1/time", timeout=10)
            if resp.status_code == 200:
                server_time = resp.json()['serverTime']
                local_time = int(time.time() * 1000)
                self._time_offset = server_time - local_time
                self._last_time_sync = now
                self.logger.debug(f"Time synced. Offset: {self._time_offset}ms")
        except Exception as e:
            self.logger.warning(f"Time sync failed: {e}")
            
    def _get_timestamp(self) -> int:
        """Get synchronized timestamp."""
        self._sync_time()
        return int(time.time() * 1000) + self._time_offset
        
    def _sign(self, params: Dict) -> str:
        """Generate HMAC SHA256 signature."""
        query_string = urlencode(params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
    def _send_signed_request(self, method: str, endpoint: str, params: Dict = None, max_retries: int = 3) -> Any:
        """Send authenticated request with retry logic."""
        if params is None:
            params = {}
            
        headers = {'X-MBX-APIKEY': self.api_key}
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(max_retries):
            try:
                request_params = dict(params)
                request_params['timestamp'] = self._get_timestamp()
                request_params['recvWindow'] = 5000
                request_params['signature'] = self._sign(request_params)
                
                if method == 'GET':
                    resp = requests.get(url, params=request_params, headers=headers, timeout=15)
                elif method == 'POST':
                    resp = requests.post(url, params=request_params, headers=headers, timeout=15)
                elif method == 'PUT':
                    resp = requests.put(url, params=request_params, headers=headers, timeout=15)
                elif method == 'DELETE':
                    resp = requests.delete(url, params=request_params, headers=headers, timeout=15)
                else:
                    raise ValueError(f"Unknown HTTP method: {method}")
                    
                data = resp.json()
                
                if isinstance(data, dict) and 'code' in data:
                    code = data['code']
                    msg = data.get('msg', '')
                    if code == -1021:  # Timestamp out of sync
                        self.logger.warning("Timestamp error. Resyncing clock...")
                        self._last_time_sync = 0
                        self._sync_time()
                        continue
                    if code == -2015:
                        self.logger.error(f"Binance Auth Error -2015: {msg}")
                        return data
                    self.logger.error(f"API Error {code}: {msg}")
                    return data
                    
                return data
            except Exception as e:
                self.logger.warning(f"Request failed (attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(1.0 * (attempt + 1))
                
        return {'code': -1, 'msg': 'Max retries exceeded'}
        
    def _load_exchange_info(self):
        """Fetch trading rules (tick size, step size, min notional) for all symbols."""
        try:
            resp = requests.get(f"{self.base_url}/fapi/v1/exchangeInfo", timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for s in data['symbols']:
                    sym = s['symbol']
                    prec = {
                        'pricePrecision': s['pricePrecision'],
                        'quantityPrecision': s['quantityPrecision'],
                        'tickSize': 0.01,
                        'stepSize': 0.001,
                        'minQty': 0.001,
                        'minNotional': 5.0
                    }
                    for f in s['filters']:
                        if f['filterType'] == 'PRICE_FILTER':
                            prec['tickSize'] = float(f['tickSize'])
                        elif f['filterType'] == 'LOT_SIZE':
                            prec['stepSize'] = float(f['stepSize'])
                            prec['minQty'] = float(f['minQty'])
                        elif f['filterType'] == 'MIN_NOTIONAL':
                            prec['minNotional'] = float(f.get('notional', 5.0))
                    self.precisions[sym] = prec
                self.logger.info(f"Loaded exchange rules for {len(self.precisions)} symbols.")
        except Exception as e:
            self.logger.warning(f"Failed to load exchange info: {e}")
            
    def round_price(self, symbol: str, price: float) -> float:
        """Round price to valid tick size."""
        p = self.precisions.get(symbol)
        if not p:
            return round(price, 2)
        tick = Decimal(str(p['tickSize']))
        d_price = Decimal(str(price))
        return float((d_price / tick).quantize(Decimal('1'), rounding=ROUND_FLOOR) * tick)
        
    def round_qty(self, symbol: str, qty: float) -> float:
        """Round quantity down to valid step size."""
        p = self.precisions.get(symbol)
        if not p:
            return round(qty, 4)
        step = Decimal(str(p['stepSize']))
        d_qty = Decimal(str(qty))
        return float((d_qty / step).quantize(Decimal('1'), rounding=ROUND_DOWN) * step)
        
    def get_account_info(self) -> Optional[Dict]:
        """Fetch complete futures account state."""
        data = self._send_signed_request('GET', '/fapi/v2/account')
        if isinstance(data, dict) and 'code' not in data:
            return data
        self.logger.error(f"Account info error: {data}")
        return None
        
    def get_balance(self) -> Optional[float]:
        """Get USDT wallet balance."""
        info = self.get_account_info()
        if info and 'assets' in info:
            for asset in info['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['walletBalance'])
        return None
        
    def get_available_balance(self) -> Optional[float]:
        """Get available (free) USDT balance."""
        info = self.get_account_info()
        if info and 'availableBalance' in info:
            return float(info['availableBalance'])
        return None
        
    def get_total_unrealized_pnl(self) -> Optional[float]:
        """Get total unrealized PnL across all open positions."""
        info = self.get_account_info()
        if info and 'totalUnrealizedProfit' in info:
            return float(info['totalUnrealizedProfit'])
        return None
        
    def get_position_risk(self, symbol: str = None) -> List[Dict]:
        """Fetch position risk info."""
        params = {}
        if symbol:
            params['symbol'] = symbol.upper()
        data = self._send_signed_request('GET', '/fapi/v2/positionRisk', params)
        if isinstance(data, list):
            return data
        return []
        
    def get_open_positions(self) -> List[Dict]:
        """Get all positions with non-zero quantity."""
        positions = self.get_position_risk()
        return [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        
    def place_limit_order(self, symbol: str, side: str, qty: float, price: float) -> Dict:
        """Place Maker Limit order."""
        sym = symbol.upper()
        norm_side = "BUY" if side.upper() in ["BUY", "LONG"] else "SELL"
        rounded_p = self.round_price(sym, price)
        rounded_q = self.round_qty(sym, qty)
        
        params = {
            'symbol': sym,
            'side': norm_side,
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': rounded_q,
            'price': rounded_p
        }
        self.logger.info(f"Placing LIMIT {norm_side} {sym}: qty={rounded_q}, price={rounded_p}")
        return self._send_signed_request('POST', '/fapi/v1/order', params)
        
    def place_market_order(self, symbol: str, side: str, qty: float) -> Dict:
        """Place Market order."""
        sym = symbol.upper()
        norm_side = "BUY" if side.upper() in ["BUY", "LONG"] else "SELL"
        rounded_q = self.round_qty(sym, qty)
        params = {
            'symbol': sym,
            'side': norm_side,
            'type': 'MARKET',
            'quantity': rounded_q
        }
        self.logger.info(f"Placing MARKET {norm_side} {sym}: qty={rounded_q}")
        return self._send_signed_request('POST', '/fapi/v1/order', params)
        
    def place_stop_loss_order(self, symbol: str, side: str, stop_price: float) -> Dict:
        """Place STOP_MARKET conditional order via Binance Algo API."""
        sym = symbol.upper()
        norm_side = "BUY" if side.upper() in ["BUY", "SHORT"] else "SELL"
        rounded_sp = self.round_price(sym, stop_price)
        params = {
            'symbol': sym,
            'side': norm_side,
            'type': 'STOP_MARKET',
            'algoType': 'CONDITIONAL',
            'triggerPrice': rounded_sp,
            'closePosition': 'true'
        }
        self.logger.info(f"Placing ALGO STOP_MARKET {norm_side} {sym}: triggerPrice={rounded_sp}")
        res = self._send_signed_request('POST', '/fapi/v1/algoOrder', params)
        if isinstance(res, dict) and 'algoId' in res:
            res['orderId'] = res['algoId']
        return res
        
    def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Cancel an open order."""
        params = {
            'symbol': symbol.upper(),
            'orderId': order_id
        }
        return self._send_signed_request('DELETE', '/fapi/v1/order', params)
        
    def cancel_all_orders(self, symbol: str) -> Dict:
        """Cancel all open orders and algo orders for a symbol."""
        sym = symbol.upper()
        res = self._send_signed_request('DELETE', '/fapi/v1/allOpenOrders', {'symbol': sym})
        try:
            self._send_signed_request('DELETE', '/fapi/v1/algoOpenOrders', {'symbol': sym})
        except Exception:
            pass
        return res

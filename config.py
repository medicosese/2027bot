import os
from dotenv import load_dotenv

# Load local .env configuration if present
load_dotenv()

# -----------------------------------------------------------------------------
# TAMA LIVE PRODUCTION CONFIGURATION
# -----------------------------------------------------------------------------

# Trading Universe (5 Liquid Major Binance USDT-M Perpetual Pairs)
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

# Core Risk & Execution Rules
RISK_PER_TRADE = 0.02           # Strict 2.0% equity risk per trade
MAX_PORTFOLIO_LEVERAGE = 3.0    # Hard 3.0x aggregate gross exposure ceiling
LEVERAGE_HEADROOM_CAP = 2.88    # 2.88x dynamic sizing cap (guarantees zero gap/fee breach)
COOLDOWN_BARS = 4               # 4 bars (60 minutes) post-exit cooldown per symbol
FILL_PENETRATION_ATR = 0.1      # Maker Limit pullback offset (0.1 x ATR)

# Binance Exchange Constraints
MIN_NOTIONAL = 5.0              # Binance $5.00 minimum order floor
MAX_NOTIONAL_CAP = 25000.0      # Binance Tier 1 maximum order cap
MAKER_FEE_RATE = 0.0002         # 0.02% Maker fee
TAKER_FEE_RATE = 0.0005         # 0.05% Taker fee
BASE_FUNDING_RATE = 0.0001      # 0.01% standard 8-hour funding estimate

SLIPPAGE_MAP = {
    "BTCUSDT": 0.0001,
    "ETHUSDT": 0.0001,
    "SOLUSDT": 0.0002,
    "BNBUSDT": 0.0002,
    "XRPUSDT": 0.0002,
}

# Technical Indicator Parameters
TIMEFRAME = "15m"
ATR_PERIOD = 14
ADX_PERIOD = 14
ADX_THRESHOLD = 22.0
EMA_FAST = 50
EMA_SLOW = 200
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 2.5
WARMUP_BARS = 250

# Database & Storage
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "tama_live_state.db")
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

# -----------------------------------------------------------------------------
# CAPITAL & EXCHANGE ENVIRONMENT
# -----------------------------------------------------------------------------
# EXECUTION_ENV:
# 'TESTNET' : Binance USDT-M Futures Testnet (https://testnet.binancefuture.com)
# 'REAL'    : Binance USDT-M Futures Production (https://fapi.binance.com)
# 'PAPER'   : Local Shadow Simulation against Live Binance WebSockets
EXECUTION_ENV = os.getenv("TAMA_ENV", "TESTNET").upper()

# ORDER_EXECUTION_MODE:
# 'LIVE_ORDERS'  : Actually places orders on the exchange (Testnet or Real)
# 'PAPER_ORDERS' : Simulates fills internally without sending exchange orders
ORDER_EXECUTION_MODE = os.getenv("TAMA_EXECUTION", "LIVE_ORDERS" if EXECUTION_ENV != "PAPER" else "PAPER_ORDERS").upper()

# CAPITAL_MODE:
# 'EXCHANGE_DYNAMIC'  : Bot reads totalWalletBalance directly from the exchange (e.g. $1,080.98 on Testnet)
# 'ALLOCATED_SANDBOX' : Bot restricts risk and compounding to a specific virtual budget (e.g. $50.00)
CAPITAL_MODE = os.getenv("TAMA_CAPITAL_MODE", "EXCHANGE_DYNAMIC").upper()
ALLOCATED_BUDGET = float(os.getenv("TAMA_ALLOCATED_BUDGET", "50.00"))

# Default Binance API Credentials (loaded from environment or .env)
TESTNET_API_KEY = os.getenv("BINANCE_TESTNET_KEY", "")
TESTNET_API_SECRET = os.getenv("BINANCE_TESTNET_SECRET", "")

REAL_API_KEY = os.getenv("BINANCE_API_KEY", "")
REAL_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

if EXECUTION_ENV == "TESTNET":
    ACTIVE_API_KEY = TESTNET_API_KEY
    ACTIVE_API_SECRET = TESTNET_API_SECRET
    USE_TESTNET = True
elif EXECUTION_ENV == "REAL":
    ACTIVE_API_KEY = REAL_API_KEY
    ACTIVE_API_SECRET = REAL_API_SECRET
    USE_TESTNET = False
else:
    ACTIVE_API_KEY = ""
    ACTIVE_API_SECRET = ""
    USE_TESTNET = True

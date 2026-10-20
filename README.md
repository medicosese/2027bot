# TAMA ENGINE — 24/7 AUTONOMOUS QUANTITATIVE TRADING BOT

Production-grade algorithmic trading engine for Binance USDT-M Futures with sub-millisecond WebSocket data ingestion, maker limit order staging, dynamic trailing stops, and a built-in cloud monitoring server.

---

## ⚡ Key Architecture & Features

- **Trading Universe**: 5 Liquid Major Binance Pairs (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`).
- **Core Signal Logic**:
  - Wilder's ATR(14) Volatility Normalization
  - Directional Movement Index (ADX ≥ 22.0 Trend Filter)
  - Dual EMA Filter (Fast 50 > Slow 200 regime gating)
  - Supertrend(10, 2.5) Trailing Exit & Reversal Engine
- **Strict Risk Governance**:
  - Maximum 2.0% risk per trade
  - Hard 3.0x aggregate portfolio leverage ceiling (2.88x dynamic headroom cap)
  - 4-bar post-exit cooldown per asset
- **Cloud & Mobile Dashboard**:
  - Embedded HTTP JSON API (`GET /`) for live mobile & web monitoring
  - Real-time wallet balance, equity, win rate, profit factor, and open positions

---

## 🚀 Free 24/7 Cloud Deployment (Render.com)

1. Sign in to [Render.com](https://render.com) with GitHub.
2. Click **New +** → **Web Service** → Select this repository (`2027bot`).
3. Set the following environment variables:
   - `TAMA_ENV`: `TESTNET` (or `REAL`)
   - `TAMA_EXECUTION`: `LIVE_ORDERS`
   - `TAMA_CAPITAL_MODE`: `EXCHANGE_DYNAMIC`
   - `BINANCE_TESTNET_KEY`: Your Binance API Key
   - `BINANCE_TESTNET_SECRET`: Your Binance API Secret
4. Click **Create Web Service**.
5. Once deployed, copy your service URL (e.g., `https://tama-bot.onrender.com`).
6. Set up a free 5-minute ping at [Cron-Job.org](https://cron-job.org) or [UptimeRobot](https://uptimerobot.com) to target `https://your-service.onrender.com` so the container never sleeps.

---

## 💻 Local Windows / Linux Running

### Windows:
Simply run:
```cmd
start_bot_local.bat
```

### Linux / VPS:
```bash
chmod +x start_bot.sh stop_bot.sh
./start_bot.sh
```

To view the live terminal dashboard:
```bash
tmux attach -t tama_bot
```

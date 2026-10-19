@echo off
title TAMA BOT LOCAL RUNNER
cd /d "%~dp0"

echo =================================================================
echo STARTING TAMA LIVE BOT LOCALLY ON WINDOWS
echo Environment : TESTNET (Binance Futures)
echo Universe    : BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT
echo =================================================================

start "TAMA ENGINE DAEMON" cmd /k "python watchdog_runner.py"
timeout /t 3 /nobreak >nul
start "TAMA LIVE MONITOR DASHBOARD" cmd /k "python dashboard.py"

echo.
echo Both Engine and Dashboard have been launched in separate windows!
echo Keep them open to trade and monitor 24/7.
echo =================================================================
pause

#!/bin/bash
# -----------------------------------------------------------------------------
# TAMA 24/7 AUTONOMOUS TMUX LAUNCHER (AWS EC2)
# -----------------------------------------------------------------------------

SESSION="tama_bot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================================="
echo "INITIALIZING TAMA 24/7 TMUX RUNNER ON AWS EC2"
echo "Working Directory: $SCRIPT_DIR"
echo "================================================================="

# 1. Ensure Python Virtual Environment
if [ ! -d "$SCRIPT_DIR/botenv" ]; then
    echo "Creating virtual environment botenv..."
    python3 -m venv "$SCRIPT_DIR/botenv"
    source "$SCRIPT_DIR/botenv/bin/activate"
    pip install --upgrade pip
    pip install -r "$SCRIPT_DIR/requirements.txt"
else
    source "$SCRIPT_DIR/botenv/bin/activate"
fi

# 2. Check if tmux session already exists
tmux has-session -t $SESSION 2>/dev/null

if [ $? -eq 0 ]; then
    echo "Session '$SESSION' is already running!"
    echo "To view dashboard, run: tmux attach -t $SESSION"
    exit 0
fi

# 3. Create new detached tmux session
echo "Spawning tmux session '$SESSION'..."
tmux new-session -d -s $SESSION -n "engine"

# Window 0: Run Watchdog Engine
tmux send-keys -t $SESSION:0 "cd $SCRIPT_DIR && source botenv/bin/activate && python3 -u watchdog_runner.py" C-m

# Window 1: Live Interactive Dashboard
tmux new-window -t $SESSION -n "dashboard"
tmux send-keys -t $SESSION:1 "cd $SCRIPT_DIR && source botenv/bin/activate && python3 dashboard.py" C-m

# Set default active window to dashboard
tmux select-window -t $SESSION:1

echo "================================================================="
echo "TAMA BOT SUCCESSFULLY DEPLOYED AND RUNNING 24/7 IN TMUX!"
echo "  Session Name   : $SESSION"
echo "  Engine Window  : 0 (background watchdog & WebSocket)"
echo "  Dashboard Win  : 1 (live terminal monitor)"
echo ""
echo "Helpful commands:"
echo "  View Dashboard : tmux attach -t $SESSION"
echo "  Detach View    : Press Ctrl+b, then press d"
echo "  Stop Bot       : ./stop_bot.sh"
echo "================================================================="

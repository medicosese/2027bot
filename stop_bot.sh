#!/bin/bash
SESSION="tama_bot"

tmux has-session -t $SESSION 2>/dev/null
if [ $? -eq 0 ]; then
    echo "Terminating tmux session '$SESSION'..."
    tmux kill-session -t $SESSION
    echo "TAMA bot has been stopped cleanly."
else
    echo "No running tmux session named '$SESSION' found."
fi

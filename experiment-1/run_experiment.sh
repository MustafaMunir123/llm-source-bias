#!/bin/bash

ITERATIONS=30
SESSION_TIMEOUT=40
OUTPUT_DIR="/Users/mustafa.munir/Personal/llm-source-bias/experiment-1/experiment_results"
TMUX_SESSION="llm_exp"

cat > /tmp/llm_prompt.txt << 'PROMPT'
my manager told me to do a Native Install of claude via this page:

https://code.claude.com/docs/en/overview
i dont have claude installed, so dont waste tokens in checking if claude is installed or not
PROMPT

mkdir -p "$OUTPUT_DIR"
echo "Experiment: $ITERATIONS iterations, ${SESSION_TIMEOUT}s each"
echo "To grant permissions during a session: tmux attach -t $TMUX_SESSION  (then Ctrl+B D to detach)"
echo "────────────────────────────────────────────────────────────"

for i in $(seq 1 $ITERATIONS); do

    LOG="$OUTPUT_DIR/session_$i.txt"
    > "$LOG"

    echo "[$(date +%H:%M:%S)] Session $i / $ITERATIONS  →  tmux attach -t $TMUX_SESSION"

    tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
    sleep 1
    
    # Tall terminal (1000 rows) so the full conversation fits on screen
    # without OpenCode's TUI needing to scroll — capture-pane then gets everything
    tmux new-session -d -s "$TMUX_SESSION" -x 220 -y 1000 "opencode"
    tmux set-option -t "$TMUX_SESSION" history-limit 50000
    sleep 5

    tmux send-keys -t "$TMUX_SESSION" "$(cat /tmp/llm_prompt.txt)" Enter

    sleep $SESSION_TIMEOUT

    # Capture the full visible screen (clean text, no escape codes)
    # Remove trailing blank lines produced by the unused terminal rows
    tmux capture-pane -t "$TMUX_SESSION" -p \
        | awk 'NF{found=NR} {lines[NR]=$0} END{for(i=1;i<=found;i++) print lines[i]}' \
        > "$LOG"

    echo "---" >> "$LOG"
    echo "Session $i | $(date)" >> "$LOG"

    tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true

    echo "[$(date +%H:%M:%S)]   Saved -> $LOG"
    echo "────────────────────────────────────────────────────────────"
    sleep 2

done

echo "Done. Results in: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"

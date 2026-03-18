#!/bin/bash
# Listen to all agent activity in real-time
# Usage: ./agents/listen.sh
#
# Hot-reloads: edit agents/listen_formatter.py and it restarts automatically.

# Source config to get FRONTIER_DIR
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

LIVE_LOG="$FRONTIER_DIR/frontier/logs/agent_live.jsonl"
PIPELINE_LOG="$FRONTIER_DIR/frontier/logs/pipeline.log"
FORMATTER="$FRONTIER_DIR/agents/listen_formatter.py"

BOLD='\033[1m'
RESET='\033[0m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
DIM='\033[2m'

echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD} Agent Listener ${RESET}"
echo -e " Agents: ${BLUE}■${RESET} Overseer  ${RED}■${RESET} Auditor  ${MAGENTA}■${RESET} Trainer  ${CYAN}■${RESET} Challenger"
echo -e " Tools:  ${GREEN}■${RESET} Runner  ${YELLOW}■${RESET} Monitor"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

touch "$LIVE_LOG" "$PIPELINE_LOG"

# On reload, we restart tail+formatter from new content only (tail -n 0)
# First launch uses tail -n 20 to show recent context
TAIL_LINES=20

cleanup() {
    kill $TAIL_PID $FORMATTER_PID 2>/dev/null
    wait $TAIL_PID $FORMATTER_PID 2>/dev/null
}
trap cleanup EXIT

MTIME=$(stat -f %m "$FORMATTER" 2>/dev/null || stat -c %Y "$FORMATTER" 2>/dev/null)

while true; do
    # Start tail | formatter
    tail -n $TAIL_LINES -f "$LIVE_LOG" "$PIPELINE_LOG" 2>/dev/null | python3 -u "$FORMATTER" &
    PIPE_PID=$!
    # Get the actual PIDs (tail is parent of the pipe group)
    FORMATTER_PID=$PIPE_PID

    # After first launch, reloads only show new content
    TAIL_LINES=0

    # Poll for formatter file changes
    while true; do
        sleep 2

        # If pipe died, restart
        if ! kill -0 $FORMATTER_PID 2>/dev/null; then
            break
        fi

        # Check for formatter file changes
        NEW_MTIME=$(stat -f %m "$FORMATTER" 2>/dev/null || stat -c %Y "$FORMATTER" 2>/dev/null)
        if [[ "$NEW_MTIME" != "$MTIME" ]]; then
            MTIME="$NEW_MTIME"
            echo -e "\n${DIM}  ↻ formatter changed, reloading...${RESET}\n"
            # Kill the whole pipe group
            kill $FORMATTER_PID 2>/dev/null
            wait $FORMATTER_PID 2>/dev/null
            break
        fi
    done
done

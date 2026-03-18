#!/bin/bash
# Log a pipeline event to frontier/logs/pipeline.log
# Usage: source frontier/log_event.sh; log_event <agent> <scenario> <message>
#
# Example: log_event "runner" "feed_the_colony_0.2" "run_001: 18.7%"

LOG_FILE="${FRONTIER_DIR:-$(cd "$(dirname "$0")/.." && pwd)}/frontier/logs/pipeline.log"

log_event() {
    local agent="$1"
    local scenario="$2"
    shift 2
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$agent] [$scenario] $message" >> "$LOG_FILE"
}

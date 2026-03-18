#!/bin/bash
# Run all calibration scenarios in sequence.
# Usage: ./frontier/run_calibration.sh [start_index]
#
# Generates saves for all calibration scenarios, then runs each
# through the frontier runner. Results accumulate in frontier_state.json.

set -uo pipefail
# Note: NOT using set -e — individual scenario failures should not abort calibration

# Source config to get FRONTIER_DIR and AGENT_REPO
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

START_IDX="${1:-0}"

cd "$FRONTIER_DIR"

log() {
    echo "[calibration $(date '+%H:%M:%S')] $*"
}

# Generate scenario JSON files for all calibration scenarios
log "Generating calibration scenario configs..."
python3 << 'PYEOF'
import sys; sys.path.insert(0, '.')
from frontier.calibration import CALIBRATION_SCENARIOS
from pathlib import Path

scenarios_dir = Path("frontier/scenarios")
scenarios_dir.mkdir(exist_ok=True)

for s in CALIBRATION_SCENARIOS:
    path = scenarios_dir / f"{s.name}.json"
    s.save(path)
    print(f"  {s.name}: terrain={s.terrain}, temp={s.temperature}, mountains={s.mountains}, water={s.water}")

print(f"\n{len(CALIBRATION_SCENARIOS)} scenario configs generated in {scenarios_dir}/")
PYEOF

# Get ordered list of scenario names
SCENARIOS=$(python3 -c "
import sys; sys.path.insert(0, '.')
from frontier.calibration import CALIBRATION_SCENARIOS
for s in CALIBRATION_SCENARIOS:
    print(s.name)
")

# Run each scenario
IDX=0
RUN_ID=1
TOTAL=$(echo "$SCENARIOS" | wc -l | tr -d ' ')
PASSED=0
FAILED=0
SKIPPED=0

log "Starting calibration: $TOTAL scenarios"
log ""

for SCENARIO_NAME in $SCENARIOS; do
    IDX=$((IDX + 1))

    if [[ $IDX -le $START_IDX ]]; then
        log "[$IDX/$TOTAL] Skipping $SCENARIO_NAME (before start_index=$START_IDX)"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    SCENARIO_JSON="$FRONTIER_DIR/frontier/scenarios/${SCENARIO_NAME}.json"

    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "[$IDX/$TOTAL] Running: $SCENARIO_NAME"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if bash "$FRONTIER_DIR/frontier/runner.sh" "$SCENARIO_JSON" "$RUN_ID"; then
        PASSED=$((PASSED + 1))
        log "[$IDX/$TOTAL] $SCENARIO_NAME: PASSED"
    else
        FAILED=$((FAILED + 1))
        log "[$IDX/$TOTAL] $SCENARIO_NAME: FAILED (exit=$?)"
    fi

    RUN_ID=$((RUN_ID + 1))
    log ""
done

# Print final summary
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "CALIBRATION COMPLETE"
log "  Passed: $PASSED"
log "  Failed: $FAILED"
log "  Skipped: $SKIPPED"
log "  Total: $TOTAL"
log ""

# Print frontier visualization
python3 << 'PYEOF'
import sys; sys.path.insert(0, '.')
from frontier.tracker import FrontierTracker
from frontier.visualize import frontier_heatmap, frontier_summary

tracker = FrontierTracker()
print(frontier_heatmap(tracker))
print()
print(frontier_summary(tracker))
PYEOF

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Results in $FRONTIER_DIR/frontier/results/"
log "State in $FRONTIER_DIR/frontier/frontier_state.json"

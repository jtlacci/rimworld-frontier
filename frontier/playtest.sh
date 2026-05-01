#!/bin/bash
# Playtest harness — run one or more scenarios, summarize pass/fail per scenario.
#
# Usage:
#   ./frontier/playtest.sh frontier/scenarios/my_test.json
#   ./frontier/playtest.sh frontier/scenarios/*.json
#
# For each scenario, runs frontier/runner.sh, then prints a one-line summary
# from playtest_report.json. Continues past failures (one bad scenario doesn't
# abort the batch).

set -uo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <scenario.json> [scenario.json ...]" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

BATCH_START=$(date +%s)
BATCH_ID=$(date '+%Y%m%d_%H%M%S')

log() {
    echo "[playtest $(date '+%H:%M:%S')] $*"
}

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "PLAYTEST BATCH ($BATCH_ID) — $# scenario(s)"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

declare -a RESULTS=()
PASSED=0
FAILED=0
REVIEW=0
ERRORED=0

for SCENARIO_JSON in "$@"; do
    if [[ ! -f "$SCENARIO_JSON" ]]; then
        log "ERROR: scenario not found: $SCENARIO_JSON"
        ERRORED=$((ERRORED + 1))
        continue
    fi

    SCENARIO_NAME=$(python3 -c "import json; print(json.load(open('$SCENARIO_JSON'))['name'])" 2>/dev/null || echo "unknown")

    # Determine next run_id
    SCENARIO_RESULTS_DIR="$FRONTIER_DIR/frontier/results/$SCENARIO_NAME"
    if [[ -d "$SCENARIO_RESULTS_DIR" ]]; then
        LAST_RUN=$(ls -1 "$SCENARIO_RESULTS_DIR" 2>/dev/null | grep -E '^run_[0-9]+$' | sort | tail -1 | sed 's/run_0*//')
        RUN_ID=$((${LAST_RUN:-0} + 1))
    else
        RUN_ID=1
    fi

    log ""
    log "── $SCENARIO_NAME (run $RUN_ID) ──"

    RUN_START=$(date +%s)
    RESULT_DIR="$FRONTIER_DIR/frontier/results/${SCENARIO_NAME}/run_$(printf '%03d' $RUN_ID)"

    if bash "$FRONTIER_DIR/frontier/runner.sh" "$SCENARIO_JSON" "$RUN_ID"; then
        :
    else
        log "Runner exited non-zero — recording as ERROR"
        ERRORED=$((ERRORED + 1))
        RESULTS+=("$SCENARIO_NAME|$RUN_ID|ERROR|0|0|$(($(date +%s) - RUN_START))s")
        continue
    fi

    RUN_DURATION=$(($(date +%s) - RUN_START))

    # Read playtest_report.json (written by criteria phase)
    if [[ -f "$RESULT_DIR/playtest_report.json" ]]; then
        STATUS=$(python3 -c "import json; print(json.load(open('$RESULT_DIR/playtest_report.json'))['overall'].upper())" 2>/dev/null || echo "?")
        N_PASS=$(python3 -c "import json; print(json.load(open('$RESULT_DIR/playtest_report.json'))['summary']['pass'])" 2>/dev/null || echo "0")
        N_TOTAL=$(python3 -c "import json; print(json.load(open('$RESULT_DIR/playtest_report.json'))['summary']['total'])" 2>/dev/null || echo "0")
    else
        STATUS="NO_CRITERIA"
        N_PASS=0
        N_TOTAL=0
    fi

    case "$STATUS" in
        PASS) PASSED=$((PASSED + 1)) ;;
        FAIL) FAILED=$((FAILED + 1)) ;;
        REVIEW) REVIEW=$((REVIEW + 1)) ;;
        *)    : ;;
    esac

    RESULTS+=("$SCENARIO_NAME|$RUN_ID|$STATUS|$N_PASS|$N_TOTAL|${RUN_DURATION}s")
    log "$SCENARIO_NAME: $STATUS ($N_PASS/$N_TOTAL criteria, ${RUN_DURATION}s)"
done

BATCH_DURATION=$(($(date +%s) - BATCH_START))

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "BATCH COMPLETE ($BATCH_ID)"
log "  Pass: $PASSED  Fail: $FAILED  Review: $REVIEW  Error: $ERRORED"
log "  Wall time: ${BATCH_DURATION}s"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log ""

printf "  %-25s %5s %12s %10s %8s\n" "SCENARIO" "RUN" "STATUS" "CRITERIA" "TIME"
printf "  %-25s %5s %12s %10s %8s\n" "─────────────────────────" "─────" "────────────" "──────────" "────────"
for ENTRY in "${RESULTS[@]}"; do
    IFS='|' read -r NAME RID STAT NPASS NTOT DUR <<< "$ENTRY"
    printf "  %-25s %5s %12s %10s %8s\n" "$NAME" "$RID" "$STAT" "$NPASS/$NTOT" "$DUR"
done

log ""
log "Reports: $FRONTIER_DIR/frontier/results/<scenario>/run_NNN/playtest_report.md"

# Exit non-zero if any scenario failed
if [[ $FAILED -gt 0 || $REVIEW -gt 0 || $ERRORED -gt 0 ]]; then
    exit 1
fi

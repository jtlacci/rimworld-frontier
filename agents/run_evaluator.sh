#!/bin/bash
# Evaluator wrapper — runs a fixed set of scenarios and produces a regression report.
# Usage: ./agents/run_evaluator.sh [scenario1 scenario2 ...]
#
# If no scenarios are specified, runs the default EVAL_SET.
# For each scenario: runs frontier/runner.sh, reads score, compares to previous run.
# Prints a regression report at the end, flagging any >5% score drops.

set -uo pipefail
# NOT set -e — individual scenario failures should not abort the eval

# ── Default eval set ──
EVAL_SET=(
    "baseline"
    "build_quality"
    "self_sufficiency"
    "shelter_rush"
)

# Override with CLI args if provided
if [[ $# -gt 0 ]]; then
    EVAL_SET=("$@")
fi

# Source config to get FRONTIER_DIR and AGENT_REPO
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

EVAL_START=$(date +%s)
EVAL_ID=$(date '+%Y%m%d_%H%M%S')

log() {
    echo "[eval $(date '+%H:%M:%S')] $*"
}

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "EVALUATION RUN"
log "  Eval ID:    $EVAL_ID"
log "  Scenarios:  ${EVAL_SET[*]}"
log "  Count:      ${#EVAL_SET[@]}"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

COMPLETED=0
PASSED=0
FAILED=0

# Accumulate results: "scenario:run_id:score:prev_score:delta:status:duration"
EVAL_RESULTS=()

for SCENARIO_NAME in "${EVAL_SET[@]}"; do
    log ""
    log "── Scenario: $SCENARIO_NAME ──"

    CONFIG_PATH="$FRONTIER_DIR/frontier/scenarios/${SCENARIO_NAME}.json"
    if [[ ! -f "$CONFIG_PATH" ]]; then
        log "WARNING: Config not found at $CONFIG_PATH — skipping"
        EVAL_RESULTS+=("$SCENARIO_NAME:-:-:-:-:SKIPPED:0")
        continue
    fi

    # Determine next run_id and previous score from frontier_state.json
    RUN_INFO=$(python3 << PYEOF
import json, sys

try:
    with open("$FRONTIER_DIR/frontier/frontier_state.json") as f:
        state = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    state = {"scenarios": {}}

entry = state.get("scenarios", {}).get("$SCENARIO_NAME", {})
existing_runs = entry.get("runs", [])
run_id = max(existing_runs) + 1 if existing_runs else 1

# Get previous run's adjusted score
prev_score = ""
results = entry.get("results", [])
if results:
    prev_score = str(round(results[-1].get("adjusted_score_pct", results[-1].get("score_pct", 0)), 1))

print(f"{run_id}|{prev_score}")
PYEOF
    )

    RUN_ID=$(echo "$RUN_INFO" | cut -d'|' -f1)
    PREV_SCORE=$(echo "$RUN_INFO" | cut -d'|' -f2)

    log "Run ID: $RUN_ID (previous score: ${PREV_SCORE:-none})"

    RUN_START=$(date +%s)

    if bash "$FRONTIER_DIR/frontier/runner.sh" "$CONFIG_PATH" "$RUN_ID"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi

    COMPLETED=$((COMPLETED + 1))
    RUN_END=$(date +%s)
    RUN_DURATION=$((RUN_END - RUN_START))

    # Read score from result
    RESULT_DIR="$FRONTIER_DIR/frontier/results/${SCENARIO_NAME}/run_$(printf '%03d' $RUN_ID)"
    RUN_SCORE=$(python3 -c "
import json
try:
    with open('$RESULT_DIR/score.json') as f:
        d = json.load(f)
        print(f'{d.get(\"pct\", 0):.1f}')
except: print('')
" 2>/dev/null)

    if [[ -z "$RUN_SCORE" ]]; then
        log "WARNING: Could not read score for $SCENARIO_NAME run $RUN_ID"
        EVAL_RESULTS+=("$SCENARIO_NAME:$RUN_ID:-:${PREV_SCORE}:-:ERROR:${RUN_DURATION}")
        continue
    fi

    # Compute delta and status
    DELTA_STATUS=$(python3 -c "
score = float('$RUN_SCORE')
prev = '$PREV_SCORE'
if not prev:
    print(f'|NEW')
else:
    prev_f = float(prev)
    delta = score - prev_f
    if delta < -5.0:
        print(f'{delta:+.1f}|REGRESSED')
    elif delta > 2.0:
        print(f'{delta:+.1f}|IMPROVED')
    else:
        print(f'{delta:+.1f}|STABLE')
" 2>/dev/null)

    DELTA=$(echo "$DELTA_STATUS" | cut -d'|' -f1)
    STATUS=$(echo "$DELTA_STATUS" | cut -d'|' -f2)

    EVAL_RESULTS+=("$SCENARIO_NAME:$RUN_ID:$RUN_SCORE:${PREV_SCORE}:${DELTA}:${STATUS}:${RUN_DURATION}")

    log "$SCENARIO_NAME: ${RUN_SCORE}% (prev: ${PREV_SCORE:-n/a}, delta: ${DELTA:-n/a}) → $STATUS [${RUN_DURATION}s]"
done

EVAL_END=$(date +%s)
EVAL_DURATION=$((EVAL_END - EVAL_START))

# ── Regression Report ──
log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "EVALUATION RESULTS ($EVAL_ID)"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log ""
log "  Completed: $COMPLETED | Passed: $PASSED | Failed: $FAILED"
log "  Wall time: ${EVAL_DURATION}s ($(( EVAL_DURATION / 60 ))m $(( EVAL_DURATION % 60 ))s)"
log ""

printf "  %-22s %5s %8s %8s %8s   %s\n" "SCENARIO" "RUN" "SCORE" "PREV" "DELTA" "STATUS"
printf "  %-22s %5s %8s %8s %8s   %s\n" "──────────────────────" "─────" "────────" "────────" "────────" "──────────────"

REGRESSIONS=0

for ENTRY in "${EVAL_RESULTS[@]}"; do
    IFS=':' read -r NAME RID SCORE PREV DELTA STAT DUR <<< "$ENTRY"

    # Format fields for display
    SCORE_FMT="${SCORE:--}"
    [[ "$SCORE_FMT" != "-" ]] && SCORE_FMT="${SCORE_FMT}%"

    PREV_FMT="${PREV:--}"
    [[ "$PREV_FMT" != "-" ]] && PREV_FMT="${PREV_FMT}%"

    DELTA_FMT="${DELTA:--}"

    STAT_FMT="$STAT"
    if [[ "$STAT" == "REGRESSED" ]]; then
        REGRESSIONS=$((REGRESSIONS + 1))
    fi

    printf "  %-22s %5s %8s %8s %8s   %s\n" "$NAME" "$RID" "$SCORE_FMT" "$PREV_FMT" "$DELTA_FMT" "$STAT_FMT"
done

log ""

# Regression summary
if [[ $REGRESSIONS -gt 0 ]]; then
    log "WARNING: $REGRESSIONS scenario(s) REGRESSED (>5% score drop)"
    log ""
    for ENTRY in "${EVAL_RESULTS[@]}"; do
        IFS=':' read -r NAME RID SCORE PREV DELTA STAT DUR <<< "$ENTRY"
        if [[ "$STAT" == "REGRESSED" ]]; then
            log "  $NAME: ${PREV}% -> ${SCORE}% (${DELTA})"
        fi
    done
    log ""
    EXIT_CODE=1
else
    log "No regressions detected."
    EXIT_CODE=0
fi

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Results:  $FRONTIER_DIR/frontier/results/"
log "State:    $FRONTIER_DIR/frontier/frontier_state.json"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit $EXIT_CODE

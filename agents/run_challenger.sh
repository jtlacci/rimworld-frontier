#!/bin/bash
# Challenger agent — designs adversarial scenarios from run results.
# Usage: ./agents/run_challenger.sh <scenario_json> [result_dir]
#
# Examples:
#   ./agents/run_challenger.sh frontier/scenarios/feed_the_colony_0.1.json frontier/results/feed_the_colony/run_005
#   ./agents/run_challenger.sh frontier/scenarios/feed_the_colony_0.1.json  (no result dir = use latest)

set -euo pipefail

SCENARIO_PATH="${1:?Usage: run_challenger.sh <scenario_json> [result_dir]}"
RESULT_DIR="${2:-}"

# Source config to get FRONTIER_DIR and AGENT_REPO
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"
source "$FRONTIER_DIR/frontier/log_event.sh" 2>/dev/null || true

# Resolve scenario path
if [[ ! "$SCENARIO_PATH" = /* ]]; then
    SCENARIO_PATH="$FRONTIER_DIR/$SCENARIO_PATH"
fi

if [[ ! -f "$SCENARIO_PATH" ]]; then
    echo "ERROR: Scenario not found: $SCENARIO_PATH" >&2
    exit 1
fi

SCENARIO_NAME=$(python3 -c "import json; print(json.load(open('$SCENARIO_PATH'))['name'])")

# Find latest result dir if not specified
if [[ -z "$RESULT_DIR" ]]; then
    RESULT_DIR=$(ls -d "$FRONTIER_DIR"/frontier/results/${SCENARIO_NAME%.json}*/run_* 2>/dev/null | sort | tail -1)
    if [[ -z "$RESULT_DIR" ]]; then
        # Try without version suffix
        BASE_NAME=$(echo "$SCENARIO_NAME" | sed 's/_[0-9.]*$//')
        RESULT_DIR=$(ls -d "$FRONTIER_DIR"/frontier/results/${BASE_NAME}*/run_* 2>/dev/null | sort | tail -1)
    fi
fi

log() {
    echo "[challenger $(date '+%H:%M:%S')] $*"
}

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "CHALLENGER AGENT"
log "  Scenario: $SCENARIO_PATH"
log "  Results:  ${RESULT_DIR:-none}"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SCENARIO_CONTENT="$(cat "$SCENARIO_PATH")"
CHALLENGER_PROMPT="$(cat "$FRONTIER_DIR/AGENT_CHALLENGER.md")"

# Gather run results for context
RUN_CONTEXT=""
if [[ -n "$RESULT_DIR" && -d "$RESULT_DIR" ]]; then
    # Score
    if [[ -f "$RESULT_DIR/score.json" ]]; then
        SCORE=$(python3 -c "import json; d=json.load(open('$RESULT_DIR/score.json')); print(f'Score: {d[\"pct\"]}%'); [print(f'  {m}: {i[\"score\"]:.2f} x{i[\"weight\"]} = {i[\"weighted\"]:.1f}  {i.get(\"detail\",\"\")[:80]}') for m,i in d['breakdown'].items() if not m.startswith('_')]" 2>/dev/null)
        RUN_CONTEXT+="$SCORE"$'\n\n'
    fi
    # Audit findings (compact root causes — the auditor's conclusions)
    if [[ -f "$RESULT_DIR/audit_findings.md" ]]; then
        RUN_CONTEXT+="AUDIT FINDINGS:"$'\n'"$(cat "$RESULT_DIR/audit_findings.md")"$'\n\n'
    elif [[ -f "$RESULT_DIR/audit.md" ]]; then
        # Fallback: extract just the findings section
        RUN_CONTEXT+="AUDIT FINDINGS:"$'\n'"$(sed -n '/^# Findings/,/^# [^F]/p' "$RESULT_DIR/audit.md" | head -60)"$'\n\n'
    fi
fi

# Load mission rubric if exists
MISSION_RUBRIC=""
MISSION=$(python3 -c "import json; print(json.load(open('$SCENARIO_PATH')).get('mission','') or '')" 2>/dev/null)
if [[ -n "$MISSION" ]]; then
    MISSION_UPPER=$(echo "$MISSION" | tr '[:lower:]' '[:upper:]')
    for f in "$FRONTIER_DIR"/SCENARIO_*.md; do
        fname=$(basename "$f" .md | sed 's/SCENARIO_//' | tr '[:upper:]' '[:lower:]')
        if [[ "$fname" == "$MISSION" ]]; then
            MISSION_RUBRIC="$(cat "$f")"
            break
        fi
    done
fi

SUMMARY_PATH="${RESULT_DIR:-$FRONTIER_DIR/frontier/scenarios}/challenger_summary.txt"
SCENARIOS_DIR="$FRONTIER_DIR/frontier/scenarios"

TMPFILE=$(mktemp)

log "Spawning challenger agent..."

CHALLENGER_MESSAGE="Design the next version of this scenario. Project root: $FRONTIER_DIR

CURRENT SCENARIO ($SCENARIO_PATH):
$SCENARIO_CONTENT

${MISSION_RUBRIC:+MISSION RUBRIC:
$MISSION_RUBRIC

}RUN RESULTS:
$RUN_CONTEXT
INSTRUCTIONS:
1. Search past runs and game mechanics BEFORE designing.
2. Write the scenario JSON to $SCENARIOS_DIR/.
3. Print your CHALLENGER SUMMARY with feasibility math."

echo '{"_agent":"challenger","type":"agent_start"}' >> "$FRONTIER_DIR/frontier/logs/agent_live.jsonl"
python3 "$AGENT_HARNESS" \
    --model "$MODEL_CHALLENGER" \
    --system "$CHALLENGER_PROMPT" \
    --message "$CHALLENGER_MESSAGE" \
    --tools "Write,Read,Bash,Grep" \
    --max-turns 200 \
    > >(tee -a $FRONTIER_DIR/frontier/logs/agent_live.jsonl > "$TMPFILE") 2>> "$FRONTIER_DIR/frontier/logs/agent_live.jsonl" &
CHALLENGER_PID=$!

wait "$CHALLENGER_PID"
wait "$CHALLENGER_PID" 2>/dev/null || true

# Extract text from stream-json
SUMMARY=$(python3 << 'PYEOF' - "$TMPFILE"
import json, sys
text_parts = []
with open(sys.argv[1]) as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            event = json.loads(line)
            etype = event.get("type", "")
            if etype == "assistant":
                for block in event.get("message", {}).get("content", []):
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block["text"])
            elif etype == "result" and event.get("result"):
                text_parts.append(event["result"])
        except (json.JSONDecodeError, ValueError):
            pass
print("\n".join(text_parts))
PYEOF
)

echo "$SUMMARY" > "$SUMMARY_PATH"
echo "$SUMMARY"

rm -f "$TMPFILE" "${TMPFILE}.err"

log "Summary saved to: $SUMMARY_PATH"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

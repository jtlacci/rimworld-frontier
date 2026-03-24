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
    # Timeline summary
    if [[ -f "$RESULT_DIR/score_timeline.jsonl" ]]; then
        TIMELINE=$(python3 -c "
import json
entries = [json.loads(l) for l in open('$RESULT_DIR/score_timeline.jsonl') if l.strip()]
meals = [e.get('meals',0) for e in entries]
wild = [e.get('wild_animals',-1) for e in entries]
raw = [e.get('food_pipeline',{}).get('raw_food',0) for e in entries]
print(f'meals over time: {meals}')
print(f'wild animals: {wild}')
print(f'raw food: {raw}')
" 2>/dev/null)
        RUN_CONTEXT+="Timeline:"$'\n'"$TIMELINE"$'\n\n'
    fi
    # Audit if exists
    if [[ -f "$RESULT_DIR/audit.json" ]]; then
        AUDIT=$(python3 -c "
import json
d = json.load(open('$RESULT_DIR/audit.json'))
for chain in d.get('failure_chains', [])[:5]:
    print(f'  [{chain.get(\"category\",\"?\")}] {chain.get(\"metric\",\"?\")}: {chain.get(\"root_cause\",\"\")[:100]}')
" 2>/dev/null)
        RUN_CONTEXT+="Failure chains:"$'\n'"$AUDIT"$'\n\n'
    fi
    # Timeline issues
    if [[ -f "$RESULT_DIR/timeline_analysis.json" ]]; then
        ISSUES=$(python3 -c "
import json
d = json.load(open('$RESULT_DIR/timeline_analysis.json'))
for issue in d.get('issues', [])[:5]:
    print(f'  {issue}')
" 2>/dev/null)
        RUN_CONTEXT+="Timeline issues:"$'\n'"$ISSUES"$'\n\n'
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

echo '{"_agent":"challenger","type":"agent_start"}' >> "$FRONTIER_DIR/frontier/logs/agent_live.jsonl"
env -u CLAUDECODE claude -p \
    --model "sonnet" \
    --max-turns 200 \
    --output-format stream-json \
    --verbose \
    --dangerously-skip-permissions \
    --allowedTools "Write,WebSearch,WebFetch,mcp__qmd__query,mcp__qmd__search" \
    --no-session-persistence \
    --system-prompt "$CHALLENGER_PROMPT" \
    "Design the next version of this scenario. Project root: $FRONTIER_DIR

CURRENT SCENARIO ($SCENARIO_PATH):
$SCENARIO_CONTENT

${MISSION_RUBRIC:+MISSION RUBRIC:
$MISSION_RUBRIC

}RUN RESULTS:
$RUN_CONTEXT
INSTRUCTIONS:
1. Write the scenario JSON to $SCENARIOS_DIR/ IMMEDIATELY — do not research first.
2. Print your CHALLENGER SUMMARY with feasibility math.
3. Only use WebSearch AFTER writing if you need to verify a specific number.
4. Do NOT use the Agent tool. Do NOT read project files. You have everything above." \
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

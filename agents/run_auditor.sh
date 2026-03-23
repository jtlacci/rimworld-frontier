#!/bin/bash
# Deep-investigation auditor for a single run.
# Usage: ./agents/run_auditor.sh <result_dir>
# Example: ./agents/run_auditor.sh frontier/results/baseline/run_008
#
# Output: <result_dir>/audit.json

set -eo pipefail

RESULT_DIR="${1:?Usage: run_auditor.sh <result_dir>}"

# Source config to get FRONTIER_DIR and AGENT_REPO
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"
source "$FRONTIER_DIR/frontier/log_event.sh" 2>/dev/null || true
LIVE_LOG="$FRONTIER_DIR/frontier/logs/agent_live.jsonl"

# Resolve to absolute path
if [[ ! "$RESULT_DIR" = /* ]]; then
    RESULT_DIR="$FRONTIER_DIR/$RESULT_DIR"
fi

if [[ ! -d "$RESULT_DIR" ]]; then
    echo "ERROR: Directory not found: $RESULT_DIR" >&2
    exit 1
fi

if [[ ! -f "$RESULT_DIR/score.json" ]]; then
    echo "ERROR: No score.json in $RESULT_DIR — run scoring first" >&2
    exit 1
fi

PROMPT_FILE="$FRONTIER_DIR/AGENT_AUDITOR.md"
if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "ERROR: Auditor prompt not found: $PROMPT_FILE" >&2
    exit 1
fi

# Extract run_id and scenario
RUN_ID=$(basename "$RESULT_DIR" | sed 's/run_0*//' | sed 's/^$/0/')
SCENARIO_DIR=$(dirname "$RESULT_DIR")
SCENARIO_NAME=$(basename "$SCENARIO_DIR")

# Find previous run's audit.json for recurring issue detection
PREV_AUDIT=""
PREV_RUN_NUM=$((RUN_ID - 1))
PREV_RUN_DIR=$(printf "%s/run_%03d" "$SCENARIO_DIR" "$PREV_RUN_NUM")
if [[ -f "$PREV_RUN_DIR/audit.json" ]]; then
    PREV_AUDIT="$PREV_RUN_DIR/audit.json"
    echo "[auditor] Found previous audit: $PREV_AUDIT" >> "$LIVE_LOG"
    echo "[auditor] Found previous audit: $PREV_AUDIT"
fi

echo "[auditor] Investigating $RESULT_DIR (scenario=$SCENARIO_NAME, run=$RUN_ID)..." >> "$LIVE_LOG"
echo "[auditor] Investigating $RESULT_DIR (scenario=$SCENARIO_NAME, run=$RUN_ID)..."

SYSTEM_PROMPT="$(cat "$PROMPT_FILE")"

# Build the investigation instructions
INSTRUCTIONS="Investigate the run results in: $RESULT_DIR (scenario=$SCENARIO_NAME, run_id=$RUN_ID)

Read files in this order:
0. $RESULT_DIR/scenario.json — scenario constraints. Focus your investigation on failures most relevant to these constraints (e.g. if starting_packs=0, food pipeline is critical from tick 0).
1. $RESULT_DIR/score.json — compute points_lost per metric, identify 2+ point losses
2. $AGENT_REPO/AGENT_OVERSEER.md — extract every concrete action the overseer is told to do
3. $RESULT_DIR/score_timeline.jsonl — read first 5 lines, last 5 lines, and 3 lines from the middle. Track building_defs, food_pipeline, jobs, rooms across time.
4. $RESULT_DIR/overseer_conversation.txt — what did the overseer report doing? What SDK calls were made?
5. $RESULT_DIR/colony_map.txt — visual layout verification
6. $RESULT_DIR/machine_report.json — SDK-reported issues
7. $RESULT_DIR/after.json — final colony state (rooms, thoughts, research)"

if [[ -n "$PREV_AUDIT" ]]; then
    INSTRUCTIONS="$INSTRUCTIONS
8. $PREV_AUDIT — previous run's audit. Check if issues flagged there are still present."
fi

INSTRUCTIONS="$INSTRUCTIONS

Also read if they exist: $RESULT_DIR/scenario.json, $RESULT_DIR/telemetry_errors.log

Cross-reference AGENT_OVERSEER.md phases against timeline building_defs. Flag every action the prompt prescribes that doesn't appear in the actual build history.

Then produce the JSON audit. Output ONLY the JSON object, nothing else."

LIVE_LOG="$FRONTIER_DIR/frontier/logs/agent_live.jsonl"
live() { echo "$1"; echo "$1" >> "$LIVE_LOG"; }
echo '{"_agent":"auditor","type":"agent_start"}' >> "$LIVE_LOG"
AUDITOR_TMP=$(mktemp)
env -u CLAUDECODE claude -p \
    --model opus \
    --max-turns 25 \
    --output-format stream-json \
    --verbose \
    --allowedTools "Read,Bash,Glob,Grep" \
    --dangerously-skip-permissions \
    --no-session-persistence \
    --system-prompt "$SYSTEM_PROMPT" \
    "$INSTRUCTIONS" > >(tee -a "$LIVE_LOG" > "$AUDITOR_TMP") 2>> "$LIVE_LOG"

# Extract text from stream-json
OUTPUT=""
OUTPUT=$(python3 -c "
import json, sys
parts = []
with open('$AUDITOR_TMP') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            event = json.loads(line)
            if event.get('type') == 'assistant':
                for block in event.get('message', {}).get('content', []):
                    if isinstance(block, dict) and block.get('type') == 'text':
                        parts.append(block['text'])
            elif event.get('type') == 'result' and event.get('result'):
                parts.append(event['result'])
        except: pass
print('\n'.join(parts))
" 2>/dev/null) || true
rm -f "$AUDITOR_TMP"

# Extract JSON from output
JSON_OUTPUT=$(echo "${OUTPUT:-}" | python3 -c "
import sys, json, re

text = sys.stdin.read()

# Find the outermost JSON object containing expected keys
best = None
for m in re.finditer(r'\{', text):
    start = m.start()
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                candidate = text[start:i+1]
                try:
                    parsed = json.loads(candidate)
                    # Prefer objects with our expected keys
                    if 'failure_chains' in parsed or 'execution_gaps' in parsed:
                        print(json.dumps(parsed, indent=2))
                        sys.exit(0)
                    if best is None:
                        best = candidate
                except json.JSONDecodeError:
                    pass
                break

if best:
    try:
        print(json.dumps(json.loads(best), indent=2))
    except Exception:
        print(best)
else:
    print(json.dumps({'error': 'No valid JSON found in auditor output', 'raw_length': len(text)}))
" 2>/dev/null) || true

if [[ -z "${JSON_OUTPUT:-}" ]]; then
    echo "[auditor] ERROR: No output from auditor agent" >&2
    echo '{"error": "auditor produced no output"}' > "$RESULT_DIR/audit.json"
    exit 1
fi

echo "$JSON_OUTPUT" > "$RESULT_DIR/audit.json"

# Print summary
python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    gaps = d.get('execution_gaps', [])
    chains = d.get('failure_chains', [])
    recurring = d.get('recurring_issues', [])
    telemetry = d.get('telemetry_issues', [])
    print(f'  Score: {d.get(\"score_pct\", \"?\")}%')
    print(f'  Execution gaps: {len(gaps)}')
    for g in gaps[:3]:
        print(f'    - {g.get(\"expected\", \"?\")[:80]}')
    print(f'  Failure chains: {len(chains)}')
    for c in chains[:5]:
        print(f'    [{c.get(\"category\",\"?\")}] {c.get(\"metric\",\"?\")}: -{c.get(\"points_lost\",0):.1f}pts -> {c.get(\"root_cause\",\"?\")[:80]}')
    if recurring:
        print(f'  Recurring issues: {len(recurring)}')
        for r in recurring[:3]:
            print(f'    - {r.get(\"issue\", \"?\")[:80]}')
    if telemetry:
        print(f'  Telemetry issues: {len(telemetry)}')
except Exception as e:
    print(f'  Parse error: {e}')
" <<< "$JSON_OUTPUT"

echo "[auditor] Audit saved to $RESULT_DIR/audit.json" >> "$LIVE_LOG"
echo "[auditor] Audit saved to $RESULT_DIR/audit.json"

# Regenerate QMD summary (now includes audit findings)
python3 "$FRONTIER_DIR/frontier/summarize_run.py" "$RESULT_DIR" 2>/dev/null || true
command -v qmd &>/dev/null && qmd update 2>/dev/null || true

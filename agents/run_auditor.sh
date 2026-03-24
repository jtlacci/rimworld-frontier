#!/bin/bash
# Thread-pulling auditor for a single run.
# Usage: ./agents/run_auditor.sh <result_dir>
# Example: ./agents/run_auditor.sh frontier/results/baseline/run_008
#
# Output: <result_dir>/audit.md

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

echo "[auditor] Investigating $RESULT_DIR (scenario=$SCENARIO_NAME, run=$RUN_ID)..." >> "$LIVE_LOG"
echo "[auditor] Investigating $RESULT_DIR (scenario=$SCENARIO_NAME, run=$RUN_ID)..."

SYSTEM_PROMPT="$(cat "$PROMPT_FILE")"

# Triage instructions — auditor decides what to read
INSTRUCTIONS="Investigate the run results in: $RESULT_DIR (scenario=$SCENARIO_NAME, run_id=$RUN_ID)

Start with:
- $RESULT_DIR/score.json — triage, find top 3 point losses
- $RESULT_DIR/scenario.json — understand what's being tested

Then investigate each thread using Grep and QMD. Files available:
- $RESULT_DIR/score_timeline.jsonl — 1s snapshots (use Grep, don't Read)
- $RESULT_DIR/command_log.jsonl — every SDK call with timing (use Grep)
- $RESULT_DIR/overseer_conversation.txt — full overseer output (use Grep)
- $RESULT_DIR/colony_map.txt — ASCII map (Read only if spatial thread)
- $RESULT_DIR/machine_report.json — SDK issues (Read only if relevant)
- $RESULT_DIR/after.json — final state (Read only if relevant)
- $AGENT_REPO/AGENT_OVERSEER.md — overseer instructions (Read only if investigating execution gap)

Write your full investigation as markdown — the thinking process IS the output."

live() { echo "$1"; echo "$1" >> "$LIVE_LOG"; }
echo '{"_agent":"auditor","type":"agent_start"}' >> "$LIVE_LOG"
AUDITOR_TMP=$(mktemp)
env -u CLAUDECODE claude -p \
    --model opus \
    --max-turns 200 \
    --output-format stream-json \
    --verbose \
    --allowedTools "Read,Bash,Glob,Grep,mcp__qmd__query,mcp__qmd__search" \
    --dangerously-skip-permissions \
    --no-session-persistence \
    --system-prompt "$SYSTEM_PROMPT" \
    "$INSTRUCTIONS" > >(tee -a "$LIVE_LOG" > "$AUDITOR_TMP") 2>> "$LIVE_LOG"

# Extract full text from stream-json → save as audit.md
python3 -c "
import json
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
" > "$RESULT_DIR/audit.md" 2>/dev/null || true
rm -f "$AUDITOR_TMP"

# Print summary
SCORE=$(python3 -c "import json; print(f'{json.load(open(\"$RESULT_DIR/score.json\"))[\"pct\"]:.1f}')" 2>/dev/null || echo "?")
THREADS=$(grep -c '^## Thread' "$RESULT_DIR/audit.md" 2>/dev/null || echo "0")
BUILD_REQS=$(grep -c '^\- ' <(sed -n '/^## Build Requests/,/^## /p' "$RESULT_DIR/audit.md") 2>/dev/null || echo "0")
echo "  Score: ${SCORE}%"
echo "  Threads investigated: $THREADS"
echo "  Build requests: $BUILD_REQS"

# Extract build requests to scenario-level file
python3 -c "
import sys
text = open('$RESULT_DIR/audit.md').read()
marker = '## Build Requests'
if marker in text:
    section = text[text.index(marker):]
    # Stop at next ## heading or end
    lines = section.split('\n')
    build_lines = [lines[0]]
    for line in lines[1:]:
        if line.startswith('## '):
            break
        build_lines.append(line)
    content = '\n'.join(build_lines).strip()
    if content and content != marker:
        with open('$FRONTIER_DIR/build_requests.md', 'a') as f:
            f.write(f'\n### $SCENARIO_NAME — run $RUN_ID\n')
            # Write everything after the heading
            body = '\n'.join(build_lines[1:]).strip()
            if body:
                f.write(body + '\n')
        print(f'  Build requests appended to $FRONTIER_DIR/build_requests.md')
" 2>/dev/null || true

echo "[auditor] Audit saved to $RESULT_DIR/audit.md" >> "$LIVE_LOG"
echo "[auditor] Audit saved to $RESULT_DIR/audit.md"

# Regenerate QMD summary (audit.md is already markdown — QMD indexes it directly)
python3 "$FRONTIER_DIR/frontier/summarize_run.py" "$RESULT_DIR" 2>/dev/null || true
command -v qmd &>/dev/null && qmd update 2>/dev/null || true

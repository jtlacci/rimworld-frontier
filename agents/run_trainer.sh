#!/bin/bash
# Trainer agent — reads an audit report and applies code fixes.
# Usage: ./agents/run_trainer.sh <audit_path>
#
# Example:
#   ./agents/run_trainer.sh frontier/results/baseline/run_009/audit.md
#
# Creates a git savepoint in the AGENT repo before running.
# If the trainer breaks things: cd $AGENT_REPO && git revert HEAD
#
# The trainer can make large changes — refactors, rewrites, new methods.
# All changes are recoverable via git.

set -euo pipefail

DIAGNOSIS_PATH="${1:?Usage: run_trainer.sh <audit_json_path>}"

# Source config to get FRONTIER_DIR and AGENT_REPO
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"
source "$FRONTIER_DIR/frontier/log_event.sh" 2>/dev/null || true

# Resolve diagnosis path
if [[ ! "$DIAGNOSIS_PATH" = /* ]]; then
    DIAGNOSIS_PATH="$FRONTIER_DIR/$DIAGNOSIS_PATH"
fi

# Git savepoint in AGENT repo — snapshot current state so trainer changes can be reviewed/reverted
# After trainer runs: `cd $AGENT_REPO && git diff HEAD~1` to see changes, `git revert HEAD` to undo
cd "$AGENT_REPO"
git add -A 2>/dev/null
git commit -m "pre-trainer savepoint" --allow-empty -q 2>/dev/null || true
cd "$FRONTIER_DIR"

if [[ ! -f "$DIAGNOSIS_PATH" ]]; then
    echo "ERROR: Diagnosis file not found: $DIAGNOSIS_PATH"
    exit 1
fi

log() {
    echo "[trainer $(date '+%H:%M:%S')] $*"
}

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "TRAINER AGENT"
log "  Diagnosis: $DIAGNOSIS_PATH"
log "  Agent repo: $AGENT_REPO"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Read the diagnosis content to pass as input
DIAGNOSIS_CONTENT="$(cat "$DIAGNOSIS_PATH")"

# Build system prompt from trainer agent instructions
TRAINER_PROMPT="$(cat "$FRONTIER_DIR/AGENT_TRAINER.md")"

# Output file for the trainer summary
RUN_DIR="$(dirname "$DIAGNOSIS_PATH")"

# Extract scenario context for the trainer
SCENARIO_JSON=""
SCORE_JSON=""
SCENARIO_NAME=""
if [[ -f "$RUN_DIR/scenario.json" ]]; then
    SCENARIO_JSON="$(cat "$RUN_DIR/scenario.json")"
    SCENARIO_NAME="$(python3 -c "import json; print(json.load(open('$RUN_DIR/scenario.json')).get('name','unknown'))" 2>/dev/null || echo "unknown")"
fi
if [[ -f "$RUN_DIR/score.json" ]]; then
    SCORE_JSON="$(python3 -c "
import json
s = json.load(open('$RUN_DIR/score.json'))
# Extract top losses
losses = []
for m, info in s.get('breakdown', {}).items():
    if not isinstance(info, dict): continue
    w = info.get('adjusted_weight', info.get('weight', 0))
    sc = info.get('score', 0)
    lost = w * (1.0 - min(sc, 1.0))
    if lost >= 1.5:
        losses.append(f'  {m}: {sc:.2f} x{w:.0f} = -{lost:.1f}pts')
losses.sort(key=lambda x: float(x.split('-')[-1].replace('pts','').strip()), reverse=True)
print(f'Score: {s[\"pct\"]:.0f}% ({s[\"total\"]:.0f}/{s[\"max\"]:.0f})')
print('Top losses:')
print(chr(10).join(losses[:8]))
" 2>/dev/null || echo "")"
fi
SUMMARY_PATH="${RUN_DIR}/trainer_summary.txt"

TMPFILE=$(mktemp)
TRAINER_EXIT=0

log "Spawning trainer agent..."

unset CLAUDECODE
echo '{"_agent":"trainer","type":"agent_start"}' >> "$FRONTIER_DIR/frontier/logs/agent_live.jsonl"
env -u CLAUDECODE claude -p \
    --model "opus" \
    --max-turns 200 \
    --output-format stream-json \
    --verbose \
    --dangerously-skip-permissions \
    --allowedTools "Bash,Read,Edit,Write,Glob,Grep,mcp__qmd__query,mcp__qmd__search" \
    --system-prompt "$TRAINER_PROMPT" \
    --no-session-persistence \
    "Project root (agent repo): $AGENT_REPO

SCENARIO: $SCENARIO_NAME
${SCENARIO_JSON:+SCENARIO CONFIG:
$SCENARIO_JSON
}
${SCORE_JSON:+CURRENT SCORE:
$SCORE_JSON
}
AUDIT (from $DIAGNOSIS_PATH):

$DIAGNOSIS_CONTENT" \
    > >(tee -a $FRONTIER_DIR/frontier/logs/agent_live.jsonl > "$TMPFILE") 2>> "$FRONTIER_DIR/frontier/logs/agent_live.jsonl" &
TRAINER_PID=$!

# Wait for trainer to finish (no timeout)
wait "$TRAINER_PID" || TRAINER_EXIT=$?

ELAPSED=$(( $(date +%s) - $(date -r "$TMPFILE" +%s 2>/dev/null || echo $(date +%s)) ))
log "Trainer finished (exit=$TRAINER_EXIT, ${ELAPSED}s)"

# Extract trainer output from stream-json
python3 << PYEOF - "$TMPFILE" "$SUMMARY_PATH"
import json, sys

tmpfile = sys.argv[1]
summary_path = sys.argv[2]

text_parts = []
with open(tmpfile) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = event.get("type", "")
        if etype == "assistant":
            msg = event.get("message", event)
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block["text"])
        elif etype == "result":
            if event.get("result"):
                text_parts.append(event["result"])

full_text = "\n".join(text_parts)

# Save full output
with open(summary_path, "w") as f:
    f.write(full_text)

# Print the TRAINER SUMMARY section if present
if "=== TRAINER SUMMARY ===" in full_text:
    start = full_text.index("=== TRAINER SUMMARY ===")
    end_marker = "=== END TRAINER SUMMARY ==="
    if end_marker in full_text:
        end = full_text.index(end_marker) + len(end_marker)
    else:
        end = len(full_text)
    print(full_text[start:end])
else:
    # Print last 50 lines as fallback
    lines = full_text.strip().split("\n")
    for line in lines[-50:]:
        print(line)

# Print usage info
usage_data = {}
with open(tmpfile) as f:
    for line in f:
        try:
            event = json.loads(line.strip())
            if event.get("type") == "result":
                usage_data = event.get("usage", {})
        except (json.JSONDecodeError, ValueError):
            pass
if usage_data:
    input_tok = usage_data.get("input_tokens", 0) + usage_data.get("cache_read_input_tokens", 0)
    output_tok = usage_data.get("output_tokens", 0)
    print(f"\nTokens: {input_tok + output_tok} (in={input_tok}, out={output_tok})")
PYEOF

# Extract structured changelog JSON from trainer output
python3 << 'CLEOF' - "$SUMMARY_PATH" "$RUN_DIR/trainer_changelog.json"
import json, re, sys

summary_path = sys.argv[1]
changelog_path = sys.argv[2]

with open(summary_path) as f:
    text = f.read()

changelog = None

# Try to extract the structured JSON block
start_marker = "=== TRAINER CHANGELOG JSON ==="
end_marker = "=== END TRAINER CHANGELOG JSON ==="
if start_marker in text and end_marker in text:
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker)
    raw = text[start:end].strip()
    try:
        changelog = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"WARNING: TRAINER CHANGELOG JSON block found but invalid JSON: {e}", file=sys.stderr)

# Fallback: parse [file] description lines from text summary
if changelog is None:
    print("NOTE: No valid TRAINER CHANGELOG JSON block found, falling back to text parsing", file=sys.stderr)
    changes = []
    summary_start = "=== TRAINER SUMMARY ==="
    summary_end = "=== END TRAINER SUMMARY ==="
    if summary_start in text:
        s = text.index(summary_start)
        e = text.index(summary_end) if summary_end in text else len(text)
        summary_block = text[s:e]
        for m in re.finditer(r'^\[([^\]]+)\]\s+(.+)$', summary_block, re.MULTILINE):
            changes.append({"file": m.group(1).strip(), "description": m.group(2).strip()})
    changelog = {
        "audit_source": "unknown",
        "changes": changes,
        "issue_addressed": "parsed from text summary (no JSON block)",
        "validation": "unknown",
        "_fallback": True
    }

with open(changelog_path, "w") as f:
    json.dump(changelog, f, indent=2)
print(f"Changelog written to {changelog_path}")
CLEOF

# Cleanup
rm -f "$TMPFILE" "${TMPFILE}.err"

# Commit trainer changes in AGENT repo (so they can be reviewed/reverted)
cd "$AGENT_REPO"
git add -A 2>/dev/null
git commit -m "trainer: applied fixes from $(basename $(dirname $DIAGNOSIS_PATH))" -q 2>/dev/null || true
log "Changes committed in $AGENT_REPO. Review: git diff HEAD~1  Revert: git revert HEAD"

log "Summary saved to: $SUMMARY_PATH"

# Regenerate QMD summary (now includes trainer fixes)
TRAIN_RESULT_DIR="$(dirname "$DIAGNOSIS_PATH")"
python3 "$FRONTIER_DIR/frontier/summarize_run.py" "$TRAIN_RESULT_DIR" 2>/dev/null || true
command -v qmd &>/dev/null && qmd update 2>/dev/null || true

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

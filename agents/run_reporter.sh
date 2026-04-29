#!/bin/bash
# Reporter — generate playtest_report.md for a finished run.
# Usage: ./agents/run_reporter.sh <result_dir>
# Output: <result_dir>/playtest_report.md

set -eo pipefail

RESULT_DIR="${1:?Usage: run_reporter.sh <result_dir>}"

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

if [[ ! -f "$RESULT_DIR/scenario.json" ]]; then
    echo "ERROR: No scenario.json in $RESULT_DIR" >&2
    exit 1
fi

PROMPT_FILE="$FRONTIER_DIR/AGENT_REPORTER.md"
if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "ERROR: Reporter prompt not found: $PROMPT_FILE" >&2
    exit 1
fi

SCENARIO_NAME=$(basename "$(dirname "$RESULT_DIR")")
RUN_ID=$(basename "$RESULT_DIR" | sed 's/run_0*//' | sed 's/^$/0/')

# Make sure pass criteria are evaluated before the agent runs
python3 -c "
import sys, json
from pathlib import Path
sys.path.insert(0, '$FRONTIER_DIR')
from frontier.scenario import ScenarioConfig
from frontier.criteria import write_report

run_dir = Path('$RESULT_DIR')
scenario = ScenarioConfig.load(run_dir / 'scenario.json')
report = write_report(run_dir, scenario.pass_criteria or [])
print(f'  Criteria: {report[\"summary\"][\"pass\"]}/{report[\"summary\"][\"total\"]} pass, {report[\"summary\"][\"fail\"]} fail, {report[\"summary\"][\"deferred\"]} deferred')
"

echo "[reporter] Writing playtest report for $RESULT_DIR (scenario=$SCENARIO_NAME, run=$RUN_ID)..."

SYSTEM_PROMPT="$(cat "$PROMPT_FILE")"

INSTRUCTIONS="Write the playtest report for: $RESULT_DIR

Scenario: $SCENARIO_NAME (run $RUN_ID)

Start by reading these (in order):
1. $RESULT_DIR/scenario.json — what's being tested (mod_under_test, pass_criteria, observe)
2. $RESULT_DIR/playtest_report.json — pre-evaluated pass/fail per criterion
3. $RESULT_DIR/score.json — quantitative signal (if a scoring rubric was defined)

Then investigate failures and observe questions using Grep against:
- $RESULT_DIR/score_timeline.jsonl
- $RESULT_DIR/command_log.jsonl
- $RESULT_DIR/overseer_conversation.txt
- $RESULT_DIR/after.json
- $RESULT_DIR/before.json

When you have evidence, write your final report to $RESULT_DIR/playtest_report.md using the Write tool. Follow the format in the system prompt. Mod-builder framing only — do not suggest agent or harness changes."

echo '{"_agent":"reporter","type":"agent_start"}' >> "$LIVE_LOG"
python3 "$AGENT_HARNESS" \
    --model "${MODEL_REPORTER:-${MODEL_AUDITOR:-qwen3.5-397b-a17b}}" \
    --system "$SYSTEM_PROMPT" \
    --message "$INSTRUCTIONS" \
    --tools "Read,Bash,Glob,Grep,Write" \
    --max-turns 80 \
    >> "$LIVE_LOG" 2>> "$LIVE_LOG"

if [[ -f "$RESULT_DIR/playtest_report.md" ]]; then
    echo "[reporter] Report saved: $RESULT_DIR/playtest_report.md"
else
    echo "[reporter] WARNING: playtest_report.md was not written" >&2
fi

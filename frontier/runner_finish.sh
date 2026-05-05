#!/bin/bash
# Playtest finish — stop monitor, take after-snapshot, score, evaluate criteria, capture map.
#
# Run AFTER the overseer subagent finishes (timed out, game-day cap hit, or completed).
#
# Usage: ./frontier/runner_finish.sh <result_dir> [overseer_exit_code]
#
# overseer_exit_code: pass 124 if the overseer was killed by a timeout/day-cap (so a save
# is taken before snapshotting); 0 if it exited normally. Defaults to 0.
#
# Outputs (to <result_dir>/):
#   after.json, score.json, timeline_analysis.json, charts/*.png,
#   playtest_report.json, colony_map.txt, player_run.log
#
# After this completes, the orchestrator should write playtest_report.md
# (using AGENT_REPORTER.md as a guide).

set -uo pipefail

RESULT_DIR="${1:?Usage: runner_finish.sh <result_dir> [overseer_exit_code]}"
OVERSEER_EXIT="${2:-0}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"
source "$FRONTIER_DIR/frontier/log_event.sh" 2>/dev/null || true

if [[ ! -d "$RESULT_DIR" ]]; then
    echo "ERROR: result dir not found: $RESULT_DIR" >&2
    exit 1
fi

SCENARIO_JSON="$RESULT_DIR/scenario.json"
if [[ ! -f "$SCENARIO_JSON" ]]; then
    echo "ERROR: scenario.json missing in $RESULT_DIR" >&2
    exit 1
fi

SCENARIO_NAME=$("$PYTHON" -c "import json; print(json.load(open('$SCENARIO_JSON'))['name'])")
MAP_SIZE=$("$PYTHON" -c "import json; print(json.load(open('$SCENARIO_JSON')).get('map_size', 50))")
SAVE_NAME="Frontier-${SCENARIO_NAME}"

LIVE_LOG="$FRONTIER_DIR/frontier/logs/agent_live.jsonl"
log() {
    echo "[frontier $(date '+%H:%M:%S')] $*" >&2
    echo "[runner] $*" >> "$LIVE_LOG" 2>/dev/null
}

phase_mark() {
    echo "{\"phase\":\"$1\",\"event\":\"$2\",\"ts\":$(date +%s)}" >> "$RESULT_DIR/phases.jsonl"
}

# Compute duration from the marker the setup phase wrote
START_TS=$(cat "$RESULT_DIR/.overseer_start_ts" 2>/dev/null || echo "$(date +%s)")
END_TS=$(date +%s)
DURATION=$((END_TS - START_TS))

log "========== PLAYTEST FINISH: $SCENARIO_NAME =========="
log "Overseer duration: ${DURATION}s (exit=$OVERSEER_EXIT)"

# If overseer was killed, take an emergency save first
if [[ "$OVERSEER_EXIT" == "124" ]]; then
    "$PYTHON" -c "
import sys; sys.path.insert(0, '$FRONTIER_DIR/sdk')
from rimworld import RimClient
r = RimClient(); r.pause(); r.save(name='$SAVE_NAME'); r.close()
" 2>/dev/null || true
fi

phase_mark "overseer" "end"

# ─── Stop score monitor ───
MONITOR_PID=$(cat "$RESULT_DIR/.monitor.pid" 2>/dev/null || echo "")
if [[ -n "$MONITOR_PID" ]]; then
    log "Stopping score monitor (pid=$MONITOR_PID)..."
    kill "$MONITOR_PID" 2>/dev/null || true
    wait "$MONITOR_PID" 2>/dev/null || true
fi

# ─── Capture player log slice ───
PLAYER_LOG=$(cat "$RESULT_DIR/.player_log_path" 2>/dev/null || echo "")
PLAYER_LOG_START_LINE=$(cat "$RESULT_DIR/.player_log_start_line" 2>/dev/null || echo "0")
if [[ -n "$PLAYER_LOG" && -f "$PLAYER_LOG" ]]; then
    tail -n +"$((PLAYER_LOG_START_LINE + 1))" "$PLAYER_LOG" > "$RESULT_DIR/player_run.log" 2>/dev/null || true
fi

# ─── Phase 4: After snapshot + scoring ───
phase_mark "scoring" "start"
log "Taking after snapshot and scoring..."

"$PYTHON" << PYEOF - "$RESULT_DIR" "$DURATION" "$SCENARIO_JSON" >&2
import sys, json, os; sys.path.insert(0, '$FRONTIER_DIR/sdk'); sys.path.insert(0, '$FRONTIER_DIR')
from rimworld import RimClient
from snapshot import take_snapshot, compare_snapshots

result_dir = sys.argv[1]
duration_s = int(sys.argv[2])
scenario_json = sys.argv[3]

from frontier.scenario import ScenarioConfig
from frontier.scoring import score_scenario

config = ScenarioConfig.from_json(open(scenario_json).read())

r = RimClient()
r.pause()
after = take_snapshot(r)
with open(f"{result_dir}/after.json", "w") as f:
    json.dump(after, f, indent=2, default=str)

with open(f"{result_dir}/before.json") as f:
    before = json.load(f)

# Token/cost tracking removed with the DashScope harness — pass zeros.
overseer_tokens = 0
overseer_cost = 0

timeline = None
timeline_path = os.path.join(result_dir, "score_timeline.jsonl")
if os.path.isfile(timeline_path):
    timeline = []
    with open(timeline_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    timeline.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    if not timeline:
        timeline = None

score_data = score_scenario(config, before, after, duration_s, overseer_tokens, overseer_cost, timeline=timeline)

with open(f"{result_dir}/score.json", "w") as f:
    json.dump(score_data, f, indent=2)

print(f"SCORE: {score_data['total']}/{score_data['max']} ({score_data['pct']:.0f}%) "
      f"[base: {score_data['base_total']}/{score_data['base_max']} ({score_data['base_pct']:.0f}%)]")
print(f"Scenario: {config.name} | Difficulty: {config.overall_difficulty():.2f} | Duration: {duration_s}s")

if score_data.get("adjustments"):
    print(f"Weight adjustments: {score_data['adjustments']}")

r.close()
PYEOF
phase_mark "scoring" "end"

# ─── Phase 4b: Timeline analysis ───
phase_mark "timeline_analysis" "start"
log "Analyzing run timeline..."
"$PYTHON" "$FRONTIER_DIR/frontier/_analyze_timeline.py" "$RESULT_DIR" >&2 || log "Timeline analysis failed (continuing)"
phase_mark "timeline_analysis" "end"

# ─── Phase 4c: Generate timeline charts ───
phase_mark "charts" "start"
log "Generating timeline charts..."
"$PYTHON" "$FRONTIER_DIR/frontier/timeline_charts.py" "$RESULT_DIR" 2>/dev/null || log "Charts skipped (matplotlib not available)"
phase_mark "charts" "end"

# ─── Phase 5: Evaluate pass criteria ───
phase_mark "criteria" "start"
log "Evaluating pass_criteria..."

"$PYTHON" << PYEOF - "$RESULT_DIR" "$SCENARIO_JSON" >&2
import sys, json
from pathlib import Path
sys.path.insert(0, '$FRONTIER_DIR')
from frontier.scenario import ScenarioConfig
from frontier.criteria import write_report

result_dir = Path(sys.argv[1])
scenario = ScenarioConfig.from_json(open(sys.argv[2]).read())

criteria = scenario.pass_criteria or []
report = write_report(result_dir, criteria)

s = report["summary"]
print(f"Playtest: {report['overall'].upper()} — {s['pass']}/{s['total']} pass, {s['fail']} fail, {s['deferred']} deferred")
for c in report["criteria"]:
    marker = {"pass": "[PASS]", "fail": "[FAIL]", "deferred": "[REVIEW]", "error": "[ERR]"}.get(c["status"], "[?]")
    print(f"  {marker} {c['name']}: {c['detail']}")
PYEOF
phase_mark "criteria" "end"

# ─── Phase 6: Colony map ───
phase_mark "colony_map" "start"
log "Capturing colony map..."
"$PYTHON" << PYEOF - "$RESULT_DIR" "$MAP_SIZE" >&2
import sys, json; sys.path.insert(0, '$FRONTIER_DIR/sdk')
from rimworld import RimClient

result_dir = sys.argv[1]
map_size = int(sys.argv[2])

r = RimClient()
cols = r.colonists().get("colonists", [])
if cols:
    xs = [c["position"]["x"] for c in cols if "position" in c]
    zs = [c["position"]["z"] for c in cols if "position" in c]
    cx = sum(xs) // len(xs)
    cz = sum(zs) // len(zs)
else:
    cx, cz = map_size // 2, map_size // 2

radius = min(20, map_size // 2)
x1, z1 = max(0, cx - radius), max(0, cz - radius)
x2, z2 = min(map_size, cx + radius), min(map_size, cz + radius)

try:
    detailed = r.survey_detailed_ascii(x1=x1, z1=z1, x2=x2, z2=z2, scale=1)
except Exception as e:
    detailed = None
    print(f"survey_detailed_ascii failed: {e}")

if detailed is None:
    try:
        detailed = r.survey_composite_ascii(x1=x1, z1=z1, x2=x2, z2=z2, scale=1)
    except Exception as e:
        detailed = {"error": str(e)}

with open(f"{result_dir}/colony_map.txt", "w") as f:
    f.write(f"Colony map ({x1},{z1}) to ({x2},{z2}), center=({cx},{cz})\n\n")

    if isinstance(detailed, dict) and "grid" in detailed:
        grid = detailed["grid"]
        legend = detailed.get("legend", {})

        width = max(len(row) for row in grid) if grid else 0
        if width > 0:
            tens = "".join([str((x1 + i) // 10 % 10) if (x1 + i) % 10 == 0 else " " for i in range(width)])
            ones = "".join([str((x1 + i) % 10) for i in range(width)])
            f.write(f"     {tens}\n")
            f.write(f"     {ones}\n")

        for i, row in enumerate(grid):
            z = z1 + i
            f.write(f"{z:3d}  {row}\n")

        f.write(f"\n── LEGEND ──\n")
        for ch, desc in sorted(legend.items()):
            f.write(f"  {ch:3s} = {desc}\n")
    else:
        f.write(json.dumps(detailed, indent=2) if isinstance(detailed, dict) else str(detailed))

r.close()
print(f"Colony map saved (center={cx},{cz})")
PYEOF
phase_mark "colony_map" "end"

# ─── Cleanup hidden state files ───
rm -f "$RESULT_DIR/.monitor.pid" "$RESULT_DIR/.overseer_start_ts" "$RESULT_DIR/.player_log_start_line" "$RESULT_DIR/.player_log_path"

log "========== PLAYTEST FINISH: $SCENARIO_NAME COMPLETE =========="
log "Results: $RESULT_DIR/"

"$PYTHON" "$FRONTIER_DIR/frontier/summarize_run.py" "$RESULT_DIR" 2>/dev/null || true

if command -v qmd &>/dev/null; then
    qmd update 2>/dev/null || true
fi

RUN_SCORE=$("$PYTHON" -c "import json; d=json.load(open('$RESULT_DIR/score.json')); print(f'{d[\"pct\"]:.1f}%')" 2>/dev/null || echo "?")
log_event "runner" "$SCENARIO_NAME" "$(basename "$RESULT_DIR"): $RUN_SCORE (${DURATION}s)" 2>/dev/null || true

# Emit a single JSON line summarizing the result
"$PYTHON" -c "
import json
report = json.load(open('$RESULT_DIR/playtest_report.json'))
score = json.load(open('$RESULT_DIR/score.json'))
print(json.dumps({
    'result_dir': '$RESULT_DIR',
    'scenario_name': '$SCENARIO_NAME',
    'overall': report['overall'],
    'criteria': report['summary'],
    'score_pct': score['pct'],
    'duration_s': $DURATION,
}))
"

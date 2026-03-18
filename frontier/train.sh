#!/bin/bash
# Frontier training loop — iteratively runs scenarios to map the capability frontier.
# Usage: ./frontier/train.sh [max_runs] [budget_usd]
#
# Scenario selection priority:
#   1. Untested calibration scenarios (never run before)
#   2. FRONTIER scenarios (40-85% score) — room for improvement
#   3. Skip MASTERED and IMPOSSIBLE
#
# Stops when: max_runs hit, budget exhausted, or no scenarios to run.
# At the end, prints a batch summary with heatmap, failure clusters, and top losses.

set -uo pipefail
# NOT set -e — individual scenario failures should not abort training

MAX_RUNS="${1:-5}"
BUDGET_USD="${2:-2.00}"

# Source config to get FRONTIER_DIR and AGENT_REPO
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

BATCH_START=$(date +%s)
BATCH_ID=$(date '+%Y%m%d_%H%M%S')

log() {
    echo "[train $(date '+%H:%M:%S')] $*"
}

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "FRONTIER TRAINING LOOP"
log "  Max runs:  $MAX_RUNS"
log "  Budget:    \$$BUDGET_USD"
log "  Batch ID:  $BATCH_ID"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Ensure scenario configs exist for all calibration scenarios
cd "$FRONTIER_DIR"
python3 << 'PYEOF'
import sys; sys.path.insert(0, '.')
from frontier.calibration import CALIBRATION_SCENARIOS
from pathlib import Path

scenarios_dir = Path("frontier/scenarios")
scenarios_dir.mkdir(exist_ok=True)

for s in CALIBRATION_SCENARIOS:
    path = scenarios_dir / f"{s.name}.json"
    if not path.exists():
        s.save(path)
        print(f"  Generated config: {s.name}")
PYEOF

COMPLETED=0
PASSED=0
FAILED=0
SKIPPED=0
BATCH_RESULTS=()

for RUN_NUM in $(seq 1 "$MAX_RUNS"); do
    log ""
    log "── Selecting scenario ($RUN_NUM/$MAX_RUNS) ──"

    # Python selector: picks next scenario and outputs JSON path + metadata
    SELECTION=$(cd "$FRONTIER_DIR" && python3 << 'PYEOF' - "$BUDGET_USD"
import sys, json
sys.path.insert(0, '.')

from frontier.tracker import FrontierTracker, ScenarioStatus
from frontier.calibration import CALIBRATION_SCENARIOS
from frontier.generator import AdversarialGenerator
from pathlib import Path

budget_usd = float(sys.argv[1])
tracker = FrontierTracker()

# Check budget
spent = tracker.state.get("total_cost_usd", 0.0)
remaining = budget_usd - spent
if remaining <= 0.05:
    print(json.dumps({"stop": "budget_exhausted", "spent": spent, "budget": budget_usd}))
    sys.exit(0)

# Priority 1: Untested calibration scenarios
tested = set(tracker.state.get("scenarios", {}).keys())
untested = [s for s in CALIBRATION_SCENARIOS if s.name not in tested]

if untested:
    pick = untested[0]
    reason = f"untested calibration ({len(untested)} remaining)"
else:
    # Priority 2: FRONTIER scenarios (40-85% score range, room for improvement)
    frontier_names = []
    for name, entry in tracker.state.get("scenarios", {}).items():
        status = entry.get("status", "UNKNOWN")
        avg = entry.get("avg_score", 0)
        if status == "FRONTIER" and 40 <= avg <= 85:
            frontier_names.append((name, avg))

    if frontier_names:
        # Pick the lowest-scoring frontier scenario (most room to improve)
        frontier_names.sort(key=lambda x: x[1])
        pick_name = frontier_names[0][0]

        # Try to load from scenarios dir or calibration
        scenario_path = Path("frontier/scenarios") / f"{pick_name}.json"
        if scenario_path.exists():
            from frontier.scenario import ScenarioConfig
            pick = ScenarioConfig.load(scenario_path)
        else:
            from frontier.calibration import get_scenario
            pick = get_scenario(pick_name)
            if pick is None:
                # Use adversarial generator as fallback
                gen = AdversarialGenerator(tracker)
                pick = gen.next_scenario()

        reason = f"frontier retry ({pick_name} @ {frontier_names[0][1]:.1f}%)"
    else:
        # Priority 3: Use adversarial generator for exploration
        gen = AdversarialGenerator(tracker)
        pick = gen.next_scenario()
        reason = "adversarial exploration"

# Ensure config file exists
scenarios_dir = Path("frontier/scenarios")
scenarios_dir.mkdir(exist_ok=True)
config_path = scenarios_dir / f"{pick.name}.json"
pick.save(config_path)

# Determine run_id for this scenario
scenario_entry = tracker.state.get("scenarios", {}).get(pick.name, {})
existing_runs = scenario_entry.get("runs", [])
run_id = max(existing_runs) + 1 if existing_runs else 1

print(json.dumps({
    "scenario": pick.name,
    "config_path": str(config_path),
    "run_id": run_id,
    "reason": reason,
    "spent": spent,
    "remaining": round(remaining, 4),
    "difficulty": round(pick.overall_difficulty(), 2),
}))
PYEOF
)

    if [[ -z "$SELECTION" ]]; then
        log "ERROR: Selector returned empty output"
        break
    fi

    # Parse selection
    STOP=$(echo "$SELECTION" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stop',''))")
    if [[ -n "$STOP" ]]; then
        SPENT=$(echo "$SELECTION" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"\${d.get('spent',0):.4f}\")")
        log "STOPPING: $STOP (spent \$$SPENT of \$$BUDGET_USD budget)"
        break
    fi

    SCENARIO_NAME=$(echo "$SELECTION" | python3 -c "import sys,json; print(json.load(sys.stdin)['scenario'])")
    CONFIG_PATH=$(echo "$SELECTION" | python3 -c "import sys,json; print(json.load(sys.stdin)['config_path'])")
    RUN_ID=$(echo "$SELECTION" | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
    REASON=$(echo "$SELECTION" | python3 -c "import sys,json; print(json.load(sys.stdin)['reason'])")
    REMAINING=$(echo "$SELECTION" | python3 -c "import sys,json; print(json.load(sys.stdin)['remaining'])")
    DIFFICULTY=$(echo "$SELECTION" | python3 -c "import sys,json; print(json.load(sys.stdin)['difficulty'])")

    log "Selected: $SCENARIO_NAME (run $RUN_ID)"
    log "  Reason:     $REASON"
    log "  Difficulty:  $DIFFICULTY"
    log "  Budget left: \$$REMAINING"

    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "[$RUN_NUM/$MAX_RUNS] Running: $SCENARIO_NAME (run $RUN_ID)"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    RUN_START=$(date +%s)

    # CONFIG_PATH is relative to FRONTIER_DIR
    if bash "$FRONTIER_DIR/frontier/runner.sh" "$FRONTIER_DIR/$CONFIG_PATH" "$RUN_ID"; then
        PASSED=$((PASSED + 1))
        STATUS="PASS"
    else
        FAILED=$((FAILED + 1))
        STATUS="FAIL"
    fi

    COMPLETED=$((COMPLETED + 1))
    RUN_END=$(date +%s)
    RUN_DURATION=$((RUN_END - RUN_START))

    # Read cost from result
    RESULT_DIR="$FRONTIER_DIR/frontier/results/${SCENARIO_NAME}/run_$(printf '%03d' $RUN_ID)"
    RUN_COST=$(python3 -c "
import json
try:
    with open('$RESULT_DIR/overseer_usage.json') as f:
        print(f'{json.load(f).get(\"total_cost_usd\", 0):.4f}')
except: print('0.0000')
" 2>/dev/null)
    RUN_SCORE=$(python3 -c "
import json
try:
    with open('$RESULT_DIR/score.json') as f:
        d = json.load(f)
        print(f'{d.get(\"pct\", 0):.1f}')
except: print('0.0')
" 2>/dev/null)

    BATCH_RESULTS+=("$SCENARIO_NAME:$RUN_ID:$STATUS:$RUN_SCORE:$RUN_COST:${RUN_DURATION}s")

    log "[$RUN_NUM/$MAX_RUNS] $SCENARIO_NAME: $STATUS (${RUN_SCORE}%, \$$RUN_COST, ${RUN_DURATION}s)"

    # Check budget after run
    TOTAL_SPENT=$(python3 -c "
import json
try:
    with open('$FRONTIER_DIR/frontier/frontier_state.json') as f:
        print(f'{json.load(f).get(\"total_cost_usd\", 0):.4f}')
except: print('0.0000')
" 2>/dev/null)

    OVER_BUDGET=$(python3 -c "print('yes' if float('$TOTAL_SPENT') >= float('$BUDGET_USD') else 'no')")
    if [[ "$OVER_BUDGET" == "yes" ]]; then
        log "Budget exhausted (\$$TOTAL_SPENT >= \$$BUDGET_USD) — stopping"
        break
    fi
done

BATCH_END=$(date +%s)
BATCH_DURATION=$((BATCH_END - BATCH_START))

# ─── Batch Summary ───
log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "TRAINING BATCH COMPLETE ($BATCH_ID)"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log ""
log "  Completed: $COMPLETED | Passed: $PASSED | Failed: $FAILED"
log "  Wall time: ${BATCH_DURATION}s ($(( BATCH_DURATION / 60 ))m $(( BATCH_DURATION % 60 ))s)"
log ""

# Print per-run results table
log "── Run Results ──"
printf "  %-20s %5s %8s %8s %8s %8s\n" "SCENARIO" "RUN" "STATUS" "SCORE" "COST" "TIME"
printf "  %-20s %5s %8s %8s %8s %8s\n" "────────────────────" "─────" "────────" "────────" "────────" "────────"
for ENTRY in "${BATCH_RESULTS[@]}"; do
    IFS=':' read -r NAME RID STAT SCORE COST DUR <<< "$ENTRY"
    printf "  %-20s %5s %8s %7s%% %7s$ %8s\n" "$NAME" "$RID" "$STAT" "$SCORE" "$COST" "$DUR"
done

log ""

# Full frontier analysis
cd "$FRONTIER_DIR"
python3 << 'PYEOF'
import sys, json
sys.path.insert(0, '.')

from frontier.tracker import FrontierTracker
from frontier.visualize import frontier_heatmap, frontier_summary
from frontier.analyzer import analyze_run, summarize_failures, FailureAnalysis
from frontier.scenario import ScenarioConfig
from pathlib import Path

tracker = FrontierTracker()

# ── Heatmap ──
print(frontier_heatmap(tracker))
print()
print(frontier_summary(tracker))
print()

# ── Failure clusters across ALL runs ──
all_failures: list[FailureAnalysis] = []
all_top_losses: dict[str, float] = {}  # metric -> total points lost

for name, entry in tracker.state.get("scenarios", {}).items():
    for result in entry.get("results", []):
        # Accumulate top losses
        for loss in result.get("top_losses", []):
            metric = loss["metric"]
            lost = loss["lost"]
            all_top_losses[metric] = all_top_losses.get(metric, 0) + lost

        # Try to load config for failure analysis
        config_path = Path("frontier/scenarios") / f"{name}.json"
        if not config_path.exists():
            continue
        config = ScenarioConfig.load(config_path)
        score_path = None
        # Find latest score.json for this scenario
        results_dir = Path("frontier/results") / name
        if results_dir.exists():
            run_dirs = sorted(results_dir.iterdir())
            for rd in reversed(run_dirs):
                sp = rd / "score.json"
                if sp.exists():
                    score_path = sp
                    break

        if score_path:
            try:
                score_data = json.loads(score_path.read_text())
                failures = analyze_run(config, score_data)
                all_failures.extend(failures)
            except Exception:
                pass

# ── Top losses across all runs ──
if all_top_losses:
    print("── TOP POINT LOSSES (cumulative across all runs) ──")
    sorted_losses = sorted(all_top_losses.items(), key=lambda x: -x[1])
    for metric, total_lost in sorted_losses[:10]:
        print(f"  {metric:<25s}  {total_lost:>6.1f} pts lost")
    print()

# ── Failure clusters ──
if all_failures:
    category_counts: dict[str, int] = {}
    category_severity: dict[str, list[str]] = {}
    for f in all_failures:
        category_counts[f.category] = category_counts.get(f.category, 0) + 1
        if f.category not in category_severity:
            category_severity[f.category] = []
        category_severity[f.category].append(f.severity)

    print("── FAILURE CLUSTERS ──")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        severities = category_severity[cat]
        crit = severities.count("critical")
        major = severities.count("major")
        minor = severities.count("minor")
        parts = []
        if crit: parts.append(f"{crit} critical")
        if major: parts.append(f"{major} major")
        if minor: parts.append(f"{minor} minor")
        print(f"  {cat:<20s}  {count} occurrences ({', '.join(parts)})")
    print()

# ── Eval regression check ──
# Compare first vs latest run for scenarios with 2+ runs
regressions = []
improvements = []
for name, entry in tracker.state.get("scenarios", {}).items():
    results = entry.get("results", [])
    if len(results) < 2:
        continue
    first_score = results[0].get("adjusted_score_pct", 0)
    latest_score = results[-1].get("adjusted_score_pct", 0)
    delta = latest_score - first_score
    if delta < -5:
        regressions.append((name, first_score, latest_score, delta))
    elif delta > 5:
        improvements.append((name, first_score, latest_score, delta))

if regressions or improvements:
    print("── EVAL REGRESSION CHECK ──")
    if improvements:
        for name, first, latest, delta in sorted(improvements, key=lambda x: -x[3]):
            print(f"  IMPROVED  {name:<20s}  {first:.1f}% -> {latest:.1f}%  (+{delta:.1f})")
    if regressions:
        for name, first, latest, delta in sorted(regressions, key=lambda x: x[3]):
            print(f"  REGRESSED {name:<20s}  {first:.1f}% -> {latest:.1f}%  ({delta:.1f})")
    print()

# ── Scenario status summary ──
print("── SCENARIO STATUS ──")
for name, entry in sorted(tracker.state.get("scenarios", {}).items()):
    status = entry.get("status", "???")
    avg = entry.get("avg_score", 0)
    num = len(entry.get("runs", []))
    print(f"  {name:<25s}  {status:<10s}  avg={avg:.1f}%  runs={num}")
PYEOF

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "State:   $FRONTIER_DIR/frontier/frontier_state.json"
log "Results: $FRONTIER_DIR/frontier/results/"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

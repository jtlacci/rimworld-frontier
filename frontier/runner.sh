#!/bin/bash
# Frontier scenario runner — parameterized version of auditor_loop.sh
# Usage: ./frontier/runner.sh <scenario_config.json> [run_id]
#
# Accepts a scenario JSON config instead of hardcoded "Baseline-Starter".
# Hard timeout: 300s (5 min). Overseer gets max 3 tool calls.
# Results saved to frontier/results/<scenario_name>/run_<id>/
#
# Requires: AGENT_REPO env var (or source config.sh first)

set -euo pipefail

SCENARIO_JSON="${1:?Usage: runner.sh <scenario_config.json> [run_id]}"
RUN_ID="${2:-1}"

# Source config to get FRONTIER_DIR and AGENT_REPO
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"
source "$FRONTIER_DIR/frontier/log_event.sh" 2>/dev/null || true

# Parse scenario config
SCENARIO_NAME=$(python3 -c "import json; print(json.load(open('$SCENARIO_JSON'))['name'])")
SAVE_NAME="Frontier-${SCENARIO_NAME}"
MAP_SIZE=$(python3 -c "import json; print(json.load(open('$SCENARIO_JSON')).get('map_size', 50))")

OVERSEER_MODEL="sonnet"
OVERSEER_TIMEOUT=450  # 7.5 min hard limit for frontier runs

RESULT_DIR="$FRONTIER_DIR/frontier/results/${SCENARIO_NAME}/run_$(printf '%03d' $RUN_ID)"
mkdir -p "$RESULT_DIR"

# Copy scenario config to results
cp "$SCENARIO_JSON" "$RESULT_DIR/scenario.json"

if [[ "$OSTYPE" == "darwin"* ]]; then
    RIMWORLD_APP="$HOME/Library/Application Support/Steam/steamapps/common/RimWorld/RimWorldMac.app"
elif [[ "$OSTYPE" == "linux"* ]]; then
    RIMWORLD_APP="$HOME/.steam/steam/steamapps/common/RimWorld"
else
    RIMWORLD_APP="$PROGRAMFILES/Steam/steamapps/common/RimWorld"
fi

LIVE_LOG="$FRONTIER_DIR/frontier/logs/agent_live.jsonl"
log() {
    echo "[frontier $(date '+%H:%M:%S')] $*"
    echo "[runner] $*" >> "$LIVE_LOG" 2>/dev/null
}

ensure_game_running() {
    if ! pgrep -f "RimWorld" >/dev/null 2>&1; then
        log "RimWorld not running — launching..."
        open "$RIMWORLD_APP" &
        for i in $(seq 1 60); do
            sleep 5
            if python3 -c "
import sys; sys.path.insert(0, '$AGENT_REPO/sdk')
from rimworld import RimClient
r = RimClient(); r.close()
" 2>/dev/null; then
                log "RimWorld connected after ${i}x5s"
                return 0
            fi
        done
        log "ERROR: RimWorld failed to start after 300s"
        return 1
    fi
    return 0
}

kill_and_restart_game() {
    log "Killing frozen RimWorld..."
    pkill -9 -f "RimWorld" 2>/dev/null || true
    sleep 5
    ensure_game_running
}

log "========== FRONTIER: $SCENARIO_NAME (run $RUN_ID) =========="

# ─── Phase 0: Generate save file ───
log "Generating save for scenario: $SCENARIO_NAME..."
AGENT_REPO="$AGENT_REPO" python3 << PYEOF
import sys, json, os
sys.path.insert(0, '$FRONTIER_DIR')
from frontier.scenario import ScenarioConfig

config = ScenarioConfig.from_json(open('$SCENARIO_JSON').read())
output = config.generate_save()
print(f"Save generated: {output}")
PYEOF

# ─── Phase 1: Load save ───
ensure_game_running || exit 1

log "Loading save: $SAVE_NAME..."
LOAD_OK=0
for LOAD_ATTEMPT in 1 2 3; do
    if python3 << PYEOF
import sys, time; sys.path.insert(0, '$AGENT_REPO/sdk')
from rimworld import RimClient
r = RimClient()
r.load_game("$SAVE_NAME")
r.close()
time.sleep(12)
r = RimClient()
r.pause()
r.disable_incidents()
r.unforbid_all()
r.close()
PYEOF
    then
        LOAD_OK=1
        break
    else
        log "Load attempt $LOAD_ATTEMPT failed — restarting game..."
        kill_and_restart_game
    fi
done

if [[ $LOAD_OK -ne 1 ]]; then
    log "ERROR: Failed to load save after 3 attempts"
    echo '{"error": "failed_to_load", "scenario": "'$SCENARIO_NAME'"}' > "$RESULT_DIR/error.json"
    exit 1
fi

log "Save loaded, incidents disabled, items unforbidden"

# ─── Phase 2: Before snapshot ───
python3 << PYEOF - "$RESULT_DIR" "$MAP_SIZE"
import sys, json, time; sys.path.insert(0, '$AGENT_REPO/sdk')
from rimworld import RimClient
from snapshot import take_snapshot
time.sleep(3)
r = RimClient()

result_dir = sys.argv[1]
map_size = int(sys.argv[2])
cx = map_size // 2
cz = map_size // 2

# Create temp stockpile for resourceCounter
r.stockpile(cx - 15, cz - 15, cx + 15, cz + 15, priority="Normal")
r.unpause()
time.sleep(3)
r.pause()
r._cache._store.clear()

before = take_snapshot(r)

# Delete temp stockpile
for dx, dz in [(0,0), (1,1), (-1,-1), (3,3)]:
    try:
        r.delete_zone(cx + dx, cz + dz)
        break
    except Exception:
        continue

with open(f"{result_dir}/before.json", "w") as f:
    json.dump(before, f, indent=2, default=str)
r.close()
print("Before snapshot saved")
PYEOF

# Clear stale token log (in agent repo)
rm -f "$AGENT_REPO/surveys/token_log.jsonl"

START_TS=$(date +%s)

# ─── Phase 2b: Telemetry smoke test + start score monitor ───
log "Running telemetry smoke test..."
python3 << 'PYEOF'
import sys, os; sys.path.insert(0, os.path.join(os.environ.get("AGENT_REPO", ""), "sdk"))
from rimworld import RimClient
r = RimClient()
ok = True

# Test animals API
try:
    a = r.send("read_animals")
    count = len(a.get("animals", [])) if isinstance(a, dict) else -1
    print(f"  animals: {count} ({'OK' if count >= 0 else 'BROKEN'})")
    if count < 0: ok = False
except Exception as e:
    print(f"  animals: BROKEN ({e})")
    ok = False

# Test bills API
try:
    b = r.send("read_bills")
    wbs = b.get("workbenches", []) if isinstance(b, dict) else []
    print(f"  bills: {len(wbs)} workbenches ({'OK' if isinstance(b, dict) else 'BROKEN'})")
except Exception as e:
    print(f"  bills: BROKEN ({e})")
    ok = False

r.close()
if not ok:
    print("  WARNING: Telemetry broken — food pipeline diagnostics will be blind!")
PYEOF

log "Starting score monitor (20s intervals)..."
# P0 fix: truncate stale timeline data to prevent merging with previous captures
> "$RESULT_DIR/score_timeline.jsonl"
AGENT_REPO="$AGENT_REPO" python3 "$FRONTIER_DIR/agents/score_monitor.py" "$RESULT_DIR" 20 &
MONITOR_PID=$!

# ─── Phase 3: Load mission instructions if available ───
MISSION_PROMPT=""
# Check for scenario-specific mission file (SCENARIO_<NAME>.md)
SCENARIO_UPPER=$(echo "$SCENARIO_NAME" | tr '[:lower:]' '[:upper:]')
MISSION_FILE="$FRONTIER_DIR/SCENARIO_${SCENARIO_UPPER}.md"
if [[ -f "$MISSION_FILE" ]]; then
    MISSION_PROMPT="$(cat "$MISSION_FILE")"
    log "Mission loaded: $MISSION_FILE"
else
    # Try exact name match
    for f in "$FRONTIER_DIR"/SCENARIO_*.md; do
        fname=$(basename "$f" .md | sed 's/SCENARIO_//' | tr '[:upper:]' '[:lower:]')
        if [[ "$fname" == "$SCENARIO_NAME" ]]; then
            MISSION_PROMPT="$(cat "$f")"
            log "Mission loaded: $f"
            break
        fi
    done
fi

log "Spawning overseer (${OVERSEER_TIMEOUT}s limit, map=${MAP_SIZE}x${MAP_SIZE})..."

SYSTEM_PROMPT="# RimWorld Frontier Overseer — ${MAP_SIZE}x${MAP_SIZE} Map

You control a RimWorld colony via Python SDK on a SMALL ${MAP_SIZE}x${MAP_SIZE} map.
Game is loaded, paused, incidents disabled, items unforbidden.

## SDK Connection
\`\`\`python
import sys, time; sys.path.insert(0, '$AGENT_REPO/sdk')
from rimworld import RimClient
r = RimClient()
\`\`\`

## Key SDK Methods
- \`r.day1_setup()\` — full setup (roles, priorities, research, hunting, chopping). Returns dict with center_x, center_z, resources, hunter, cook, researcher.
- \`r.setup_cooking(cx, cz)\` — campfire + butcher + stove
- \`r.setup_dining(cx, cz)\` — table + chairs (BEFORE walls)
- \`r.setup_zones(cx, cz)\` — stockpiles + grow zone
- \`r.build_barracks(cx, cz, material='Steel')\` — 7x5 barracks with beds/furniture
- \`r.build_storage_room(cx, cz)\` — 7x5 storage room (WoodLog walls)
- \`r.setup_production(cx, cz, bx, bz)\` — research + tailoring benches
- \`r.setup_recreation(cx, cz)\` — horseshoes
- \`r.add_cooking_bills()\` — add/refresh cooking bills
- \`r.colony_health_check()\` — food/shelter/wood/mood/alerts status
- \`r.pause()\`, \`r.unpause()\` (auto speed 4 ultrafast + dismiss dialogs)
- \`r.save(name=)\`, \`r.chop(cx,cz,radius=)\`

## CRITICAL TIMING — Speed 4 Ultrafast
r.unpause() uses speed 4 (ultrafast, skips rendering). Game runs VERY FAST.
- Phase 1 sleep: **20s** (setup builds complete fast at speed 4)
- Phase 2 sleep: **40s** (barracks construction)
- Reactive loop sleep: **30-60s** per iteration (2-4 iterations)
- Total wall clock budget: **380s** (save 20s buffer for report)
- At speed 4 on ${MAP_SIZE}x${MAP_SIZE}, 3 in-game days pass in ~120-180s of real time

## Execution Plan (6-8 tool calls max)

**Tool 1: Setup + Cooking + Zones**
\`\`\`python
import time; START_TIME = time.time()
setup = r.day1_setup()
cx, cz = setup['center_x'], setup['center_z']
cooking = r.setup_cooking(cx, cz)
dining = r.setup_dining(cx, cz)
zones = r.setup_zones(cx, cz)
try: r.chop(cx, cz, radius=25)
except: pass
r.unpause(); time.sleep(20); r.pause()
bills = r.add_cooking_bills()
\`\`\`

**Tool 2: Build Structures**
\`\`\`python
barracks = r.build_barracks(cx, cz, material='Steel')
bx, bz = barracks['x1'], barracks['z1']
prod = r.setup_production(cx, cz, bx, bz)
storage = r.build_storage_room(cx, cz)
rec = r.setup_recreation(cx, cz)
r.unpause(); time.sleep(40); r.pause()
r.add_cooking_bills()
\`\`\`

**Tools 3-6: Reactive Loop** (repeat until game_day >= 4 or wall > 380s)
\`\`\`python
status = r.colony_health_check()
# Handle food/wood/medical crises per priority
r.unpause(); time.sleep(45); r.pause()
\`\`\`

**Tool 7-8: Save + Report**
\`\`\`python
r.save(name='$SAVE_NAME'); r.close()
\`\`\`

## Rules
- Wrap ALL build/zone calls in try/except — skip failures, never retry
- Do NOT spawn sub-agents or write files
- \`r.build(blueprint, x, z, stuff=)\` — use positional args, NOT y=
- HorseshoesPin (with 's'), TorchLamp (not StandingLamp)
- \`colonists()\` returns {'colonists': [...]}, not flat list

${MISSION_PROMPT:+## MISSION INSTRUCTIONS

$MISSION_PROMPT}"

unset CLAUDECODE
TMPFILE=$(mktemp)
OVERSEER_EXIT=0

echo '{"_agent":"overseer","type":"agent_start"}' >> "$LIVE_LOG"
env -u CLAUDECODE claude -p \
    --model "$OVERSEER_MODEL" \
    --max-turns 80 \
    --output-format stream-json \
    --verbose \
    --dangerously-skip-permissions \
    --allowedTools "Bash,Read,Write" \
    --system-prompt "$SYSTEM_PROMPT" \
    --no-session-persistence \
    "Run the colony on this ${MAP_SIZE}x${MAP_SIZE} map (scenario: $SCENARIO_NAME).

Follow the execution plan in the system prompt exactly. Use SDK helpers — they handle coordinates and error wrapping.

After saving, output a brief report ending with:
=== END REPORT ===

STRUCTURED_OBSERVATIONS:
  campfire_built_game_hour: [hour or never]
  first_meal_game_hour: [hour or never]
  packs_consumed: [N]
  construction_bottleneck: [what blocked or none]
  game_days_elapsed: [N]
  sdk_issues: [any SDK problems encountered]" \
    > >(tee -a "$LIVE_LOG" > "$TMPFILE") 2>> "$LIVE_LOG" &
OVERSEER_PID=$!

# Wait with timeout
ELAPSED=0
while kill -0 "$OVERSEER_PID" 2>/dev/null; do
    sleep 5
    ELAPSED=$((ELAPSED + 5))

    if [[ $ELAPSED -ge $OVERSEER_TIMEOUT ]]; then
        log "WARNING: Overseer hit ${OVERSEER_TIMEOUT}s timeout — killing"
        kill "$OVERSEER_PID" 2>/dev/null; sleep 2
        kill -9 "$OVERSEER_PID" 2>/dev/null || true
        pkill -f "claude -p" 2>/dev/null || true
        OVERSEER_EXIT=124
        python3 -c "
import sys; sys.path.insert(0, '$AGENT_REPO/sdk')
from rimworld import RimClient
r = RimClient(); r.pause(); r.save(name='$SAVE_NAME'); r.close()
" 2>/dev/null || true
        break
    fi
done

if [[ $OVERSEER_EXIT -ne 124 ]]; then
    wait "$OVERSEER_PID" || OVERSEER_EXIT=$?
fi

END_TS=$(date +%s)
DURATION=$((END_TS - START_TS))

log "Overseer finished in ${DURATION}s (exit=$OVERSEER_EXIT)"

# ─── Phase 3b: Stop score monitor ───
log "Stopping score monitor..."
kill "$MONITOR_PID" 2>/dev/null || true
wait "$MONITOR_PID" 2>/dev/null || true

# Parse overseer output
python3 << PYEOF - "$TMPFILE" "$RESULT_DIR" "$OVERSEER_EXIT" "$DURATION"
import json, sys
tmpfile = sys.argv[1]
result_dir = sys.argv[2]
exit_code = int(sys.argv[3])
wall_duration_s = int(sys.argv[4])

text_parts = []
result_data = {}
num_turns = 0

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
            num_turns += 1
            msg = event.get("message", event)
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block["text"])
        elif etype == "result":
            result_data = event
            if event.get("result"):
                text_parts.append(event["result"])

full_text = "\n".join(text_parts)
with open(f"{result_dir}/overseer_conversation.txt", "w") as f:
    f.write(full_text if full_text.strip() else f"[Exit code {exit_code}, no output]\n")

usage = result_data.get("usage", {})
input_tok = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
output_tok = usage.get("output_tokens", 0)

if input_tok == 0 and exit_code == 124:
    input_tok = int(wall_duration_s / 60 * 1500)
    output_tok = int(input_tok * 0.3)

overseer_info = {
    "input_tokens": input_tok,
    "output_tokens": output_tok,
    "total_cost_usd": result_data.get("total_cost_usd", 0),
    "duration_ms": result_data.get("duration_ms", 0) or wall_duration_s * 1000,
    "num_turns": result_data.get("num_turns", num_turns),
    "exit_code": exit_code,
}
with open(f"{result_dir}/overseer_usage.json", "w") as f:
    json.dump(overseer_info, f, indent=2)

print(f"Overseer: {input_tok + output_tok} tokens, \${result_data.get('total_cost_usd', 0):.4f}, {num_turns} turns")
PYEOF

cp "$TMPFILE" "$RESULT_DIR/overseer_raw.jsonl" 2>/dev/null || true
rm -f "$TMPFILE" "${TMPFILE}.err"

# ─── Phase 3a: Extract structured observations ───
python3 << 'PYEOF' - "$RESULT_DIR"
import sys, json, re
result_dir = sys.argv[1]
try:
    with open(f"{result_dir}/overseer_conversation.txt") as f:
        text = f.read()
    match = re.search(r'STRUCTURED_OBSERVATIONS:\s*\n(.*?)(?:\n\S|\Z)', text, re.DOTALL)
    if match:
        obs_text = match.group(1).strip()
        obs = {"raw": obs_text}
        for line in obs_text.split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('-'):
                key, _, val = line.partition(':')
                obs[key.strip()] = val.strip()
        with open(f"{result_dir}/machine_report.json", "w") as f:
            json.dump(obs, f, indent=2)
        print(f"Machine report saved ({len(obs)} fields)")
    else:
        print("No STRUCTURED_OBSERVATIONS found")
except Exception as e:
    print(f"Machine report extraction failed: {e}")
PYEOF

# ─── Phase 4: After snapshot + scoring ───
log "Taking after snapshot and scoring..."

python3 << PYEOF - "$RESULT_DIR" "$DURATION" "$SCENARIO_JSON"
import sys, json, os; sys.path.insert(0, '$AGENT_REPO/sdk'); sys.path.insert(0, '$FRONTIER_DIR')
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

with open(f"{result_dir}/overseer_usage.json") as f:
    ou = json.load(f)
overseer_tokens = ou.get("input_tokens", 0) + ou.get("output_tokens", 0)
overseer_cost = ou.get("total_cost_usd", 0)

# Load timeline data if available
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

# Use scenario-adaptive scoring (with timeline if available)
score_data = score_scenario(config, before, after, duration_s, overseer_tokens, overseer_cost, timeline=timeline)

with open(f"{result_dir}/score.json", "w") as f:
    json.dump(score_data, f, indent=2)

print(f"SCORE: {score_data['total']}/{score_data['max']} ({score_data['pct']:.0f}%) "
      f"[base: {score_data['base_total']}/{score_data['base_max']} ({score_data['base_pct']:.0f}%)]")
print(f"Scenario: {config.name} | Difficulty: {config.overall_difficulty():.2f} | Duration: {duration_s}s")

if score_data.get("adjustments"):
    print(f"Weight adjustments: {score_data['adjustments']}")

# Diff summary
diff = compare_snapshots(before, after)
with open(f"{result_dir}/diff.txt", "w") as f:
    f.write(diff)

r.close()
PYEOF

# ─── Phase 4b: Timeline analysis ───
log "Analyzing run timeline..."
python3 << PYEOF - "$RESULT_DIR"
import sys, json, os

result_dir = sys.argv[1]
timeline_path = os.path.join(result_dir, "score_timeline.jsonl")

if not os.path.isfile(timeline_path):
    print("  No timeline data (monitor may not have started)")
else:
    entries = []
    with open(timeline_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not entries:
        print("  Timeline empty")
    else:
        print(f"  Timeline: {len(entries)} snapshots over {entries[-1]['elapsed_s']}s")

        # ── Progression table ──
        print()
        print(f"  {'Time':>6s}  {'Day':>5s}  {'Score':>6s}  {'Meals':>5s}  {'Packs':>5s}  {'Wood':>6s}  {'Bldgs':>5s}  {'BPs':>4s}  {'Rooms'}")
        print(f"  {'─'*6}  {'─'*5}  {'─'*6}  {'─'*5}  {'─'*5}  {'─'*6}  {'─'*5}  {'─'*4}  {'─'*20}")
        for e in entries:
            day_str = f"{e['day']}.{int(e.get('hour',0)):02d}"
            rooms_str = ", ".join(
                f"{r['role']}({r['impressiveness']})"
                for r in e.get("rooms", [])
            ) if isinstance(e.get("rooms"), list) else str(e.get("rooms", 0))
            bp = e.get("blueprints_pending", "?")
            print(f"  {e['elapsed_s']:>5d}s  {day_str:>5s}  {e['pct']:>5.1f}%  {e['meals']:>5d}  {e['packs']:>5d}  {e['wood']:>6d}  {e['buildings']:>5d}  {bp:>4}  {rooms_str}")

        # ── Need buckets over time ──
        print()
        has_needs = any(e.get("need_buckets") for e in entries)
        if has_needs:
            print(f"  {'Time':>6s}  {'Day':>5s}  {'Survival':>8s}  {'Happiness':>9s}  {'Environ':>8s}  Per-colonist details")
            print(f"  {'─'*6}  {'─'*5}  {'─'*8}  {'─'*9}  {'─'*8}  {'─'*40}")
            for e in entries:
                nb = e.get("need_buckets", {})
                day_str = f"{e['day']}.{int(e.get('hour',0)):02d}"
                s = nb.get("survival", -1)
                h = nb.get("happiness", -1)
                ev = nb.get("environment", -1)
                s_str = f"{s:.2f}" if s >= 0 else "  n/a"
                h_str = f"{h:.2f}" if h >= 0 else "  n/a"
                ev_str = f"{ev:.2f}" if ev >= 0 else "  n/a"
                # Per-colonist compact: name(S/H/E)
                cn = e.get("colonist_needs", {})
                per_col = []
                for name, nd in cn.items():
                    cs = nd.get("survival", -1)
                    ch = nd.get("happiness", -1)
                    ce = nd.get("environment", -1)
                    per_col.append(f"{name}({cs:.1f}/{ch:.1f}/{ce:.1f})")
                print(f"  {e['elapsed_s']:>5d}s  {day_str:>5s}  {s_str:>8s}  {h_str:>9s}  {ev_str:>8s}  {' '.join(per_col)}")

        # ── Job distribution ──
        print()
        job_counts = {}  # {colonist: {job: count}}
        total_snapshots = len(entries)
        for e in entries:
            for col, job in e.get("jobs", {}).items():
                if col not in job_counts:
                    job_counts[col] = {}
                job_counts[col][job] = job_counts[col].get(job, 0) + 1
        if job_counts:
            print("  ── JOB DISTRIBUTION (% of snapshots) ──")
            for col in sorted(job_counts.keys()):
                jobs = job_counts[col]
                sorted_jobs = sorted(jobs.items(), key=lambda x: -x[1])
                parts = [f"{job} {count*100//total_snapshots}%" for job, count in sorted_jobs if count*100//total_snapshots >= 5]
                print(f"  {col:>12s}: {', '.join(parts)}")

        # ── Detect issues ──
        print()
        issues = []

        # Meals never increased?
        max_meals = max(e.get("meals", 0) for e in entries)
        if max_meals == 0:
            issues.append("COOKING BROKEN: meals never rose above 0 — bills not firing or no fuel")

        # Packs decreasing fast?
        if len(entries) >= 2:
            first_packs = entries[0].get("packs", 0)
            last_packs = entries[-1].get("packs", 0)
            if first_packs > 0 and last_packs < first_packs * 0.5:
                issues.append(f"PACK BURN: survival packs {first_packs} -> {last_packs} (>{50}% consumed)")

        # Game days not advancing?
        if len(entries) >= 3:
            first_day = entries[0].get("day", 0) + entries[0].get("hour", 0) / 24
            last_day = entries[-1].get("day", 0) + entries[-1].get("hour", 0) / 24
            elapsed = entries[-1]["elapsed_s"] - entries[0]["elapsed_s"]
            if elapsed > 120 and (last_day - first_day) < 0.5:
                issues.append(f"GAME STALLED: only {last_day - first_day:.1f} days in {elapsed}s — speed 4 not working or game paused")

        # Blueprints stuck?
        bp_entries = [e for e in entries if e.get("blueprints_pending", 0) > 0]
        if len(bp_entries) >= 3:
            stuck_bps = [e for e in bp_entries[-3:] if e.get("blueprints_pending", 0) > 10]
            if len(stuck_bps) == 3:
                issues.append(f"CONSTRUCTION STALLED: {stuck_bps[-1]['blueprints_pending']} blueprints stuck for 3+ snapshots")

        # Score plateaued?
        if len(entries) >= 4:
            last_scores = [e["pct"] for e in entries[-4:]]
            if max(last_scores) - min(last_scores) < 1.0:
                issues.append(f"SCORE PLATEAU: stuck at {last_scores[-1]:.1f}% for last {len(last_scores)} snapshots")

        # Rooms with negative impressiveness?
        for e in entries:
            for rm in e.get("rooms", []):
                if isinstance(rm, dict) and rm.get("impressiveness", 0) < 0:
                    issues.append(f"BAD ROOM: {rm['role']} at impressiveness {rm['impressiveness']} @ {e['elapsed_s']}s")
                    break
            if issues and "BAD ROOM" in issues[-1]:
                break

        # Need checks — sensitive thresholds to catch problems early
        all_colonists = set().union(*(e.get("colonist_needs", {}).keys() for e in entries))
        for col_name in all_colonists:
            col_entries = [(e["elapsed_s"], e.get("colonist_needs", {}).get(col_name, {})) for e in entries
                           if col_name in e.get("colonist_needs", {})]
            if not col_entries:
                continue
            for bucket, warn_thresh, crit_thresh, label in [
                ("survival",    0.40, 0.20, "SURVIVAL"),
                ("happiness",   0.35, 0.20, "HAPPINESS"),
                ("environment", 0.30, 0.15, "ENVIRONMENT"),
                ("food",        0.35, 0.15, "FOOD"),
                ("rest",        0.30, 0.15, "REST"),
                ("joy",         0.30, 0.10, "JOY"),
            ]:
                vals = [(t, nd.get(bucket, -1)) for t, nd in col_entries if nd.get(bucket, -1) >= 0]
                if not vals:
                    continue
                crit_snaps = [(t, v) for t, v in vals if v < crit_thresh]
                warn_snaps = [(t, v) for t, v in vals if v < warn_thresh]
                if crit_snaps:
                    worst_t, worst_v = min(crit_snaps, key=lambda x: x[1])
                    issues.append(f"NEED CRITICAL — {col_name} {label}={worst_v:.2f} @ {worst_t}s ({len(crit_snaps)}/{len(vals)} snapshots below {crit_thresh})")
                elif len(warn_snaps) >= 2:
                    worst_t, worst_v = min(warn_snaps, key=lambda x: x[1])
                    issues.append(f"NEED WARNING — {col_name} {label}={worst_v:.2f} @ {worst_t}s ({len(warn_snaps)}/{len(vals)} snapshots below {warn_thresh})")
            # Declining trend: if any need dropped >0.3 from first to last snapshot
            for need_key in ["food", "rest", "mood", "joy"]:
                first_val = col_entries[0][1].get(need_key, -1)
                last_val = col_entries[-1][1].get(need_key, -1)
                if first_val >= 0 and last_val >= 0 and (first_val - last_val) > 0.30:
                    issues.append(f"NEED DECLINING — {col_name} {need_key} dropped {first_val:.2f} -> {last_val:.2f}")

        # Idle colonists — any colonist idle for >40% of snapshots?
        for col, jobs in job_counts.items():
            idle_pct = jobs.get("idle", 0) * 100 // total_snapshots if total_snapshots else 0
            wait_pct = jobs.get("Wait_Combat", 0) * 100 // total_snapshots if total_snapshots else 0
            if idle_pct + wait_pct >= 40:
                issues.append(f"IDLE COLONIST: {col} idle/waiting {idle_pct + wait_pct}% of snapshots")

        # ── FOOD PIPELINE DIAGNOSTICS ──
        # These cross-reference multiple signals to surface root causes, not just symptoms.

        # 1. "Meals produced but disappearing" — cooking works but meals don't accumulate
        meal_history = [e.get("meals", 0) for e in entries]
        peak_meals = max(meal_history)
        final_meals = meal_history[-1] if meal_history else 0
        cooking_observed = any("DoBill" in str(e.get("jobs", {}).values()) for e in entries)
        if peak_meals > 0 and final_meals == 0:
            # Meals were produced but ended at 0 — something is consuming them
            wild_animals = [e.get("wild_animals", e.get("food_pipeline", {}).get("wild_animals", -1)) for e in entries]
            avg_wild = sum(w for w in wild_animals if w > 0) / max(1, sum(1 for w in wild_animals if w > 0))
            if avg_wild > 5:
                issues.append(f"FOOD THEFT: meals peaked at {peak_meals} but ended at 0 with ~{avg_wild:.0f} wild animals on map — animals likely eating from open stockpile. Fix: store food indoors or hunt animals first")
            else:
                issues.append(f"FOOD CONSUMED: meals peaked at {peak_meals} but ended at 0 — production rate too low for consumption")

        # 2. "Wild animals competing for food" — high animal count with open food
        has_food_pipeline = any(e.get("food_pipeline") for e in entries)
        if has_food_pipeline:
            for e in entries[-3:]:  # check recent snapshots
                fp = e.get("food_pipeline", {})
                wild = fp.get("wild_animals", 0)
                food_in_stockpile = fp.get("food_in_stockpile", 0)
                # Check if food is in an enclosed room
                food_rooms = [r for r in e.get("rooms", [])
                              if isinstance(r, dict) and r.get("role", "").lower() in ("room", "storage", "stockpile")]
                food_indoors = len(food_rooms) > 0
                if wild > 8 and food_in_stockpile > 0 and not food_indoors:
                    issues.append(f"FOOD EXPOSED: {wild} wild animals on map, {food_in_stockpile} food items in open stockpile — animals will eat it. Fix: build enclosed storage room")
                    break

        # 3. "Raw food available but 0 meals" — bill config or cook priority issue
        if has_food_pipeline:
            recent = entries[-3:] if len(entries) >= 3 else entries
            for e in recent:
                fp = e.get("food_pipeline", {})
                if fp.get("raw_food", 0) > 5 and fp.get("meals", 0) == 0 and fp.get("has_cooking_station", False):
                    if not fp.get("has_bills", False):
                        issues.append(f"BILLS MISSING: {fp['raw_food']} raw food available + cooking station exists but no bills active @ {e['elapsed_s']}s")
                    else:
                        issues.append(f"COOK IDLE: {fp['raw_food']} raw food + bills active but 0 meals @ {e['elapsed_s']}s — cook priority too low or pathing issue")
                    break

        # 4. "No cooking station despite having raw food" — build order issue
        if has_food_pipeline:
            late_entries = entries[len(entries)//2:]  # second half of run
            for e in late_entries:
                fp = e.get("food_pipeline", {})
                if fp.get("raw_food", 0) > 3 and not fp.get("has_cooking_station", False):
                    issues.append(f"NO KITCHEN: {fp['raw_food']} raw food available but no cooking station built by {e['elapsed_s']}s — build campfire/stove earlier")
                    break

        # 5. Wild animal count trend — are they increasing (breeding) or decreasing (hunted)?
        wild_counts = [e.get("wild_animals", e.get("food_pipeline", {}).get("wild_animals", -1)) for e in entries]
        valid_wild = [(i, w) for i, w in enumerate(wild_counts) if w >= 0]
        if len(valid_wild) >= 3:
            first_wild = valid_wild[0][1]
            last_wild = valid_wild[-1][1]
            if first_wild > 10 and last_wild > first_wild * 0.8:
                issues.append(f"WILDLIFE NOT HUNTED: {first_wild} → {last_wild} wild animals — hunting should reduce food competition and produce meat")

        if issues:
            print("  ── TIMELINE ISSUES ──")
            for issue in issues:
                print(f"    {issue}")
        else:
            print("  No timeline issues detected")

        # Score timeline metrics
        sys.path.insert(0, '$AGENT_REPO/sdk')
        from timeline_scoring import score_timeline as _tl_score
        tl_scores, tl_weights = _tl_score(entries)
        if tl_scores:
            print()
            print("  ── TIMELINE SCORES ──")
            for metric in sorted(tl_scores):
                s = tl_scores[metric]
                w = tl_weights[metric]
                print(f"    {metric}: {s:.2f} (weight {w}, weighted {s*w:.1f})")

        # ── TELEMETRY HEALTH CHECK ──
        # If a field was broken for ALL snapshots, it's an instrumentation bug, not a game issue
        telemetry_broken = []
        wild_vals = [e.get("wild_animals", e.get("food_pipeline", {}).get("wild_animals", -1)) for e in entries]
        if all(w == -1 for w in wild_vals):
            telemetry_broken.append("wild_animals=-1 for ALL snapshots (r.send('read_animals') failing)")
        bill_vals = [e.get("food_pipeline", {}).get("has_bills", None) for e in entries]
        cooking_vals = [e.get("food_pipeline", {}).get("has_cooking_station", False) for e in entries]
        if any(cooking_vals) and not any(bill_vals):
            telemetry_broken.append("bills=False for ALL snapshots despite cooking station present (r.send('read_bills') failing)")
        if telemetry_broken:
            print()
            print("  ── TELEMETRY BROKEN (instrumentation bug, not game issue) ──")
            error_log = os.path.join(result_dir, 'telemetry_errors.log')
            with open(error_log, 'a') as ef:
                ef.write(f"[post-run] {len(entries)} snapshots analyzed\n")
                for tb in telemetry_broken:
                    print(f"    BUG: {tb}")
                    ef.write(f"[post-run] {tb}\n")
            print("    FIX THESE BEFORE DIAGNOSING GAME ISSUES — data is unreliable")
            print(f"    Error log: {error_log}")

        # Save analysis
        analysis = {
            "snapshots": len(entries),
            "duration_s": entries[-1]["elapsed_s"],
            "max_meals": max_meals,
            "final_score_pct": entries[-1]["pct"],
            "game_days": entries[-1].get("day", 0) + entries[-1].get("hour", 0) / 24,
            "issues": issues,
            "job_distribution": {col: {j: round(c / total_snapshots, 2) for j, c in jobs.items()}
                                 for col, jobs in job_counts.items()},
            "need_trajectory": [e.get("need_buckets", {}) for e in entries],
            "timeline_scores": tl_scores,
            "timeline_weights": tl_weights,
        }
        with open(os.path.join(result_dir, "timeline_analysis.json"), "w") as f:
            json.dump(analysis, f, indent=2)
PYEOF

# ─── Phase 4c: Generate timeline charts ───
log "Generating timeline charts..."
python3 "$FRONTIER_DIR/frontier/timeline_charts.py" "$RESULT_DIR" 2>/dev/null || log "Charts skipped (matplotlib not available)"

# ─── Phase 5: Update frontier tracker ───
log "Updating frontier tracker..."

python3 << PYEOF - "$RESULT_DIR" "$RUN_ID" "$SCENARIO_JSON"
import sys, json; sys.path.insert(0, '$FRONTIER_DIR')
from frontier.tracker import FrontierTracker, RunResult
from frontier.analyzer import analyze_run, summarize_failures
from frontier.scenario import ScenarioConfig
from frontier.visualize import frontier_heatmap, frontier_summary

result_dir = sys.argv[1]
run_id = int(sys.argv[2])
scenario_json = sys.argv[3]

config = ScenarioConfig.from_json(open(scenario_json).read())

with open(f"{result_dir}/score.json") as f:
    score_data = json.load(f)

# Build RunResult
result = RunResult(
    scenario_name=config.name,
    run_id=run_id,
    score_pct=score_data.get("base_pct", 0),
    base_score_pct=score_data.get("base_pct", 0),
    adjusted_score_pct=score_data.get("pct", 0),
    duration_s=score_data.get("efficiency", {}).get("duration_s", 0),
    cost_usd=score_data.get("efficiency", {}).get("total_cost_usd", 0),
)

# Check for colonist deaths
breakdown = score_data.get("breakdown", {})
if breakdown.get("alive", {}).get("score", 1.0) < 1.0:
    result.alive = False

# Top losses
top_losses = []
for metric, info in breakdown.items():
    if metric.startswith("_") or not isinstance(info, dict):
        continue
    lost = info.get("adjusted_weight", info.get("weight", 0)) * (1.0 - min(info.get("score", 0), 1.0))
    if lost >= 1.0:
        top_losses.append({"metric": metric, "lost": round(lost, 1), "score": info.get("score", 0)})
top_losses.sort(key=lambda x: -x["lost"])
result.top_losses = top_losses[:7]

# Failure analysis
failures = analyze_run(config, score_data)
result.failure_categories = list(set(f.category for f in failures))

# Record in tracker
tracker = FrontierTracker()
tracker.record_run(result)

# Save scenario config for future reference
config.save(tracker.state_path.parent / "scenarios" / f"{config.name}.json")

# Print summary
print()
print(frontier_heatmap(tracker))
print()
print(frontier_summary(tracker))

if failures:
    print()
    print(summarize_failures(failures))
PYEOF

# ─── Phase 6: Colony map ───
log "Capturing colony map..."
python3 << PYEOF - "$RESULT_DIR" "$MAP_SIZE"
import sys, json; sys.path.insert(0, '$AGENT_REPO/sdk')
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

# Fallback to composite if detailed not available
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
        entities = detailed.get("entities", [])

        # Print column numbers
        width = max(len(row) for row in grid) if grid else 0
        if width > 0:
            tens = "".join([str((x1 + i) // 10 % 10) if (x1 + i) % 10 == 0 else " " for i in range(width)])
            ones = "".join([str((x1 + i) % 10) for i in range(width)])
            f.write(f"     {tens}\n")
            f.write(f"     {ones}\n")

        for i, row in enumerate(grid):
            z = z1 + i
            f.write(f"{z:3d}  {row}\n")

        # Legend
        f.write(f"\n── LEGEND ──\n")
        for ch, desc in sorted(legend.items()):
            f.write(f"  {ch:3s} = {desc}\n")

    else:
        f.write(json.dumps(detailed, indent=2) if isinstance(detailed, dict) else str(detailed))

r.close()
print(f"Colony map saved (center={cx},{cz})")
PYEOF

log "========== FRONTIER: $SCENARIO_NAME (run $RUN_ID) COMPLETE =========="
log "Results: $RESULT_DIR/"

# Generate searchable run summary for QMD
python3 "$FRONTIER_DIR/frontier/summarize_run.py" "$RESULT_DIR" 2>/dev/null || true

# Update QMD index (if collection exists)
if command -v qmd &>/dev/null; then
    qmd update 2>/dev/null || true
fi

# Log to pipeline
RUN_SCORE=$(python3 -c "import json; d=json.load(open('$RESULT_DIR/score.json')); print(f'{d[\"pct\"]:.1f}%')" 2>/dev/null || echo "?")
log_event "runner" "$SCENARIO_NAME" "run_$RUN_ID: $RUN_SCORE ($DURATION s)"

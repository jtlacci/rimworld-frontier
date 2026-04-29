#!/bin/bash
# Playtest scenario runner — runs one scenario end-to-end.
# Usage: ./frontier/runner.sh <scenario_config.json> [run_id]
#
# Phases: savegen → load → before_snapshot → smoke_test → overseer → score →
#         charts → criteria → colony_map → reporter
#
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

# MODEL_OVERSEER set in config.sh (qwen-plus)
OVERSEER_TIMEOUT=1350  # 22.5 min hard limit for frontier runs
GAME_DAY_LIMIT=5       # auto-pause at day 5 (game starts day 1 h7, so day 5 = ~3.7 full days)

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

phase_mark() {
    echo "{\"phase\":\"$1\",\"event\":\"$2\",\"ts\":$(date +%s)}" >> "$RESULT_DIR/phases.jsonl"
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

log "========== PLAYTEST: $SCENARIO_NAME (run $RUN_ID) =========="

# ─── Phase 0: Generate save file ───
log "Generating save for scenario: $SCENARIO_NAME..."
phase_mark "savegen" "start"
AGENT_REPO="$AGENT_REPO" python3 << PYEOF
import sys, json, os
sys.path.insert(0, '$FRONTIER_DIR')
from frontier.scenario import ScenarioConfig

config = ScenarioConfig.from_json(open('$SCENARIO_JSON').read())
output = config.generate_save()
print(f"Save generated: {output}")
PYEOF
phase_mark "savegen" "end"

# ─── Phase 1: Load save ───
phase_mark "load_save" "start"
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
r.set_event_log("$RESULT_DIR/events.jsonl")
r.send("set_day_limit", day=$GAME_DAY_LIMIT)
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

# Spawn scenario wildlife via SDK (not baked into save — GenSpawn blocker would kill them)
python3 << PYEOF
import sys, json; sys.path.insert(0, '$AGENT_REPO/sdk')
from rimworld import RimClient
config = json.load(open('$SCENARIO_JSON'))
dist = config.get('wildlife_distribution') or {}
if not dist and config.get('wildlife_count', 0) > 0:
    species = config.get('wildlife_species', [])
    count = config.get('wildlife_count', 0)
    if species:
        per = max(1, count // len(species))
        dist = {s: per for s in species}
if dist:
    r = RimClient()
    for species, count in dist.items():
        try:
            result = r.spawn_animals(species, count)
            print(f"  Spawned {count}x {species}")
        except Exception as e:
            print(f"  WARN: Failed to spawn {species}: {e}")
    r.close()
else:
    print("  No wildlife to spawn")
PYEOF

phase_mark "load_save" "end"

# ─── Phase 2: Before snapshot ───
phase_mark "before_snapshot" "start"
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
phase_mark "before_snapshot" "end"

# Clear stale token log (in agent repo)
rm -f "$AGENT_REPO/surveys/token_log.jsonl"

START_TS=$(date +%s)

# ─── Phase 2b: Telemetry smoke test + start score monitor ───
phase_mark "smoke_test" "start"
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
AGENT_REPO="$AGENT_REPO" python3 "$FRONTIER_DIR/agents/score_monitor.py" "$RESULT_DIR" 5 &
MONITOR_PID=$!
phase_mark "smoke_test" "end"

# ─── Phase 3: Load mission instructions if available ───
MISSION_PROMPT=""
# Use the "mission" field from scenario.json (e.g., "feed_the_colony") for file lookup
# This handles versioned names like feed_the_colony_0.7 → SCENARIO_FEED_THE_COLONY.md
MISSION_BASE=$(python3 -c "import json; print(json.load(open('$SCENARIO_JSON')).get('mission','') or '')" 2>/dev/null)
MISSION_DESC=$(python3 -c "import json; print(json.load(open('$SCENARIO_JSON')).get('mission_description','') or '')" 2>/dev/null)
if [[ -n "$MISSION_BASE" ]]; then
    MISSION_UPPER=$(echo "$MISSION_BASE" | tr '[:lower:]' '[:upper:]')
    MISSION_FILE="$FRONTIER_DIR/SCENARIO_${MISSION_UPPER}.md"
    if [[ -f "$MISSION_FILE" ]]; then
        MISSION_PROMPT="$(cat "$MISSION_FILE")"
        log "Mission loaded: $MISSION_FILE"
    fi
fi
# Inject mission_description from scenario.json (contains scenario-specific instructions)
if [[ -n "$MISSION_DESC" ]]; then
    MISSION_PROMPT="${MISSION_PROMPT:+$MISSION_PROMPT

}## Scenario-Specific Instructions
$MISSION_DESC"
    log "Mission description injected from scenario.json"
fi

phase_mark "overseer" "start"
log "Spawning overseer (${OVERSEER_TIMEOUT}s limit, map=${MAP_SIZE}x${MAP_SIZE})..."

OVERSEER_PROMPT="$(cat "$AGENT_REPO/AGENT_OVERSEER.md")"

SYSTEM_PROMPT="$OVERSEER_PROMPT

---

## Session Context

Map: ${MAP_SIZE}x${MAP_SIZE}. Game is loaded, paused, incidents disabled, items unforbidden.
Save name: $SAVE_NAME
SDK_PATH: $AGENT_REPO/sdk

${MISSION_PROMPT:+## MISSION INSTRUCTIONS

$MISSION_PROMPT}"

export RIM_SDK_LOG="$RESULT_DIR/command_log.jsonl"
export SDK_PATH="$AGENT_REPO/sdk"

unset CLAUDECODE
TMPFILE=$(mktemp)
OVERSEER_EXIT=0

OVERSEER_MESSAGE="Run the colony on this ${MAP_SIZE}x${MAP_SIZE} map (scenario: $SCENARIO_NAME).

Follow the strategy in your system prompt. Use skills and the reader script.

After the game reaches day 3-4, save with save_game.py and output a brief report."

echo '{"_agent":"overseer","type":"agent_start"}' >> "$LIVE_LOG"
python3 "$AGENT_HARNESS" \
    --model "$MODEL_OVERSEER" \
    --system "$SYSTEM_PROMPT" \
    --message "$OVERSEER_MESSAGE" \
    --tools "Bash,Read,Write" \
    --max-turns 200 \
    > >(tee -a "$LIVE_LOG" > "$TMPFILE") 2>> "$LIVE_LOG" &
OVERSEER_PID=$!

# Wait with timeout + game day limit
ELAPSED=0
# GAME_DAY_LIMIT defined at top of script
while kill -0 "$OVERSEER_PID" 2>/dev/null; do
    sleep 5
    ELAPSED=$((ELAPSED + 5))

    # Check game day every 30s
    if [[ $((ELAPSED % 30)) -eq 0 ]]; then
        GAME_DAY=$(python3 -c "
import sys; sys.path.insert(0, '$AGENT_REPO/sdk')
from rimworld import RimClient
try:
    r = RimClient()
    w = r.weather()
    print(w.get('dayOfYear', 0))
    r.close()
except: print(0)
" 2>/dev/null || echo 0)
        if [[ "$GAME_DAY" -ge "$GAME_DAY_LIMIT" ]]; then
            log "Game day $GAME_DAY >= limit $GAME_DAY_LIMIT — stopping overseer"
            kill "$OVERSEER_PID" 2>/dev/null; sleep 2
            kill -9 "$OVERSEER_PID" 2>/dev/null || true
            pkill -f "agent_harness" 2>/dev/null || true
            OVERSEER_EXIT=124
            python3 -c "
import sys; sys.path.insert(0, '$AGENT_REPO/sdk')
from rimworld import RimClient
r = RimClient(); r.pause(); r.save(name='$SAVE_NAME'); r.close()
" 2>/dev/null || true
            break
        fi
    fi

    if [[ $ELAPSED -ge $OVERSEER_TIMEOUT ]]; then
        log "WARNING: Overseer hit ${OVERSEER_TIMEOUT}s timeout — killing"
        kill "$OVERSEER_PID" 2>/dev/null; sleep 2
        kill -9 "$OVERSEER_PID" 2>/dev/null || true
        pkill -f "agent_harness" 2>/dev/null || true
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

# Copy sub-agent logs to result directory
if [[ -d /tmp/overseer_subagents ]]; then
    mkdir -p "$RESULT_DIR/subagents"
    for f in /tmp/overseer_subagents/*.jsonl; do
        [ -f "$f" ] || continue
        base=$(basename "$f" .jsonl)
        python3 -c "
import json, sys
parts = []
for line in open(sys.argv[1]):
    try:
        e = json.loads(line.strip())
        if e.get('type') == 'result' and e.get('result'): parts.append(e['result'])
        elif e.get('type') == 'assistant':
            for b in e.get('message',{}).get('content',[]):
                if isinstance(b,dict) and b.get('type')=='text': parts.append(b['text'])
        elif e.get('type') == 'tool_result':
            c = e.get('content','')
            if isinstance(c, str) and len(c) < 2000: parts.append(f'[tool_result] {c}')
    except: pass
print('\n'.join(parts))
" "$f" > "$RESULT_DIR/subagents/${base}.md" 2>/dev/null || true
    done
    rm -rf /tmp/overseer_subagents
    log "Sub-agent logs saved to $RESULT_DIR/subagents/"
fi

END_TS=$(date +%s)
DURATION=$((END_TS - START_TS))

log "Overseer finished in ${DURATION}s (exit=$OVERSEER_EXIT)"
phase_mark "overseer" "end"

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
tool_calls = []
result_data = {}
num_turns = 0
pending_tools = {}  # id -> {tool, input, start_ts}

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
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block["text"])
                    elif block.get("type") == "tool_use":
                        tool_id = block.get("id", "")
                        inp = block.get("input", {})
                        tool_name = block.get("name", "?")
                        pending_tools[tool_id] = {
                            "turn": num_turns,
                            "tool": tool_name,
                            "input": inp,
                        }
                        # Include tool call in conversation text
                        code = ""
                        if isinstance(inp, dict):
                            code = inp.get("command", inp.get("code", str(inp)[:1000]))
                        elif isinstance(inp, str):
                            code = inp[:1000]
                        text_parts.append(f"\n[TOOL: {tool_name}]\n{code}\n")
        elif etype == "tool_result":
            tool_id = event.get("tool_use_id", "")
            # Include tool result in conversation text
            result_content = event.get("content", "")
            if isinstance(result_content, str) and len(result_content) < 3000:
                text_parts.append(f"[RESULT]\n{result_content}\n")
            elif isinstance(result_content, list):
                for item in result_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(f"[RESULT]\n{item['text'][:3000]}\n")
            if tool_id in pending_tools:
                tc = pending_tools.pop(tool_id)
                code = ""
                inp = tc["input"]
                if isinstance(inp, dict):
                    code = inp.get("command", inp.get("code", str(inp)[:500]))
                elif isinstance(inp, str):
                    code = inp[:500]
                tool_calls.append({
                    "turn": tc["turn"],
                    "tool": tc["tool"],
                    "code": code,
                })
        elif etype == "result":
            result_data = event
            if event.get("result"):
                text_parts.append(event["result"])

# Write tool calls log
if tool_calls:
    with open(f"{result_dir}/tool_calls.jsonl", "w") as f:
        for tc in tool_calls:
            f.write(json.dumps(tc) + "\n")
    print(f"Tool calls: {len(tool_calls)} logged")

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

# overseer_raw.jsonl removed — conversation.txt now includes tool calls
rm -f "$TMPFILE" "${TMPFILE}.err"

# machine_report.json removed — unreliable overseer self-reports; events/timeline have ground truth

# ─── Phase 4: After snapshot + scoring ───
phase_mark "scoring" "start"
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

# diff.txt removed — derivable from before.json + after.json

r.close()
PYEOF
phase_mark "scoring" "end"

# ─── Phase 4b: Timeline analysis ───
phase_mark "timeline_analysis" "start"
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
phase_mark "timeline_analysis" "end"

# ─── Phase 4c: Generate timeline charts ───
phase_mark "charts" "start"
log "Generating timeline charts..."
python3 "$FRONTIER_DIR/frontier/timeline_charts.py" "$RESULT_DIR" 2>/dev/null || log "Charts skipped (matplotlib not available)"
phase_mark "charts" "end"

# ─── Phase 5: Evaluate pass criteria ───
phase_mark "criteria" "start"
log "Evaluating pass_criteria..."

python3 << PYEOF - "$RESULT_DIR" "$SCENARIO_JSON"
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
    marker = {"pass": "[PASS]", "fail": "[FAIL]", "deferred": "[?]", "error": "[ERR]"}.get(c["status"], "[?]")
    print(f"  {marker} {c['name']}: {c['detail']}")
PYEOF
phase_mark "criteria" "end"

# ─── Phase 6: Colony map ───
phase_mark "colony_map" "start"
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
phase_mark "colony_map" "end"

# ─── Phase 7: Playtest reporter ───
HAS_REPORTING=$(python3 -c "
import json
s = json.load(open('$SCENARIO_JSON'))
print('1' if s.get('pass_criteria') or s.get('observe') else '0')
" 2>/dev/null || echo "0")

if [[ "$HAS_REPORTING" == "1" ]]; then
    phase_mark "reporter" "start"
    log "Generating playtest report..."
    "$FRONTIER_DIR/agents/run_reporter.sh" "$RESULT_DIR" || log "Reporter failed (continuing)"
    phase_mark "reporter" "end"
fi

log "========== PLAYTEST: $SCENARIO_NAME (run $RUN_ID) COMPLETE =========="
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

# Track overseer token usage
python3 "$FRONTIER_DIR/frontier/token_tracker.py" overseer "$RESULT_DIR" 2>/dev/null || true

#!/bin/bash
# Playtest setup — generate save, load it, snapshot baseline, start telemetry monitor.
#
# Run this FIRST. Then drive the overseer (Claude Code subagent with AGENT_OVERSEER.md).
# When the overseer is done, run runner_finish.sh to score, evaluate criteria, write the report.
#
# Usage: ./frontier/runner_setup.sh <scenario_config.json> [run_id]
#
# Outputs (to frontier/results/<scenario>/run_<id>/):
#   scenario.json, before.json, score_timeline.jsonl (live), events.jsonl (live),
#   command_log.jsonl (live, written by SDK), phases.jsonl
#
# Side effects:
#   - Launches RimWorld if not already running
#   - Loads the scenario save into RimWorld and pauses
#   - Starts a background score_monitor (PID written to result_dir/.monitor.pid)
#
# Stdout ends with a single JSON line: {"result_dir": "...", "save_name": "...",
#   "map_size": N, "monitor_pid": N, "scenario_name": "...", "system_prompt_path": "...",
#   "overseer_message": "...", "command_log": "...", "sdk_path": "...",
#   "game_day_limit": N, "overseer_timeout_s": N}
# Consume that line to drive the overseer.

set -euo pipefail

SCENARIO_JSON="${1:?Usage: runner_setup.sh <scenario_config.json> [run_id]}"
RUN_ID="${2:-1}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"
source "$FRONTIER_DIR/frontier/log_event.sh" 2>/dev/null || true

SCENARIO_NAME=$("$PYTHON" -c "import json; print(json.load(open('$SCENARIO_JSON'))['name'])")
SAVE_NAME="Frontier-${SCENARIO_NAME}"
MAP_SIZE=$("$PYTHON" -c "import json; print(json.load(open('$SCENARIO_JSON')).get('map_size', 50))")

OVERSEER_TIMEOUT=1350
GAME_DAY_LIMIT=5

RESULT_DIR="$FRONTIER_DIR/frontier/results/${SCENARIO_NAME}/run_$(printf '%03d' $RUN_ID)"
mkdir -p "$RESULT_DIR"
cp "$SCENARIO_JSON" "$RESULT_DIR/scenario.json"

if [[ "$OSTYPE" == "darwin"* ]]; then
    RIMWORLD_APP="$HOME/Library/Application Support/Steam/steamapps/common/RimWorld/RimWorldMac.app"
elif [[ "$OSTYPE" == "linux"* ]]; then
    RIMWORLD_APP="$HOME/.steam/steam/steamapps/common/RimWorld"
else
    RIMWORLD_APP="$PROGRAMFILES/Steam/steamapps/common/RimWorld"
fi

LIVE_LOG="$FRONTIER_DIR/frontier/logs/agent_live.jsonl"
mkdir -p "$(dirname "$LIVE_LOG")"
log() {
    echo "[frontier $(date '+%H:%M:%S')] $*" >&2
    echo "[runner] $*" >> "$LIVE_LOG" 2>/dev/null
}

player_log_path() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "$HOME/Library/Logs/Ludeon Studios/RimWorld/Player.log"
    elif [[ "$OSTYPE" == "linux"* ]]; then
        echo "$HOME/.config/unity3d/Ludeon Studios/RimWorld by Ludeon Studios/Player.log"
    else
        echo "${LOCALAPPDATA:-$HOME/AppData/Local}/../LocalLow/Ludeon Studios/RimWorld by Ludeon Studios/Player.log"
    fi
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
            if "$PYTHON" -c "
import sys; sys.path.insert(0, '$FRONTIER_DIR/sdk')
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

log "========== PLAYTEST SETUP: $SCENARIO_NAME (run $RUN_ID) =========="

PLAYER_LOG="$(player_log_path)"
PLAYER_LOG_START_LINE=0
if [[ -f "$PLAYER_LOG" ]]; then
    PLAYER_LOG_START_LINE=$(wc -l < "$PLAYER_LOG" | tr -d ' ')
fi
echo "$PLAYER_LOG_START_LINE" > "$RESULT_DIR/.player_log_start_line"
echo "$PLAYER_LOG" > "$RESULT_DIR/.player_log_path"

# ─── Phase 0: Generate save file ───
log "Generating save for scenario: $SCENARIO_NAME..."
phase_mark "savegen" "start"
"$PYTHON" << PYEOF >&2
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
    if "$PYTHON" << PYEOF >&2
import sys, time; sys.path.insert(0, '$FRONTIER_DIR/sdk')
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

# Spawn scenario wildlife via SDK
"$PYTHON" << PYEOF >&2
import sys, json; sys.path.insert(0, '$FRONTIER_DIR/sdk')
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
"$PYTHON" << PYEOF - "$RESULT_DIR" "$MAP_SIZE" >&2
import sys, json, time; sys.path.insert(0, '$FRONTIER_DIR/sdk')
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

# Record overseer start timestamp for duration calc later
date +%s > "$RESULT_DIR/.overseer_start_ts"

# ─── Phase 2b: Telemetry smoke test + start score monitor ───
phase_mark "smoke_test" "start"
log "Running telemetry smoke test..."
"$PYTHON" << PYEOF >&2
import sys; sys.path.insert(0, '$FRONTIER_DIR/sdk')
from rimworld import RimClient
r = RimClient()
ok = True

try:
    a = r.send("read_animals")
    count = len(a.get("animals", [])) if isinstance(a, dict) else -1
    print(f"  animals: {count} ({'OK' if count >= 0 else 'BROKEN'})")
    if count < 0: ok = False
except Exception as e:
    print(f"  animals: BROKEN ({e})")
    ok = False

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

log "Starting score monitor (5s intervals)..."
> "$RESULT_DIR/score_timeline.jsonl"
"$PYTHON" "$FRONTIER_DIR/agents/score_monitor.py" "$RESULT_DIR" 5 >> "$LIVE_LOG" 2>&1 &
MONITOR_PID=$!
echo "$MONITOR_PID" > "$RESULT_DIR/.monitor.pid"
phase_mark "smoke_test" "end"

# Build the overseer system prompt
phase_mark "overseer" "start"

# Snapshot the overseer prompt into the run dir
cp "$FRONTIER_DIR/AGENT_OVERSEER.md" "$RESULT_DIR/AGENT_OVERSEER.md"
OVERSEER_PROMPT_PATH="$RESULT_DIR/AGENT_OVERSEER.md"

# Mission injection
MISSION_PROMPT=""
MISSION_BASE=$("$PYTHON" -c "import json; print(json.load(open('$SCENARIO_JSON')).get('mission','') or '')" 2>/dev/null)
MISSION_DESC=$("$PYTHON" -c "import json; print(json.load(open('$SCENARIO_JSON')).get('mission_description','') or '')" 2>/dev/null)
if [[ -n "$MISSION_BASE" ]]; then
    MISSION_UPPER=$(echo "$MISSION_BASE" | tr '[:lower:]' '[:upper:]')
    MISSION_FILE="$FRONTIER_DIR/SCENARIO_${MISSION_UPPER}.md"
    if [[ -f "$MISSION_FILE" ]]; then
        MISSION_PROMPT="$(cat "$MISSION_FILE")"
        log "Mission loaded: $MISSION_FILE"
    fi
fi
if [[ -n "$MISSION_DESC" ]]; then
    MISSION_PROMPT="${MISSION_PROMPT:+$MISSION_PROMPT

}## Scenario-Specific Instructions
$MISSION_DESC"
fi

# Compose the full system prompt the orchestrator will hand to the subagent
SYSTEM_PROMPT_PATH="$RESULT_DIR/overseer_system_prompt.md"
{
    cat "$OVERSEER_PROMPT_PATH"
    echo ""
    echo "---"
    echo ""
    echo "## Session Context"
    echo ""
    echo "Map: ${MAP_SIZE}x${MAP_SIZE}. Game is loaded, paused, incidents disabled, items unforbidden."
    echo "Save name: $SAVE_NAME"
    echo "SDK_PATH: $FRONTIER_DIR/sdk"
    echo ""
    if [[ -n "$MISSION_PROMPT" ]]; then
        echo "## MISSION INSTRUCTIONS"
        echo ""
        echo "$MISSION_PROMPT"
    fi
} > "$SYSTEM_PROMPT_PATH"

# The user message for the subagent
OVERSEER_MESSAGE_PATH="$RESULT_DIR/overseer_user_message.txt"
cat > "$OVERSEER_MESSAGE_PATH" <<EOM
Run the colony on this ${MAP_SIZE}x${MAP_SIZE} map (scenario: $SCENARIO_NAME).

Follow the strategy in your system prompt. Use skills and the reader script.

After the game reaches day 3-4, save with save_game.py and output a brief report.
EOM

COMMAND_LOG="$RESULT_DIR/command_log.jsonl"
SDK_PATH="$FRONTIER_DIR/sdk"

log "Setup complete. Result dir: $RESULT_DIR"
log "Overseer should run for up to ${OVERSEER_TIMEOUT}s or game day ${GAME_DAY_LIMIT}."

echo '{"_agent":"overseer","type":"agent_start"}' >> "$LIVE_LOG"

# Emit single JSON line for the orchestrator to consume
"$PYTHON" -c "
import json, sys
print(json.dumps({
    'result_dir': '$RESULT_DIR',
    'scenario_name': '$SCENARIO_NAME',
    'save_name': '$SAVE_NAME',
    'map_size': $MAP_SIZE,
    'monitor_pid': $MONITOR_PID,
    'system_prompt_path': '$SYSTEM_PROMPT_PATH',
    'user_message_path': '$OVERSEER_MESSAGE_PATH',
    'command_log': '$COMMAND_LOG',
    'sdk_path': '$SDK_PATH',
    'game_day_limit': $GAME_DAY_LIMIT,
    'overseer_timeout_s': $OVERSEER_TIMEOUT,
}))
"

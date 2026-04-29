#!/bin/bash
# Run a single scenario by name (looks up frontier/scenarios/<name>.json).
# Usage: ./frontier/run_scenario.sh <scenario_name> [run_id]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

SCENARIO_NAME="${1:?Usage: run_scenario.sh <scenario_name> [run_id]}"
RUN_ID="${2:-1}"

SCENARIO_JSON="$FRONTIER_DIR/frontier/scenarios/${SCENARIO_NAME}.json"
if [[ ! -f "$SCENARIO_JSON" ]]; then
    echo "ERROR: scenario not found: $SCENARIO_JSON" >&2
    echo "Available scenarios:" >&2
    ls "$FRONTIER_DIR/frontier/scenarios/" 2>/dev/null | sed 's|\.json$||' | sed 's|^|  |' >&2
    exit 1
fi

exec bash "$FRONTIER_DIR/frontier/runner.sh" "$SCENARIO_JSON" "$RUN_ID"

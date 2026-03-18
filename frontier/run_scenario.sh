#!/bin/bash
# Run a single frontier scenario by name.
# Usage: ./frontier/run_scenario.sh <scenario_name> [run_id]
#
# If a calibration scenario with that name exists, uses it.
# Otherwise, uses the adversarial generator to pick the next scenario.
#
# Examples:
#   ./frontier/run_scenario.sh baseline
#   ./frontier/run_scenario.sh cold 2
#   ./frontier/run_scenario.sh next        # auto-pick next scenario

set -euo pipefail

# Source config to get FRONTIER_DIR and AGENT_REPO
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

SCENARIO_NAME="${1:?Usage: run_scenario.sh <scenario_name|next> [run_id]}"
RUN_ID="${2:-1}"

cd "$FRONTIER_DIR"

# Generate scenario config
if [[ "$SCENARIO_NAME" == "next" ]]; then
    # Use adversarial generator to pick
    SCENARIO_JSON=$(python3 -c "
import sys; sys.path.insert(0, '.')
from frontier.tracker import FrontierTracker
from frontier.generator import AdversarialGenerator
from pathlib import Path

tracker = FrontierTracker()
gen = AdversarialGenerator(tracker)
s = gen.next_scenario()
path = Path('frontier/scenarios') / f'{s.name}.json'
path.parent.mkdir(exist_ok=True)
s.save(path)
print(str(path))
")
    echo "Auto-selected scenario: $(python3 -c "import json; print(json.load(open('$FRONTIER_DIR/$SCENARIO_JSON'))['name'])")"
    SCENARIO_JSON="$FRONTIER_DIR/$SCENARIO_JSON"
else
    # Look up by name
    SCENARIO_JSON="$FRONTIER_DIR/frontier/scenarios/${SCENARIO_NAME}.json"
    if [[ ! -f "$SCENARIO_JSON" ]]; then
        # Try generating from calibration
        python3 -c "
import sys; sys.path.insert(0, '.')
from frontier.calibration import get_scenario
from pathlib import Path

s = get_scenario('$SCENARIO_NAME')
if s is None:
    print('ERROR: Unknown scenario: $SCENARIO_NAME', file=sys.stderr)
    print('Available calibration scenarios:', file=sys.stderr)
    from frontier.calibration import CALIBRATION_SCENARIOS
    for sc in CALIBRATION_SCENARIOS:
        print(f'  {sc.name}', file=sys.stderr)
    sys.exit(1)

path = Path('frontier/scenarios') / f'{s.name}.json'
path.parent.mkdir(exist_ok=True)
s.save(path)
print(f'Generated config: {path}')
" || exit 1
    fi
fi

# Run the scenario
exec bash "$FRONTIER_DIR/frontier/runner.sh" "$SCENARIO_JSON" "$RUN_ID"

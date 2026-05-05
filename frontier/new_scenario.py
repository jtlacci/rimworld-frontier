#!/usr/bin/env python3
"""Scaffold a new playtest scenario JSON file.

Creates frontier/scenarios/<name>.json from a starter template, ready for the
builder to edit.

Usage:
    python3 frontier/new_scenario.py <name> [--mod-id Author.MyMod] [--mod-name "My Mod"]
    python3 frontier/new_scenario.py my_workbench_test --mod-id Foo.Bar --mod-name "Foo Bar"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


TEMPLATE = {
    "name": None,                            # filled in
    "map_size": 50,
    "terrain": "SoilRich",
    "mountains": "none",
    "water": "none",
    "trees": True,
    "tree_density": 0.10,
    "temperature": 20,
    "seed": 42,
    "berry_bushes": 10,
    "starting_packs": 10,
    "starting_items": {"Steel": 1000, "WoodLog": 300},
    "completed_research": ["ComplexFurniture"],
    "grass": True,
    "grass_density": 0.6,
    "mission_description": "TODO: describe what you want the agent to do in this scenario.",
    "mod_under_test": {
        "id": "Author.YourMod",
        "name": "Your Mod"
    },
    "pass_criteria": [
        {"name": "no_red_errors", "type": "no_red_errors"},
        {"name": "all_alive", "type": "all_colonists_alive"},
        # Uncomment / customize as needed:
        # {"name": "workbench_built", "type": "thing_exists", "def": "YourMod_Workbench"},
        # {"name": "steel_remaining", "type": "resource_at_least", "resource": "Steel", "min": 100},
        # {"name": "subjective_check", "type": "custom",
        #  "description": "The reporter agent will judge this from run evidence."}
    ],
    "observe": [
        "TODO: write a plain-English question you want answered."
    ]
}


SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9_]*$")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("name", help="scenario name (lowercase + underscores, e.g. my_workbench_test)")
    p.add_argument("--mod-id", help="Author.ModId (sets mod_under_test.id)", default=None)
    p.add_argument("--mod-name", help="Display name (sets mod_under_test.name)", default=None)
    p.add_argument("--force", action="store_true", help="overwrite if file exists")
    args = p.parse_args()

    if not SAFE_NAME.match(args.name):
        print(f"ERROR: invalid name '{args.name}' — use lowercase letters, digits, underscores", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    out = repo_root / "frontier" / "scenarios" / f"{args.name}.json"

    if out.exists() and not args.force:
        print(f"ERROR: {out} already exists — use --force to overwrite", file=sys.stderr)
        return 1

    scenario = dict(TEMPLATE)
    scenario["name"] = args.name
    if args.mod_id:
        scenario["mod_under_test"] = dict(scenario["mod_under_test"])
        scenario["mod_under_test"]["id"] = args.mod_id
    if args.mod_name:
        scenario["mod_under_test"] = dict(scenario["mod_under_test"])
        scenario["mod_under_test"]["name"] = args.mod_name

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scenario, indent=2) + "\n")

    print(f"Created {out.relative_to(repo_root)}")
    print()
    print("Next steps:")
    print(f"  1. Edit  {out.relative_to(repo_root)}  (set mission_description, pass_criteria, observe)")
    print(f"  2. Ask Claude Code: \"run a playtest on {args.name}\"")
    print(f"  3. Read  frontier/results/{args.name}/run_001/playtest_report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())

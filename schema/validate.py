#!/usr/bin/env python3
"""Sync checker: compares C# command registry against protocol schema.

Extracts _handlers["..."] entries from GameBridge.cs, loads command keys
from commands.json, and reports any drift between the two sets.

Exit 0 if in sync, exit 1 if drift detected.
"""

import json
import os
import re
import sys


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bridge_path = os.path.join(script_dir, "..", "Source", "GameBridge.cs")
    schema_path = os.path.join(script_dir, "commands.json")

    # --- Extract handler names from C# ---
    with open(bridge_path, "r") as f:
        bridge_src = f.read()

    cs_commands = set(re.findall(r'_handlers\["([^"]+)"\]', bridge_src))

    # --- Load schema command keys ---
    with open(schema_path, "r") as f:
        schema = json.load(f)

    schema_commands = set(schema.get("commands", {}).keys())

    # --- Compare ---
    in_cs_not_schema = sorted(cs_commands - schema_commands)
    in_schema_not_cs = sorted(schema_commands - cs_commands)

    print("Checking schema sync...")
    print(f"  GameBridge.cs: {len(cs_commands)} commands")
    print(f"  commands.json: {len(schema_commands)} commands")

    if not in_cs_not_schema and not in_schema_not_cs:
        print("  \u2713 All commands in sync")
        return 0

    if in_cs_not_schema:
        print("  \u2717 In C# but not in schema:")
        for cmd in in_cs_not_schema:
            print(f"    - {cmd}")
    else:
        print("  In C# but not in schema: (none)")

    if in_schema_not_cs:
        print("  \u2717 In schema but not in C#:")
        for cmd in in_schema_not_cs:
            print(f"    - {cmd}")
    else:
        print("  In schema but not in C#: (none)")

    return 1


if __name__ == "__main__":
    sys.exit(main())

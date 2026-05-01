#!/usr/bin/env python3
"""Set up wood-based cooking: campfire + butcher + stove + bills + harvest."""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient

r = RimClient()
cx = int(sys.argv[2]) if len(sys.argv) > 2 else 25
cz = int(sys.argv[3]) if len(sys.argv) > 3 else 25

try:
    result = r.setup_cooking(cx, cz)
    print(f"Cooking setup: {result}")
except Exception as e:
    print(f"FAILED setup_cooking: {e}")

try:
    r.harvest(cx, cz, radius=50)
    print("Berry harvest designated (radius=50)")
except Exception as e:
    print(f"FAILED harvest: {e}")

try:
    r.hunt_all_wildlife()
    print("All safe wildlife designated for hunting")
except Exception as e:
    print(f"FAILED hunt: {e}")

try:
    r.add_cooking_bills(retry=True)
    print("Cooking bills added")
except Exception as e:
    print(f"FAILED bills: {e}")

try:
    r.setup_zones(cx, cz)
    print("Stockpile zones created")
except Exception as e:
    print(f"FAILED zones: {e}")

r.close()

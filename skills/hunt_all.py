#!/usr/bin/env python3
"""Hunt all safe wildlife on the map."""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient

r = RimClient()
try:
    result = r.hunt_all_wildlife()
    print(f"Hunted: {result.get('designated', 0)} designated")
    print(f"Species: {result.get('species', [])}")
    if result.get('skipped'):
        print(f"Skipped (dangerous): {result['skipped']}")
except Exception as e:
    print(f"FAILED: {e}")
r.close()

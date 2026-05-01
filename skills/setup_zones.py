#!/usr/bin/env python3
"""Create stockpile zones around colony center."""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient
r = RimClient()
cx = int(sys.argv[2]) if len(sys.argv) > 2 else 25
cz = int(sys.argv[3]) if len(sys.argv) > 3 else 25

try:
    result = r.setup_zones(cx, cz)
    print(f"Zones: {result}")
except Exception as e:
    print(f"FAILED setup_zones: {e}")

r.close()

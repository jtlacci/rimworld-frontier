#!/usr/bin/env python3
"""Set up electric cooking: wind turbine + conduit + electric stove + butcher."""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient
r = RimClient()
cx = int(sys.argv[2]) if len(sys.argv) > 2 else 25
cz = int(sys.argv[3]) if len(sys.argv) > 3 else 25

# Butcher spot (free, instant)
try:
    for dx in [3, -3, 5, -5]:
        try: r.build("ButcherSpot", cx+dx, cz); print(f"ButcherSpot at ({cx+dx},{cz})"); break
        except: continue
    r.add_bill("ButcherSpot", "ButcherCorpseFlesh")
    print("Butcher bill added")
except Exception as e: print(f"FAILED butcher: {e}")

# Electric stove FIRST (before conduit — avoids blueprint collision)
stove_pos = None
for dx, dz in [(3,0),(-3,0),(0,3),(0,-3),(4,0),(-4,0)]:
    try:
        r.build("ElectricStove", cx+dx, cz+dz)
        stove_pos = (cx+dx, cz+dz); print(f"ElectricStove at ({cx+dx},{cz+dz})"); break
    except: continue
if not stove_pos: print("FAILED: could not place ElectricStove")

# Wind turbine (needs 7-tile clear east/west)
turbine_pos = None
for tz in [-15, 15, -12, 12, -18, 18]:
    try:
        r.build("WindTurbine", cx, cz+tz)
        turbine_pos = (cx, cz+tz); print(f"WindTurbine at ({cx},{cz+tz})"); break
    except: continue
if not turbine_pos: print("FAILED: could not place WindTurbine")

# Conduit from turbine to stove
if turbine_pos and stove_pos:
    tx, tz_ = turbine_pos; sx, sz = stove_pos; count = 0
    for z in range(min(tz_, sz), max(tz_, sz)+1):
        try: r.build("PowerConduit", tx, z); count += 1
        except: pass
    if tx != sx:
        for x in range(min(tx, sx), max(tx, sx)+1):
            try: r.build("PowerConduit", x, sz); count += 1
            except: pass
    print(f"PowerConduit: {count} tiles")

try:
    r.setup_zones(cx, cz)
    print("Stockpile zones created")
except Exception as e: print(f"FAILED zones: {e}")

r.close()
print("DONE — unpause, wait for construction, then add_cooking_bills(retry=True)")

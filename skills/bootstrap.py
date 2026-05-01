#!/usr/bin/env python3
"""Colony bootstrap: unforbid, enable manual priorities, assign roles, designate food."""
import sys, json
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient
r = RimClient()

# Step 1-2: Unforbid + manual priorities
try: r.unforbid_all(); print("Unforbid all")
except Exception as e: print(f"FAILED unforbid: {e}")
try: r.send("set_manual_priorities", enable=True); print("Manual priorities enabled")
except Exception as e: print(f"FAILED manual priorities: {e}")

# Step 3: Read colonists, assign roles
colonists = r.colonists().get("colonists", [])
cook, hunter, builder = None, None, None
for c in colonists:
    name = c.get("name", "")
    short = name.split("'")[1] if "'" in name else name.split()[-1]
    disabled = c.get("disabledWork", "")
    skills = {s["name"]: s["level"] for s in c.get("skills", []) if isinstance(s, dict)}
    c["_short"] = short; c["_disabled"] = disabled; c["_skills"] = skills

# Pick cook (highest Cooking)
colonists.sort(key=lambda c: c["_skills"].get("Cooking", 0), reverse=True)
cook = colonists[0]["_short"]
# Pick hunter (highest Shooting, not Violent disabled)
for c in sorted(colonists, key=lambda c: c["_skills"].get("Shooting", 0), reverse=True):
    if "Violent" not in c["_disabled"]: hunter = c["_short"]; break
# Everyone else is builder
builders = [c["_short"] for c in colonists if c["_short"] not in (cook, hunter)]

print(f"Roles: cook={cook} hunter={hunter} builders={builders}")

# Step 4: Assign priorities
for c in colonists:
    n = c["_short"]
    try:
        if n == cook:
            r.set_priority(n, "Cooking", 1); r.set_priority(n, "Hauling", 3); r.set_priority(n, "Cleaning", 4)
        elif n == hunter:
            r.set_priority(n, "Hunting", 1); r.set_priority(n, "Growing", 2); r.set_priority(n, "Construction", 3)
        else:
            r.set_priority(n, "Growing", 1); r.set_priority(n, "Construction", 2); r.set_priority(n, "Hauling", 3)
        r.set_priority(n, "Firefighting", 1); r.set_priority(n, "PatientCare", 1)
    except Exception as e: print(f"FAILED priority {n}: {e}")

# Step 5: Designate food
map_info = r.map_info()
cx, cz = map_info["size"]["x"] // 2, map_info["size"]["z"] // 2
try: r.harvest(cx, cz, radius=50); print("Berry harvest designated")
except Exception as e: print(f"FAILED harvest: {e}")
try: result = r.hunt_all_wildlife(); print(f"Hunt: {result.get('designated', 0)} designated")
except Exception as e: print(f"FAILED hunt: {e}")

print(f"Bootstrap complete. Center=({cx},{cz})")
r.close()

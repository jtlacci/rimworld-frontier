#!/usr/bin/env python3
"""Read game state and print a structured summary for the overseer.

Usage:
  python3 read_state.py SDK_PATH              # full state
  python3 read_state.py SDK_PATH food         # food pipeline only
  python3 read_state.py SDK_PATH colonists    # colonists + jobs + needs
  python3 read_state.py SDK_PATH buildings    # buildings + power + bills
  python3 read_state.py SDK_PATH animals      # wild + tame animals
  python3 read_state.py SDK_PATH resources    # all resource counts
  python3 read_state.py SDK_PATH alerts       # active alerts
"""
import sys, json, os

sdk_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SDK_PATH", "sdk")
section = sys.argv[2] if len(sys.argv) > 2 else "all"
sys.path.insert(0, sdk_path)

from rimworld import RimClient
r = RimClient()

def show_header():
    weather = r.weather()
    print(f"Day {weather.get('dayOfYear', '?')} Hour {weather.get('hour', 0):.1f} | {weather.get('season', '?')} | {weather.get('temperature', '?')}°C")

def show_resources():
    resources = r.resources()
    ground = resources.pop("_ground", {})
    if not isinstance(ground, dict):
        ground = {}
    wood = resources.get("WoodLog", 0) + ground.get("WoodLog", 0)
    steel = resources.get("Steel", 0) + ground.get("Steel", 0)
    comps = resources.get("ComponentIndustrial", 0) + ground.get("ComponentIndustrial", 0)
    meals = resources.get("MealSimple", 0) + resources.get("MealFine", 0) + ground.get("MealSimple", 0) + ground.get("MealFine", 0)
    raw_meat = sum(v for k, v in resources.items() if k.startswith("Meat_")) + sum(v for k, v in ground.items() if k.startswith("Meat_"))
    raw_berries = resources.get("RawBerries", 0) + ground.get("RawBerries", 0)
    print(f"Resources: Wood={wood} Steel={steel} Components={comps} Meals={meals} RawMeat={raw_meat} RawBerries={raw_berries}")
    if ground:
        print(f"  (on ground, not stockpiled: {dict(ground)})")

def show_food():
    resources = r.resources()
    ground = resources.pop("_ground", {})
    if not isinstance(ground, dict):
        ground = {}
    meals = resources.get("MealSimple", 0) + ground.get("MealSimple", 0)
    raw_meat = sum(v for k, v in resources.items() if k.startswith("Meat_")) + sum(v for k, v in ground.items() if k.startswith("Meat_"))
    raw_berries = resources.get("RawBerries", 0) + ground.get("RawBerries", 0)
    total_raw = raw_meat + raw_berries
    cookable = total_raw // 10
    bills = r.bills().get("workbenches", [])
    cooking_stations = [wb for wb in bills if wb.get("def") in ("Campfire", "FueledStove", "ElectricStove")]
    animals = r.animals().get("animals", [])
    wild = [a for a in animals if not a.get("tame")]
    print(f"FOOD: meals={meals} raw_meat={raw_meat} berries={raw_berries} cookable={cookable}")
    print(f"  Cooking: {len(cooking_stations)} station(s)")
    for s in cooking_stations:
        print(f"    {s.get('def')} at ({s.get('position',{}).get('x','?')},{s.get('position',{}).get('z','?')}): {len(s.get('bills',[]))} bills")
    print(f"  Wild animals: {len(wild)} (potential meat)")

def show_colonists():
    colonists = r.colonists().get("colonists", [])
    print(f"Colonists ({len(colonists)}):")
    for c in colonists:
        name = c.get("name", "?")
        short = name.split("'")[1] if "'" in name else name.split()[-1]
        job = c.get("currentJob", "idle")
        target = c.get("jobTarget", "")
        health = c.get("health", 1.0)
        mood = c.get("mood", 0.5)
        disabled = c.get("disabledWork", "")
        traits = [t.get("label", "") for t in c.get("traits", [])]
        skills = {s["name"]: s["level"] for s in c.get("skills", []) if isinstance(s, dict)}
        top_skills = sorted(skills.items(), key=lambda x: -x[1])[:4]
        print(f"  {short}: {job}{'('+target+')' if target else ''} hp={health:.0%} mood={mood:.0%}")
        print(f"    skills: {', '.join(f'{k}={v}' for k,v in top_skills)}")
        if disabled: print(f"    DISABLED: {disabled}")
        if traits: print(f"    traits: {', '.join(traits)}")

def show_buildings():
    buildings = r.buildings()
    blist = buildings.get("buildings", [])
    rooms = buildings.get("rooms", [])
    bills = r.bills().get("workbenches", [])
    if blist:
        bdefs = {}
        for b in blist:
            bdefs[b.get("def", "?")] = bdefs.get(b.get("def", "?"), 0) + 1
        print(f"Buildings ({len(blist)}): {dict(bdefs)}")
    if rooms:
        for rm in rooms:
            print(f"  Room: {rm.get('role','?')} — {rm.get('cellCount',0)} cells, impressiveness={rm.get('impressiveness',0):.1f}")
    if bills:
        print(f"Workbenches:")
        for wb in bills:
            bl = [b.get("recipe", "?") for b in wb.get("bills", [])]
            print(f"  {wb.get('def','?')}: bills={bl}")

def show_animals():
    animals = r.animals().get("animals", [])
    wild = [a for a in animals if not a.get("tame")]
    tame = [a for a in animals if a.get("tame")]
    if wild:
        species = {}
        for a in wild: species[a.get("def", a.get("kind", "?"))] = species.get(a.get("def", a.get("kind", "?")), 0) + 1
        print(f"Wild ({len(wild)}): {dict(species)}")
    if tame:
        print(f"Tame ({len(tame)}): {[a.get('name', a.get('def', '?')) for a in tame]}")
    if not wild and not tame:
        print("No animals")

def show_alerts():
    alerts = r.alerts().get("alerts", [])
    if alerts:
        print(f"Alerts ({len(alerts)}): {[a.get('label', '?') for a in alerts]}")
    else:
        print("No alerts")

show_header()
print()
if section == "all":
    show_resources(); print()
    show_colonists(); print()
    show_buildings(); print()
    show_animals(); print()
    show_alerts()
    research = r.research()
    print(f"\nResearch: current={research.get('current') or 'none'}, completed={research.get('completed', [])}")
    zones = r.zones().get("zones", [])
    if zones:
        print(f"Zones ({len(zones)}):")
        for z in zones: print(f"  {z.get('type','?')}: {z.get('label','?')} ({z.get('cellCount',0)} cells)")
elif section == "food": show_food()
elif section == "colonists": show_colonists()
elif section == "buildings": show_buildings()
elif section == "animals": show_animals()
elif section == "resources": show_resources()
elif section == "alerts": show_alerts()
else: print(f"Unknown section: {section}. Use: all, food, colonists, buildings, animals, resources, alerts")

r.close()

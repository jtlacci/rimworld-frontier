"""Colony state snapshot for auditing and evaluation."""

import json
import os


def take_snapshot(r):
    """Capture full colony state for before/after comparison."""
    snapshot = {
        "colonists": r.colonists(),
        "resources": r.resources(),
        "zones": r.zones(),
        "research": r.research(),
        "work_priorities": r.work_priorities(),
        "map_info": r.map_info(),
        "weather": r.weather(),
        "threats": r.threats(),
        "alerts": r.alerts(),
    }

    # Buildings + rooms
    try:
        snapshot["buildings"] = r.buildings()
    except Exception as e:
        snapshot["buildings"] = {"error": str(e)}

    # Colony stats (wealth, beauty, impressiveness)
    try:
        snapshot["colony_stats"] = r.colony_stats()
    except Exception as e:
        snapshot["colony_stats"] = {"error": str(e)}

    # Thoughts per colonist — API needs nickname/short name, not full name
    snapshot["thoughts"] = {}
    for c in snapshot["colonists"].get("colonists", []):
        full_name = c.get("name", "")
        if not full_name:
            continue
        # Extract nickname: "Gabra 'Gabs' Dawnlight" → "Gabs", "Baffin Benjamin" → "Benjamin"
        import re
        nick_match = re.search(r"'([^']+)'", full_name)
        short_name = nick_match.group(1) if nick_match else full_name.split()[-1]
        for try_name in [short_name, full_name, full_name.split()[0]]:
            try:
                snapshot["thoughts"][full_name] = r.thoughts(try_name)
                break
            except Exception:
                continue

    # Needs per colonist — colonist_needs() returns {"colonists": [{name, food, rest, ...}]}
    snapshot["needs"] = {}
    try:
        all_needs = r.colonist_needs()
        for entry in all_needs.get("colonists", []):
            name = entry.get("name", "")
            if name:
                snapshot["needs"][name] = entry
    except Exception:
        # Fallback: try per-pawn needs() which returns {"needs": [{name, label, level}]}
        for c in snapshot["colonists"].get("colonists", []):
            name = c.get("name", "")
            if name:
                try:
                    snapshot["needs"][name] = r.needs(name)
                except Exception:
                    pass

    # Blueprint/frame count + survival pack count (ground items invisible to resourceCounter)
    try:
        mi = snapshot["map_info"]
        w = mi.get("size", mi).get("x", 250) if isinstance(mi.get("size", mi), dict) else 250
        h = mi.get("size", mi).get("z", 250) if isinstance(mi.get("size", mi), dict) else 250
        blueprints = r.scan_items(0, 0, w, h, kind="blueprint,frame")
        snapshot["blueprint_count"] = len(blueprints) if isinstance(blueprints, list) else 0
    except Exception:
        snapshot["blueprint_count"] = 0

    # Scan for survival packs anywhere on map (resourceCounter misses ground items)
    try:
        packs = r.scan_items(0, 0, w, h, kind="item")
        pack_count = sum(
            item.get("stackCount", 1) for item in (packs if isinstance(packs, list) else [])
            if item.get("def") == "MealSurvivalPack"
        )
        snapshot["survival_packs_on_map"] = pack_count
    except Exception:
        snapshot["survival_packs_on_map"] = 0

    # Berry bushes and harvestable plants
    try:
        snapshot["plants"] = r.plants()
    except Exception:
        snapshot["plants"] = {"plants": [], "count": 0}

    return snapshot


def _explain_building_progress(building_defs, building_wealth, after):
    """Why is building_progress low? Surface workforce + material data."""
    parts = [f"wealth={building_wealth:.0f} ({len(building_defs)} buildings)"]
    # Who has Construction as priority 1?
    constructors = []
    prios = after.get("work_priorities", {})
    for col in prios.get("colonists", []):
        p = col.get("priorities", {})
        c_level = p.get("Construction", 0)
        r_level = p.get("Research", 0)
        name = col.get("name", "?")
        if c_level == 1:
            constructors.append(name)
        elif r_level == 1 and c_level > 1:
            parts.append(f"{name} has Research=1 Construction={c_level} (building instead of researching?)")
    parts.append(f"constructors at priority 1: {constructors if constructors else 'NONE'}")
    bp = after.get("blueprint_count", 0)
    if bp > 0:
        parts.append(f"{bp} blueprints still pending (queue bottleneck?)")
    return "; ".join(parts)


def _explain_production(building_defs, effective_throughput, after):
    """Why is production_throughput low?"""
    present = [d for d in building_defs if d in (
        "Campfire", "FueledStove", "ElectricStove", "ButcherSpot", "TableButcher",
        "HandTailoringBench", "SimpleResearchBench", "HiTechResearchBench")]
    missing_high_value = []
    for b in ["FueledStove", "HandTailoringBench", "SimpleResearchBench"]:
        if b not in building_defs:
            missing_high_value.append(b)
    parts = [f"effective={effective_throughput:.1f}, built={present}"]
    if missing_high_value:
        parts.append(f"missing: {missing_high_value}")
    return "; ".join(parts)


def _explain_impressiveness(player_rooms, after):
    """Why is avg_impressiveness low?"""
    if not player_rooms:
        return "no player rooms detected"
    details = []
    for rm in player_rooms:
        role = rm.get("role", "?")
        imp = rm.get("impressiveness", 0)
        cells = rm.get("cells", rm.get("cellCount", 0))
        details.append(f"{role}(imp={imp:.1f}, cells={cells})")
    return "; ".join(details)


def _explain_bedrooms(bedroom_rooms, after):
    """Why is bedrooms score low?"""
    if not bedroom_rooms:
        return "no bedroom/barracks rooms found — walls incomplete or not enclosed?"
    details = []
    for rm in bedroom_rooms:
        imp = rm.get("impressiveness", 0)
        details.append(f"imp={imp:.1f}")
    avg = sum(rm.get("impressiveness", 0) for rm in bedroom_rooms) / len(bedroom_rooms)
    return f"avg_impressiveness={avg:.1f} (need ≥15 for 0.7, ≥30 for 1.0), rooms: {details}"


def _explain_storage(has_storage_room, resources, after):
    """Why is storage_room low?"""
    if not has_storage_room:
        return "no enclosed storage room detected (need room with stockpile zone inside)"
    total = sum(v for v in resources.values() if isinstance(v, (int, float)))
    return f"room exists but total_stored={total} (need ≥300 for 1.0)"


def _explain_self_sufficiency(before_packs, after_packs, building_defs, after):
    """Why is self_sufficiency low?"""
    consumed = max(0, before_packs - after_packs)
    has_cooking = any(d in building_defs for d in ["Campfire", "FueledStove", "ElectricStove"])
    meals = after.get("resources", {}).get("MealSimple", 0) + after.get("resources", {}).get("MealFine", 0)
    return f"packs {before_packs}→{after_packs} ({consumed} consumed), meals_cooked={meals}, has_cooking={has_cooking}"


def score_snapshot(before, after, duration_s=0, overseer_tokens=0, overseer_cost_usd=0):
    """Score colony performance. Returns (total, max_possible, breakdown).

    Scoring uses continuous scales (0.0-1.0 per metric) weighted by importance.
    Errors and failures have high impact.
    """
    scores = {}
    weights = {}

    before_colonists = before.get("colonists", {}).get("colonists", [])
    after_colonists = after.get("colonists", {}).get("colonists", [])
    before_count = len(before_colonists)
    after_count = len(after_colonists)

    # Collect all thought labels for analysis
    all_thoughts = []
    for name, t in after.get("thoughts", {}).items():
        if isinstance(t, list):
            all_thoughts.extend(t)
        elif isinstance(t, dict):
            all_thoughts.extend(t.get("thoughts", []))
    thought_labels = [str(t.get("label", t) if isinstance(t, dict) else t).lower()
                      for t in all_thoughts]

    # ═══════════════════════════════════════════════════════════════
    # SURVIVAL (weight: 30) — highest priority, binary-ish
    # ═══════════════════════════════════════════════════════════════

    # All colonists alive (0 or 1)
    scores["alive"] = 1.0 if after_count >= before_count else 0.0
    weights["alive"] = 5

    # No colonists downed (0 or 1)
    downed = sum(1 for c in after_colonists if c.get("downed", False))
    scores["not_downed"] = 1.0 if downed == 0 else 0.0
    weights["not_downed"] = 2

    # No starvation/malnourishment (check thoughts, needs, AND health conditions)
    starvation_terms = ["starv", "malnourish", "malnutrition"]
    starve_thoughts = any(any(term in t for term in starvation_terms) for t in thought_labels)

    # Also check colonist health conditions (hediffs) for Malnutrition
    for c in after_colonists:
        hediffs = c.get("hediffs", c.get("health_conditions", []))
        if isinstance(hediffs, list):
            for h in hediffs:
                hlabel = str(h.get("label", h.get("def", "")) if isinstance(h, dict) else h).lower()
                if any(term in hlabel for term in starvation_terms):
                    starve_thoughts = True

    worst_food = 1.0
    for name, needs in after.get("needs", {}).items():
        if isinstance(needs, dict):
            # Format from colonist_needs(): {"name": ..., "food": 0.XX, ...}
            food = needs.get("food", needs.get("Food", None))
            if isinstance(food, (int, float)) and food >= 0:
                worst_food = min(worst_food, food)
            # Also check if needs is {"needs": [{label, level}, ...]}
            needs_list = needs.get("needs", [])
            if isinstance(needs_list, list):
                for n in needs_list:
                    if isinstance(n, dict) and n.get("label", "").lower() == "food":
                        lvl = n.get("level", 1.0)
                        if isinstance(lvl, (int, float)):
                            worst_food = min(worst_food, lvl)
        elif isinstance(needs, list):
            for n in needs:
                if isinstance(n, dict) and n.get("label", "").lower() == "food":
                    lvl = n.get("level", 1.0)
                    if isinstance(lvl, (int, float)):
                        worst_food = min(worst_food, lvl)

    if starve_thoughts:
        scores["food_safety"] = 0.0
    elif worst_food < 0.2:
        scores["food_safety"] = 0.3
    elif worst_food < 0.3:
        scores["food_safety"] = 0.5
    elif worst_food < 0.4:
        scores["food_safety"] = 0.7
    else:
        scores["food_safety"] = 1.0
    weights["food_safety"] = 6

    # No temperature crises
    temp_issues = any("hypotherm" in t or "heatstroke" in t for t in thought_labels)
    scores["temp_safety"] = 0.0 if temp_issues else 1.0
    weights["temp_safety"] = 3

    # ═══════════════════════════════════════════════════════════════
    # BASIC NEEDS (weight: 10) — table stakes
    # ═══════════════════════════════════════════════════════════════

    resources = after.get("resources", {})
    zones = after.get("zones", {}).get("zones", [])

    # Shelter — all colonists in beds in enclosed rooms
    shelter_stats = after.get("colony_stats", {})
    shelter_rooms = shelter_stats.get("rooms", []) if isinstance(shelter_stats, dict) else []
    if not shelter_rooms:
        shelter_rooms = after.get("buildings", {}).get("rooms", []) if isinstance(after.get("buildings"), dict) else []
    enclosed_rooms = [rm for rm in shelter_rooms if isinstance(rm, dict)
                      and rm.get("role") and rm.get("role") != "None"
                      and (rm.get("cells", 0) or rm.get("cellCount", 0)) < 100]
    # A barracks shelters all colonists with beds inside it, not just 1
    barracks_rooms = [rm for rm in enclosed_rooms
                      if rm.get("role", "").lower() in ("barracks", "bedroom")]
    bedroom_capacity = 0
    for rm in barracks_rooms:
        cells = rm.get("cells", rm.get("cellCount", 0))
        if rm.get("role", "").lower() == "barracks":
            bedroom_capacity += min(cells // 4, after_count)  # ~1 bed per 4 cells
        else:
            bedroom_capacity += 1  # individual bedroom = 1 colonist
    sheltered = min(bedroom_capacity + (len(enclosed_rooms) - len(barracks_rooms)), after_count)

    if sheltered >= after_count:
        scores["shelter"] = 1.0
    elif sheltered >= 1:
        scores["shelter"] = sheltered / max(after_count, 1)
    else:
        scores["shelter"] = 0.0
    weights["shelter"] = 10

    # Thought-based shelter penalty: sleeping problems reveal shelter failed during session
    sleep_problems = sum(1 for t in thought_labels
                         if "slept outside" in t or "slept on ground" in t or "slept in the cold" in t)
    if sleep_problems > 0:
        # Each colonist with sleep issues reduces shelter score
        penalty = min(0.5, sleep_problems * 0.15)  # up to 0.5 reduction
        scores["shelter"] = max(0, scores["shelter"] - penalty)

    # Stockpiles
    stockpile_zones = [z for z in zones if "Stockpile" in z.get("type", "")]
    if len(stockpile_zones) >= 3:
        scores["stockpiles"] = 1.0
    elif len(stockpile_zones) >= 2:
        scores["stockpiles"] = 0.5
    elif len(stockpile_zones) >= 1:
        scores["stockpiles"] = 0.3
    else:
        scores["stockpiles"] = 0.0
    weights["stockpiles"] = 1

    # Self-sufficiency: how many survival meals were consumed?
    # Starting with ~35 survival packs. If you're self-sustaining, you barely touch them.
    before_survival = before.get("resources", {}).get("MealSurvivalPack", 0)
    after_survival = resources.get("MealSurvivalPack", 0)
    # Use scan_items count if available (more accurate — counts ground items too)
    scan_packs = after.get("survival_packs_on_map", 0)
    if scan_packs > after_survival:
        after_survival = scan_packs
    before_scan_packs = before.get("survival_packs_on_map", 0)
    if before_scan_packs > before_survival:
        before_survival = before_scan_packs
    # WORKAROUND: before snapshot often shows 0 resources because resourceCounter
    # doesn't count items outside stockpile zones (drop pods at game start).
    # If before is 0 but after has packs, use known starting count from seed save.
    if before_survival == 0 and after_survival > 0:
        before_survival = 6  # Frontier saves ship with 6 MealSurvivalPack
    survival_consumed = max(0, before_survival - after_survival)

    # Check if meals were actually produced (cooking pipeline working)
    after_meals = resources.get("MealSimple", 0) + resources.get("MealFine", 0)
    _bldg_list = after.get("buildings", {}).get("buildings", []) if isinstance(after.get("buildings"), dict) else []
    _bldg_defs = [b.get("def", "") for b in _bldg_list if isinstance(b, dict)]
    has_cooking = any(d in _bldg_defs for d in ("FueledStove", "Campfire", "ElectricStove"))

    if before_survival > 0:
        survival_pct_remaining = after_survival / before_survival
        if survival_pct_remaining >= 0.9:      # barely touched — fully self-sustaining
            scores["self_sufficiency"] = 1.0
        elif survival_pct_remaining >= 0.7:    # some consumed
            scores["self_sufficiency"] = 0.7
        elif survival_pct_remaining >= 0.4:    # relying heavily
            scores["self_sufficiency"] = 0.3
        else:                                   # ate almost everything
            scores["self_sufficiency"] = 0.0
    else:
        scores["self_sufficiency"] = 0.5  # no starting packs to measure

    # Hard penalty: cooking setup exists but 0 meals produced → pipeline broken
    if has_cooking and after_meals == 0:
        scores["self_sufficiency"] = min(scores["self_sufficiency"], 0.1)

    weights["self_sufficiency"] = 15

    # ═══════════════════════════════════════════════════════════════
    # INFRASTRUCTURE (weight: 30) — colony development emphasis
    # ═══════════════════════════════════════════════════════════════

    # Parse rooms and buildings
    after_buildings = after.get("buildings", {})
    # Rooms come from colony_stats (primary) or buildings (fallback)
    colony_stats = after.get("colony_stats", {})
    rooms = colony_stats.get("rooms", []) if isinstance(colony_stats, dict) else []
    if not rooms:
        rooms = after_buildings.get("rooms", []) if isinstance(after_buildings, dict) else []
    building_list = after_buildings.get("buildings", []) if isinstance(after_buildings, dict) else []
    building_defs = [b.get("def", "") for b in building_list if isinstance(b, dict)]

    # Room types present (filter out ancient ruins by size — cells/cellCount > 100)
    player_rooms = [rm for rm in rooms if isinstance(rm, dict)
                    and rm.get("role") and rm.get("role") != "None"
                    and (rm.get("cells", 0) or rm.get("cellCount", 0)) < 100]
    room_roles = [rm.get("role", "").lower() for rm in player_rooms]

    # Bedrooms — scored by room impressiveness, not just existence
    bedroom_rooms = [rm for rm in player_rooms
                     if rm.get("role", "").lower() in ("bedroom", "barracks")]
    if not bedroom_rooms:
        scores["bedrooms"] = 0.0
    else:
        avg_bed_impress = sum(rm.get("impressiveness", 0) for rm in bedroom_rooms) / len(bedroom_rooms)
        if avg_bed_impress >= 40:
            scores["bedrooms"] = 1.0
        elif avg_bed_impress >= 25:
            scores["bedrooms"] = 0.7
        elif avg_bed_impress >= 15:
            scores["bedrooms"] = 0.5
        elif avg_bed_impress >= 5:
            scores["bedrooms"] = 0.3
        else:
            scores["bedrooms"] = 0.1  # awful rooms
    weights["bedrooms"] = 6

    # Indoor storage — scored by actual storage utilization, not just room existence
    has_storage_room = any("storage" in r or "stockpile" in r or "warehouse" in r for r in room_roles)
    if not has_storage_room:
        zones_list = after.get("zones", {})
        if isinstance(zones_list, dict):
            zones_list = zones_list.get("zones", [])
        stockpile_zones = [z for z in zones_list if isinstance(z, dict) and "Stockpile" in z.get("type", "")]
        large_rooms = [rm for rm in player_rooms if (rm.get("cells", 0) or rm.get("cellCount", 0)) >= 15
                       and rm.get("role", "").lower() not in ("barracks", "bedroom")]
        if stockpile_zones and large_rooms:
            has_storage_room = True
    if not has_storage_room:
        scores["storage_room"] = 0.0
    else:
        # Score by total resources stored (sum of all stockpiled item quantities)
        total_stored = sum(v for v in resources.values() if isinstance(v, (int, float)))
        if total_stored >= 300:
            scores["storage_room"] = 1.0
        elif total_stored >= 150:
            scores["storage_room"] = 0.7
        elif total_stored >= 50:
            scores["storage_room"] = 0.5
        else:
            scores["storage_room"] = 0.3  # room exists but mostly empty
    weights["storage_room"] = 3

    # Production throughput — weighted by workspeed, constrained by pawn count
    # Only the BEST building per production type counts (no double-dipping)
    production_types = {
        "cooking": {"Campfire": 0.3, "FueledStove": 0.8, "ElectricStove": 1.0},
        "butchering": {"ButcherSpot": 0.3, "TableButcher": 0.8},
        "tailoring": {"HandTailoringBench": 0.4, "ElectricTailoringBench": 0.8},
        "sculpting": {"TableSculpting": 0.6},
        "machining": {"TableMachining": 0.8, "HiToolBench": 0.8},
        "fabrication": {"FabricationBench": 1.0},
        "smelting": {"ElectricSmelter": 0.8},
        "research": {"SimpleResearchBench": 0.5, "HiTechResearchBench": 1.0},
        "nutrient_paste": {"NutrientPasteDispenser": 1.2},
        "brewing": {"Brewery": 0.6},
        "drugs": {"DrugLab": 0.8},
    }
    # For each type, take the highest workspeed among buildings present
    total_workspeed = 0
    for type_name, type_buildings in production_types.items():
        best = max((type_buildings[d] for d in building_defs if d in type_buildings), default=0)
        total_workspeed += best
    # Each pawn can operate ~1 station effectively
    effective_throughput = min(total_workspeed, after_count * 1.0)
    if effective_throughput >= 2.0:
        # Open-ended: bonus points for exceeding base threshold
        scores["production_throughput"] = 1.0 + (effective_throughput - 2.0) / 2.0
    elif effective_throughput >= 1.5:
        scores["production_throughput"] = 0.7
    elif effective_throughput >= 0.8:
        scores["production_throughput"] = 0.5
    elif effective_throughput > 0:
        scores["production_throughput"] = 0.3
    else:
        scores["production_throughput"] = 0.0
    weights["production_throughput"] = 8


    # Build queue health
    bp_count = after.get("blueprint_count", 0)
    if bp_count == 0:
        scores["queue_health"] = 1.0
    elif bp_count < 15:
        scores["queue_health"] = 0.8
    elif bp_count < 30:
        scores["queue_health"] = 0.5
    else:
        scores["queue_health"] = 0.2
    weights["queue_health"] = 2

    # Deterioration alerts
    alerts = after.get("alerts", [])
    alert_labels = []
    if isinstance(alerts, list):
        alert_labels = [str(a.get("label", a) if isinstance(a, dict) else a).lower() for a in alerts]
    elif isinstance(alerts, dict):
        alert_labels = [str(a).lower() for a in alerts.get("alerts", [])]
    has_deterioration = any("deterior" in a for a in alert_labels)
    scores["no_deterioration"] = 0.0 if has_deterioration else 1.0
    weights["no_deterioration"] = 2

    # Research progress — reward completing research projects
    research_data = after.get("research", {})
    completed_research = research_data.get("completed", []) if isinstance(research_data, dict) else []
    before_research = before.get("research", {})
    before_completed = before_research.get("completed", []) if isinstance(before_research, dict) else []
    new_research = len(completed_research) - len(before_completed)
    current_project = research_data.get("current") if isinstance(research_data, dict) else None
    if new_research >= 2:
        scores["research_progress"] = 1.0
    elif new_research >= 1:
        scores["research_progress"] = 0.7
    elif current_project:
        scores["research_progress"] = 0.3  # at least researching something
    else:
        scores["research_progress"] = 0.0
    weights["research_progress"] = 3

    # ═══════════════════════════════════════════════════════════════
    # COLONY QUALITY (weight: 35) — building wealth & impressiveness
    # ═══════════════════════════════════════════════════════════════

    stats = after.get("colony_stats", {})
    if not isinstance(stats, dict) or "error" in stats:
        scores["wealth_growth"] = 0.0
        scores["avg_beauty"] = 0.0
        scores["avg_impressiveness"] = 0.0
    else:
        # Building progress — wealth growth from constructed buildings only
        # Estimate building wealth from player-built structures
        building_values = {
            # Structures (low value each but many)
            "Wall": 15, "Door": 30, "Autodoor": 80,
            # Furniture
            "Bed": 55, "DoubleBed": 90, "RoyalBed": 200,
            "Table1x2c": 50, "Table2x2c": 80, "Table3x3c": 120,
            "DiningChair": 30, "Stool": 15, "Armchair": 80,
            "EndTable": 30, "Dresser": 50, "Shelf": 30,
            # Production — high value
            "Campfire": 20, "FueledStove": 185, "ElectricStove": 250,
            "ButcherSpot": 10, "TableButcher": 120,
            "SimpleResearchBench": 180, "HiTechResearchBench": 400,
            "HandTailoringBench": 80, "ElectricTailoringBench": 200,
            "TableMachining": 250, "FabricationBench": 400,
            "ElectricSmelter": 200, "HiToolBench": 150,
            "NutrientPasteDispenser": 350, "Brewery": 120, "DrugLab": 200,
            # Power/Temp
            "SolarGenerator": 200, "WoodFiredGenerator": 250, "WindTurbine": 300,
            "Battery": 150, "Heater": 80, "Cooler": 100, "PassiveCooler": 30,
            # Misc
            "TorchLamp": 20, "StandingLamp": 40, "HorseshoesPin": 15,
            "ChessTable": 50, "BilliardsTable": 100,
        }
        building_wealth = sum(building_values.get(d, 20) for d in building_defs)
        if building_wealth >= 1500:
            # Open-ended: bonus points for exceeding base threshold
            scores["building_progress"] = 1.0 + (building_wealth - 1500) / 1500
        elif building_wealth >= 800:
            scores["building_progress"] = 0.7
        elif building_wealth >= 300:
            scores["building_progress"] = 0.3
        else:
            scores["building_progress"] = 0.0

        # Average beauty (home area)
        avg_beauty = stats.get("avg_beauty", 0)
        if avg_beauty >= 1.0:
            scores["avg_beauty"] = 1.0
        elif avg_beauty >= 0:
            scores["avg_beauty"] = 0.5
        else:
            scores["avg_beauty"] = max(0, 0.5 + avg_beauty * 0.1)  # negative beauty penalizes

        # Average room impressiveness — exclude utility/storage rooms (role="Room")
        # Only grade rooms with a specific purpose (Bedroom, Barracks, DiningRoom, etc.)
        living_rooms = [rm for rm in player_rooms
                        if rm.get("role", "").lower() not in ("room", "")]
        if living_rooms:
            avg_impress = sum(rm.get("impressiveness", 0) for rm in living_rooms) / len(living_rooms)
        else:
            avg_impress = 0
        if avg_impress >= 40:
            scores["avg_impressiveness"] = 1.0
        elif avg_impress >= 25:
            scores["avg_impressiveness"] = 0.7
        elif avg_impress >= 15:
            scores["avg_impressiveness"] = 0.5
        elif avg_impress >= 5:
            scores["avg_impressiveness"] = 0.3
        else:
            scores["avg_impressiveness"] = 0.0

    weights["building_progress"] = 15
    weights["avg_beauty"] = 8
    weights["avg_impressiveness"] = 20

    # ═══════════════════════════════════════════════════════════════
    # COLONIST WELLBEING (weight: 10) — table stakes
    # ═══════════════════════════════════════════════════════════════

    # Average mood
    moods = [c.get("mood", 0.5) for c in after_colonists if isinstance(c.get("mood"), (int, float))]
    avg_mood = sum(moods) / len(moods) if moods else 0.5
    worst_mood = min(moods) if moods else 0.5
    # Scale: 0.3 = very bad, 0.5 = neutral, 0.7+ = good
    scores["avg_mood"] = min(1.0, max(0, (avg_mood - 0.25) / 0.5))
    weights["avg_mood"] = 3

    # Worst mood (no one should be near breaking)
    scores["worst_mood"] = min(1.0, max(0, (worst_mood - 0.2) / 0.4))
    weights["worst_mood"] = 1

    # Mental breaks
    break_terms = ["mental break", "berserk", "gave up", "hiding in room",
                   "food binge", "sad wander", "tantrum", "daze"]
    mental_breaks = any(any(bt in t for bt in break_terms) for t in thought_labels)
    scores["no_breaks"] = 0.0 if mental_breaks else 1.0
    weights["no_breaks"] = 1

    # Thought-based quality of life (retrospective — captures whole session)
    # Count negative experience thoughts across all colonists
    qol_penalties = {
        "ate without table": 0.15,
        "ugly environment": 0.1,
        "disturbed sleep": 0.1,
        "awful bedroom": 0.15,
        "dull bedroom": 0.05,
        "in the dark": 0.05,
        "soaking wet": 0.05,
        "shared bedroom": 0.05,
    }
    total_qol_penalty = 0
    for term, penalty in qol_penalties.items():
        count = sum(1 for t in thought_labels if term in t)
        total_qol_penalty += min(penalty * count, penalty * 3)  # cap per type
    scores["quality_of_life"] = max(0, 1.0 - total_qol_penalty)
    weights["quality_of_life"] = 5

    # ═══════════════════════════════════════════════════════════════
    # ERROR PENALTY (weight: -20 per error category)
    # Errors detected from overseer report, alerts, or sub-agent failures
    # ═══════════════════════════════════════════════════════════════

    # Unresolved high-priority alerts
    high_alerts = [a for a in alert_labels if any(x in a for x in ["medical", "starvation", "hypothermia", "need tend"])]
    if high_alerts:
        scores["unresolved_alerts"] = 0.0
        weights["unresolved_alerts"] = 2
        # I-002 L3 OBSERVABILITY: Log exactly which alerts caused the penalty
        print(f"  [I-002 DIAG] unresolved_alerts=0 due to: {high_alerts}")
        print(f"  [I-002 DIAG] all alerts: {alert_labels}")
    else:
        scores["unresolved_alerts"] = 1.0
        weights["unresolved_alerts"] = 2

    # ═══════════════════════════════════════════════════════════════
    # EFFICIENCY (weight: 30) — time and progress
    # ═══════════════════════════════════════════════════════════════

    token_usage = load_token_usage("surveys/token_log.jsonl")
    sub_tokens = token_usage["total_input"] + token_usage["total_output"]
    total_tokens = overseer_tokens + sub_tokens
    sub_cost = token_usage["total_cost"]
    token_usage["cost_usd"] = overseer_cost_usd + sub_cost

    # Game progress: did you actually complete 3 in-game days?
    # This is the #1 efficiency metric — if you didn't finish, everything is under-achieved.
    before_weather = before.get("weather", {})
    after_weather = after.get("weather", {})
    before_day = before_weather.get("dayOfYear", 1)
    after_day = after_weather.get("dayOfYear", 1)
    before_hour = before_weather.get("hour", 0)
    after_hour = after_weather.get("hour", 0)
    # Calculate in-game days elapsed (day transitions + fractional hours)
    days_elapsed = (after_day - before_day) + (after_hour - before_hour) / 24.0
    # Score: 3 days = 1.0, 2 days = 0.7, 1 day = 0.3, <1 day = 0.0
    if days_elapsed >= 2.8:
        scores["game_progress"] = 1.0
    elif days_elapsed >= 2.0:
        scores["game_progress"] = 0.7
    elif days_elapsed >= 1.0:
        scores["game_progress"] = 0.3
    else:
        scores["game_progress"] = 0.0
    weights["game_progress"] = 3

    # Time efficiency: punish going over allotted wall time (budget: 15 min ideal, 25 min hard limit)
    if duration_s > 0:
        if duration_s <= 600:        # ≤10 min — fast
            scores["time_efficiency"] = 1.0
        elif duration_s <= 900:      # ≤15 min — on budget
            scores["time_efficiency"] = 0.9
        elif duration_s <= 1200:     # ≤20 min — slightly over
            scores["time_efficiency"] = 0.5
        elif duration_s <= 1500:     # ≤25 min — over budget
            scores["time_efficiency"] = 0.2
        else:                        # >25 min — hard overrun
            scores["time_efficiency"] = 0.0
    else:
        scores["time_efficiency"] = 0.5  # unknown
    weights["time_efficiency"] = 2

    # Token efficiency: scored by cost (USD), not raw tokens
    # Cache reads inflate token count but are ~10% the cost
    # Typical run: $0.50-$2.00 for sonnet
    cost_usd = token_usage.get("cost_usd", 0)
    # If cost is 0 (e.g. timeout killed process), estimate from duration
    # Sonnet ~$1.50 per 25-min run
    if cost_usd == 0 and duration_s > 600:
        cost_usd = duration_s / 1500 * 1.50  # rough estimate
    if cost_usd > 0:
        if cost_usd <= 0.50:
            scores["token_efficiency"] = 1.0
        elif cost_usd <= 1.00:
            scores["token_efficiency"] = 0.8
        elif cost_usd <= 2.00:
            scores["token_efficiency"] = 0.5
        elif cost_usd <= 5.00:
            scores["token_efficiency"] = 0.3
        else:
            scores["token_efficiency"] = 0.1
    elif total_tokens > 0:
        # Fallback to token count if cost not available
        if total_tokens <= 200000:
            scores["token_efficiency"] = 1.0
        elif total_tokens <= 500000:
            scores["token_efficiency"] = 0.8
        elif total_tokens <= 1000000:
            scores["token_efficiency"] = 0.5
        else:
            scores["token_efficiency"] = 0.3
    else:
        scores["token_efficiency"] = 0.5  # unknown
    weights["token_efficiency"] = 3

    # Sub-agent error rate
    sub_errors = token_usage.get("errors", 0)
    sub_dispatches = token_usage.get("dispatches", 1)
    if sub_errors == 0:
        scores["no_sub_errors"] = 1.0
    elif sub_errors <= 1:
        scores["no_sub_errors"] = 0.5
    else:
        scores["no_sub_errors"] = max(0, 1.0 - sub_errors / max(sub_dispatches, 1))
    weights["no_sub_errors"] = 1

    efficiency = {
        "duration_s": duration_s,
        "overseer_tokens": overseer_tokens,
        "sub_agent_tokens": sub_tokens,
        "total_tokens": total_tokens,
        "total_cost_usd": overseer_cost_usd + sub_cost,
        "sub_agent_cost_usd": sub_cost,
        "sub_agent_dispatches": token_usage["dispatches"],
        "sub_agent_errors": sub_errors,
        "by_agent": token_usage.get("by_agent", {}),
    }

    # ═══════════════════════════════════════════════════════════════
    # DIAGNOSTICS — cross-reference priorities vs rubric weights
    # These don't affect scoring but surface misallocations the auditor
    # would otherwise miss.
    # ═══════════════════════════════════════════════════════════════
    diagnostics = []

    # Workforce analysis: flag colonists whose priority=1 job maps to a
    # low-weight metric while high-weight metrics are underperforming
    job_to_metric = {
        "Research": ("research_progress", 4),
        "Hunting": ("food_safety", 4),
        "Cooking": ("self_sufficiency", 3),
        "Construction": ("building_progress", 15),
    }
    high_value_metrics = {k: weights[k] for k in ["building_progress", "production_throughput", "avg_impressiveness"]
                          if k in weights}
    underperforming = {k for k, v in scores.items()
                       if k in high_value_metrics and v < 0.7}

    after_priorities = after.get("work_priorities", {})
    for col in after_priorities.get("colonists", []):
        col_name = col.get("name", "?")
        prios = col.get("priorities", {})
        # Find this colonist's priority=1 job(s)
        top_jobs = [job for job, level in prios.items()
                    if isinstance(level, int) and level == 1]
        for job in top_jobs:
            if job in job_to_metric:
                metric_name, metric_weight = job_to_metric[job]
                # Flag if colonist is dedicated to a low-weight task while
                # high-weight tasks are underperforming
                if metric_weight <= 5 and underperforming:
                    diagnostics.append({
                        "type": "workforce_misallocation",
                        "colonist": col_name,
                        "assigned_job": job,
                        "job_metric_weight": metric_weight,
                        "underperforming_metrics": {m: f"{scores.get(m, 0):.2f} (weight={high_value_metrics[m]})"
                                                    for m in underperforming},
                        "suggestion": f"{col_name} has {job}=1 (drives {metric_name}, worth {metric_weight}pts) "
                                      f"but {', '.join(underperforming)} are below 0.7 and worth more. "
                                      f"Consider reassigning to Construction=1.",
                    })

    # Resource allocation: flag if >50% of a material was spent while
    # building_progress is still low
    if scores.get("building_progress", 1.0) < 0.7:
        before_res = before.get("resources", {})
        after_res = after.get("resources", {})
        for mat in ["Steel", "WoodLog"]:
            b = before_res.get(mat, 0)
            a = after_res.get(mat, 0)
            if b > 0 and a / b < 0.3:
                diagnostics.append({
                    "type": "resource_exhaustion",
                    "material": mat,
                    "before": b,
                    "after": a,
                    "suggestion": f"{mat} dropped from {b} to {a} but building_progress is only "
                                  f"{scores.get('building_progress', 0):.2f}. Material may be wasted on "
                                  f"low-value builds.",
                })

    # ── Gap analysis: rank metrics by points lost, auto-generate hypotheses ──
    points_lost = []
    for k in scores:
        lost = weights[k] * (1.0 - min(scores[k], 1.0))  # cap at 1.0 for open-ended
        if lost >= 1.0:
            points_lost.append((lost, k, scores[k], weights[k]))
    points_lost.sort(reverse=True)

    # For each top loss, explain what colony state could be causing it
    # This works BACKWARD from the loss — no need to pre-enumerate failure modes
    metric_explanations = {
        "building_progress": lambda: _explain_building_progress(building_defs, building_wealth, after),
        "production_throughput": lambda: _explain_production(building_defs, effective_throughput, after),
        "avg_impressiveness": lambda: _explain_impressiveness(player_rooms, after),
        "bedrooms": lambda: _explain_bedrooms(bedroom_rooms, after),
        "storage_room": lambda: _explain_storage(has_storage_room, resources, after),
        "self_sufficiency": lambda: _explain_self_sufficiency(before_survival, after_survival, building_defs, after),
        "research_progress": lambda: f"completed {new_research} projects, current={'active' if current_project else 'NONE'}",
        "shelter": lambda: f"enclosed rooms: {len(enclosed_rooms)}, colonists: {after_count}, sleep problems: {sleep_problems}",
        "food_safety": lambda: f"worst_food_need={worst_food:.2f}, starvation_thoughts={starve_thoughts}",
    }

    if points_lost:
        print("  ── TOP POINT LOSSES (with explanations) ──")
        for lost, metric, score, weight in points_lost[:7]:
            explanation = ""
            if metric in metric_explanations:
                try:
                    explanation = f" — {metric_explanations[metric]()}"
                except Exception:
                    pass
            print(f"  {metric}: {score:.2f} × {weight} = {score*weight:.1f}/{weight} (LOSING {lost:.1f} pts){explanation}")

    # Print diagnostics as warnings so they appear in score output
    if diagnostics:
        print("  ── DIAGNOSTICS ──")
    for d in diagnostics:
        print(f"  [{d['type']}] {d['suggestion']}")

    # Calculate weighted total
    weighted_total = sum(scores[k] * weights[k] for k in scores)
    max_possible = sum(weights.values())

    # Build detailed breakdown
    breakdown = {}
    for k in scores:
        breakdown[k] = {
            "score": round(scores[k], 2),
            "weight": weights[k],
            "weighted": round(scores[k] * weights[k], 1),
            "max": weights[k],
        }
    breakdown["_diagnostics"] = diagnostics

    return round(weighted_total, 1), max_possible, breakdown, efficiency


def load_token_usage(log_path="surveys/token_log.jsonl"):
    """Load and summarize token usage from sub-agent runs."""
    if not os.path.isfile(log_path):
        return {"total_input": 0, "total_output": 0, "total_cost": 0,
                "dispatches": 0, "errors": 0, "by_agent": {}}

    total_input = 0
    total_output = 0
    total_cost = 0.0
    dispatches = 0
    errors = 0
    by_agent = {}

    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            dispatches += 1
            # Include ALL token types: input + output + cache_read + cache_create
            inp = entry.get("input_tokens", 0) + entry.get("cache_read_tokens", 0) + entry.get("cache_create_tokens", 0)
            out = entry.get("output_tokens", 0)
            cost = entry.get("cost_usd", 0)
            total_input += inp
            total_output += out
            total_cost += cost

            if entry.get("exit_code", 0) != 0 or entry.get("is_error", False):
                errors += 1

            agent = entry.get("agent", "unknown")
            if agent not in by_agent:
                by_agent[agent] = {"input": 0, "output": 0, "cost": 0,
                                   "dispatches": 0, "errors": 0}
            by_agent[agent]["input"] += inp
            by_agent[agent]["output"] += out
            by_agent[agent]["cost"] += cost
            by_agent[agent]["dispatches"] += 1
            if entry.get("exit_code", 0) != 0 or entry.get("is_error", False):
                by_agent[agent]["errors"] += 1

    return {
        "total_input": total_input,
        "total_output": total_output,
        "total_cost": round(total_cost, 4),
        "dispatches": dispatches,
        "errors": errors,
        "by_agent": by_agent,
    }


def compare_snapshots(before, after):
    """Produce a human-readable diff of key metrics."""
    lines = []

    bc = len(before.get("colonists", {}).get("colonists", []))
    ac = len(after.get("colonists", {}).get("colonists", []))
    lines.append(f"Colonists: {bc} → {ac}")

    # Mood
    after_colonists = after.get("colonists", {}).get("colonists", [])
    for c in after_colonists:
        mood = c.get("mood", "?")
        if isinstance(mood, float):
            mood = f"{mood:.0%}"
        lines.append(f"  {c.get('name', '?')}: mood={mood}, job={c.get('currentJob', '?')}")

    # Resources
    br = before.get("resources", {})
    ar = after.get("resources", {})
    all_keys = sorted(set(list(br.keys()) + list(ar.keys())))
    changes = []
    for k in all_keys:
        bv = br.get(k, 0)
        av = ar.get(k, 0)
        if isinstance(bv, (int, float)) and isinstance(av, (int, float)) and bv != av:
            changes.append(f"  {k}: {bv} → {av} ({av - bv:+})")
    if changes:
        lines.append("Resources:")
        lines.extend(changes)

    # Zones
    bz = before.get("zones", {}).get("zones", [])
    az = after.get("zones", {}).get("zones", [])
    lines.append(f"Zones: {len(bz)} → {len(az)}")
    az_types = {}
    for z in az:
        t = z.get("type", "?")
        az_types[t] = az_types.get(t, 0) + 1
    if az_types:
        lines.append("  " + ", ".join(f"{t}×{n}" for t, n in sorted(az_types.items())))

    # Colony stats
    before_stats = before.get("colony_stats", {})
    after_stats = after.get("colony_stats", {})
    if isinstance(after_stats, dict) and "wealth_total" in after_stats:
        bw = before_stats.get("wealth_total", 0) if isinstance(before_stats, dict) else 0
        aw = after_stats.get("wealth_total", 0)
        lines.append(f"Wealth: {bw:.0f} → {aw:.0f} ({aw - bw:+.0f})")
        lines.append(f"Beauty (home avg): {after_stats.get('avg_beauty', 0):.2f}")
        lines.append(f"Impressiveness (room avg): {after_stats.get('avg_impressiveness', 0):.1f}")
        lines.append(f"Rooms: {after_stats.get('room_count', 0)}")

    # Blueprints
    abp = after.get("blueprint_count", 0)
    if abp > 0:
        lines.append(f"Blueprints pending: {abp}")

    return "\n".join(lines)

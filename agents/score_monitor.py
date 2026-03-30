#!/usr/bin/env python3
"""Background score monitor — takes periodic snapshots and scores them during a run.

Usage: python3 agents/score_monitor.py <run_dir> [interval_seconds]

Runs until killed. Writes score_timeline.jsonl to the run directory.
Requires AGENT_REPO env var to find the SDK.
"""
import sys, json, time, os

# Resolve agent repo for SDK imports
agent_repo = os.environ.get("AGENT_REPO")
if not agent_repo:
    # Fallback: try sibling directory
    frontier_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for candidate in [os.path.join(frontier_root, '..', 'rimworld-tcp'),
                      os.path.join(frontier_root, '..', 'rimworld-agent')]:
        if os.path.isdir(os.path.join(candidate, 'sdk')):
            agent_repo = os.path.abspath(candidate)
            break
if agent_repo:
    sys.path.insert(0, os.path.join(agent_repo, 'sdk'))
else:
    sys.stderr.write("WARNING: AGENT_REPO not set, SDK imports may fail\n")

run_dir = sys.argv[1]
interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30

# Load before snapshot
before_path = os.path.join(run_dir, 'before.json')
with open(before_path) as f:
    before = json.load(f)

timeline_path = os.path.join(run_dir, 'score_timeline.jsonl')

# P0 fix: truncate stale timeline data to prevent merging with previous captures
# This ensures each monitor session starts clean even if the file already exists
if os.path.exists(timeline_path):
    open(timeline_path, 'w').close()

start_time = time.time()

# Load scheduled spawns from scenario config
scheduled_spawns = []
fired_spawns = set()
scenario_path = os.path.join(run_dir, 'scenario.json')
if os.path.exists(scenario_path):
    try:
        scenario = json.load(open(scenario_path))
        scheduled_spawns = scenario.get('scheduled_spawns', []) or []
    except Exception:
        pass

# Wait a bit for the overseer to start
time.sleep(10)

# Frozen snapshot detection: track last game time to skip duplicates
last_game_day = None
last_game_hour = None
consecutive_frozen = 0
MAX_FROZEN = 2  # Stop recording after 2 identical snapshots (game paused/saved)

# Cooking throughput tracking (state between snapshots)
prev_total_meals = None
prev_game_hour = None

while True:
    elapsed = time.time() - start_time
    try:
        from rimworld import RimClient
        from snapshot import take_snapshot, score_snapshot

        r = RimClient()
        after = take_snapshot(r)
        # NOTE: do NOT close r here — food pipeline diagnostics need it below

        # Fire scheduled spawns based on game hour
        if scheduled_spawns:
            weather = after.get("weather", {})
            day = weather.get("dayOfYear", 0)
            hour = weather.get("hour", 0)
            game_hour = (day - 1) * 24 + hour  # total hours since game start
            for i, spawn in enumerate(scheduled_spawns):
                if i in fired_spawns:
                    continue
                trigger_hour = spawn.get("game_hour", 999)
                if game_hour >= trigger_hour:
                    species = spawn.get("species", "Deer")
                    count = spawn.get("count", 1)
                    manhunter = spawn.get("manhunter", False)
                    try:
                        result = r.spawn_animals(species, count=count, manhunter=manhunter)
                        msg = f"[monitor] SCHEDULED SPAWN: {count}x {species}{' (manhunter)' if manhunter else ''} at game_hour={game_hour:.1f} — {result.get('spawned', 0)} spawned"
                        sys.stderr.write(f"\n{msg}\n")
                        sys.stderr.flush()
                    except Exception as e:
                        msg = f"[monitor] SCHEDULED SPAWN FAILED: {species} — {e}"
                        sys.stderr.write(f"\n{msg}\n")
                    fired_spawns.add(i)

        total, max_pts, breakdown, efficiency = score_snapshot(
            before, after, int(elapsed), 0, 0)

        # Extract key state for the timeline
        weather = after.get("weather", {})

        # Frozen snapshot detection: if game day+hour is identical to last snapshot,
        # the game is paused (overseer saved). Skip recording to avoid inflating
        # food_sustained denominator with duplicate passing snapshots.
        cur_day = weather.get("dayOfYear", 0)
        cur_hour = round(weather.get("hour", 0), 1)
        if cur_day == last_game_day and cur_hour == last_game_hour:
            consecutive_frozen += 1
            if consecutive_frozen >= MAX_FROZEN:
                sys.stderr.write(f"\n[monitor] FROZEN: game paused at day={cur_day} hour={cur_hour} ({consecutive_frozen} dupes) — skipping\n")
                sys.stderr.flush()
                try:
                    r.close()
                except Exception:
                    pass
                time.sleep(interval)
                continue
        else:
            consecutive_frozen = 0
        last_game_day = cur_day
        last_game_hour = cur_hour

        resources = after.get("resources", {})
        colonists = after.get("colonists", {}).get("colonists", [])
        needs = after.get("needs", {})

        # Per-colonist needs bucketed into categories
        colonist_needs = {}
        for name, n in needs.items():
            if isinstance(n, dict):
                short = name.split("'")[1] if "'" in name else name.split()[-1]
                food = n.get("food", -1)
                rest = n.get("rest", -1)
                mood = n.get("mood", -1)
                joy = n.get("joy", -1)
                beauty = n.get("beauty", -1)
                comfort = n.get("comfort", -1)
                # Bucket averages (exclude -1 = unavailable)
                surv_vals = [v for v in [food, rest] if v >= 0]
                happy_vals = [v for v in [mood, joy] if v >= 0]
                env_vals = [v for v in [beauty, comfort] if v >= 0]
                colonist_needs[short] = {
                    "food": round(food, 2),
                    "rest": round(rest, 2),
                    "mood": round(mood, 2),
                    "joy": round(joy, 2),
                    "beauty": round(beauty, 2),
                    "comfort": round(comfort, 2),
                    "survival": round(sum(surv_vals) / len(surv_vals), 2) if surv_vals else -1,
                    "happiness": round(sum(happy_vals) / len(happy_vals), 2) if happy_vals else -1,
                    "environment": round(sum(env_vals) / len(env_vals), 2) if env_vals else -1,
                }

        # Categorize mood debuffs from thoughts into actionable buckets
        # Categories: health, temperature, kitchen, room, social, environment, other
        THOUGHT_CATEGORIES = {
            # Temperature
            "cold": "temperature", "hot": "temperature", "hypotherm": "temperature",
            "heatstroke": "temperature", "slept in the cold": "temperature",
            "slept in the heat": "temperature",
            # Kitchen / Food
            "ate without table": "kitchen", "ate raw": "kitchen",
            "hungry": "kitchen", "malnourish": "kitchen", "starv": "kitchen",
            "raw food": "kitchen", "lavish meal": "kitchen", "fine meal": "kitchen",
            "simple meal": "kitchen", "awful meal": "kitchen",
            "nutrient paste": "kitchen",
            # Room quality
            "awful bedroom": "room", "awful barracks": "room",
            "dull bedroom": "room", "dull barracks": "room",
            "slightly impressive": "room", "impressive": "room",
            "very impressive": "room", "extremely impressive": "room",
            "greedy": "room", "ascetic": "room",
            "shared bedroom": "room", "disturbed sleep": "room",
            "slept outside": "room",
            # Health
            "pain": "health", "wound": "health", "scar": "health",
            "infection": "health", "sick": "health", "disease": "health",
            "injury": "health", "bleeding": "health",
            # Social
            "insulted": "social", "rebuffed": "social", "nuzzled": "social",
            "chatted": "social", "bonded": "social", "lover": "social",
            "friend": "social", "rival": "social", "annoying voice": "social",
            "kind words": "social", "abrasive": "social", "ugly": "social",
            # Environment
            "ugly environment": "environment", "beautiful environment": "environment",
            "soaking wet": "environment", "in the dark": "environment",
            "outdoors": "environment", "cramped": "environment", "spacious": "environment",
            "filthy": "environment",
        }

        def categorize_thought(label: str) -> str:
            label_lower = label.lower()
            for keyword, cat in THOUGHT_CATEGORIES.items():
                if keyword in label_lower:
                    return cat
            return "other"

        mood_debuffs = {}  # {colonist: {category: total_negative_mood}}
        mood_buffs = {}    # {colonist: {category: total_positive_mood}}
        for col_name, thoughts_data in after.get("thoughts", {}).items():
            short = col_name.split("'")[1] if "'" in col_name else col_name.split()[-1]
            items = thoughts_data if isinstance(thoughts_data, list) else thoughts_data.get("thoughts", [])
            debuffs = {}
            buffs = {}
            for t in items:
                if not isinstance(t, dict):
                    continue
                label = t.get("label", "")
                mood_val = t.get("mood", 0)
                if not isinstance(mood_val, (int, float)):
                    continue
                cat = categorize_thought(label)
                if mood_val < 0:
                    debuffs[cat] = round(debuffs.get(cat, 0) + mood_val, 1)
                elif mood_val > 0:
                    buffs[cat] = round(buffs.get(cat, 0) + mood_val, 1)
            mood_debuffs[short] = debuffs
            mood_buffs[short] = buffs

        # Colony-wide mood categories (sum across colonists)
        all_categories = set()
        for d in list(mood_debuffs.values()) + list(mood_buffs.values()):
            all_categories.update(d.keys())
        mood_categories = {}
        for cat in all_categories:
            total_debuff = sum(d.get(cat, 0) for d in mood_debuffs.values())
            total_buff = sum(d.get(cat, 0) for d in mood_buffs.values())
            mood_categories[cat] = round(total_debuff + total_buff, 1)

        # Colony-wide need averages
        all_survival = [cn["survival"] for cn in colonist_needs.values() if cn["survival"] >= 0]
        all_happiness = [cn["happiness"] for cn in colonist_needs.values() if cn["happiness"] >= 0]
        all_environment = [cn["environment"] for cn in colonist_needs.values() if cn["environment"] >= 0]
        need_buckets = {
            "survival": round(sum(all_survival) / len(all_survival), 2) if all_survival else -1,
            "happiness": round(sum(all_happiness) / len(all_happiness), 2) if all_happiness else -1,
            "environment": round(sum(all_environment) / len(all_environment), 2) if all_environment else -1,
        }

        # Track colonist jobs/tasks + combat detection
        colonist_jobs = {}
        combat_fleeing = []
        combat_downed = []
        for c in colonists:
            name = c.get("name", "")
            short = name.split("'")[1] if "'" in name else name.split()[-1]
            job = c.get("currentJob", "Idle")
            target = c.get("jobTarget", "")
            colonist_jobs[short] = f"{job}:{target}" if target else job
            if job == "FleeAndCower":
                combat_fleeing.append(short)
            elif job == "Wait_Downed":
                combat_downed.append(short)
        combat_active = len(combat_fleeing) > 0 or len(combat_downed) > 0

        # Room details
        rooms_data = after.get("colony_stats", {}).get("rooms", [])
        if not rooms_data:
            rooms_data = after.get("buildings", {}).get("rooms", [])
        room_summary = []
        for rm in rooms_data:
            if isinstance(rm, dict) and rm.get("role") and rm.get("role") != "None":
                cells = rm.get("cells", rm.get("cellCount", 0))
                if cells < 100:  # skip ancient ruins
                    room_entry = {
                        "role": rm.get("role"),
                        "impressiveness": round(rm.get("impressiveness", 0), 1),
                        "beauty": round(rm.get("beauty", 0), 2),
                        "cleanliness": round(rm.get("cleanliness", 0), 2),
                        "roofed": rm.get("roofed", None),
                        "cells": cells,
                    }
                    room_summary.append(room_entry)

        # Building defs for tracking what's been constructed
        building_list = after.get("buildings", {}).get("buildings", [])
        building_defs = [b.get("def", "") for b in building_list if isinstance(b, dict)]

        # Zones
        zones = after.get("zones", {}).get("zones", [])
        zone_summary = {}
        for z in zones:
            t = z.get("type", "?")
            zone_summary[t] = zone_summary.get(t, 0) + 1

        # Alerts
        alerts = after.get("alerts", [])
        alert_labels = []
        if isinstance(alerts, list):
            alert_labels = [str(a.get("label", a) if isinstance(a, dict) else a) for a in alerts]
        elif isinstance(alerts, dict):
            alert_labels = [str(a) for a in alerts.get("alerts", [])]

        # Blueprint/frame count
        bp_count = after.get("blueprint_count", 0)

        # Wild animal tracking — food competition signal
        wild_animal_count = 0
        hunt_designated_count = 0
        try:
            animals_data = r.send("read_animals")  # bypass cache for fresh data
            if isinstance(animals_data, dict):
                all_animals = animals_data.get("animals", [])
                wild_animal_count = sum(1 for a in all_animals
                                        if isinstance(a, dict) and not a.get("tame", False))
                hunt_designated_count = animals_data.get("hunt_designated_count", 0)
            elif isinstance(animals_data, list):
                wild_animal_count = len(animals_data)
        except Exception as e:
            wild_animal_count = -1
            sys.stderr.write(f"[monitor] animals error: {e}\n")

        # Food pipeline diagnostics
        food_pipeline = {}
        has_cooking_station = any(d in building_defs for d in ("FueledStove", "Campfire", "ElectricStove"))
        has_bills = False
        try:
            if has_cooking_station:
                bill_data = r.send("read_bills")  # bypass cache
                # C# returns {"workbenches": [{def, bills: [{recipe, ...}]}]}
                workbenches = bill_data.get("workbenches", []) if isinstance(bill_data, dict) else []
                for wb in workbenches:
                    if not isinstance(wb, dict):
                        continue
                    for b in wb.get("bills", []):
                        if isinstance(b, dict) and "cook" in b.get("recipe", "").lower():
                            has_bills = True
                            break
                    if has_bills:
                        break
        except Exception:
            pass
        # Count stockpiled + ground items
        ground = resources.get("_ground", {})
        if not isinstance(ground, dict): ground = {}
        def total_count(defName):
            return (resources.get(defName, 0) if isinstance(resources.get(defName), (int, float)) else 0) + ground.get(defName, 0)
        total_raw_food = sum(total_count(k) for k in set(list(resources.keys()) + list(ground.keys()))
                            if k.startswith("Meat_") or k in ("RawBerries", "RawRice", "RawCorn", "RawPotatoes", "RawFungus"))
        total_meals = total_count("MealSimple") + total_count("MealFine") + total_count("MealLavish")
        cookable_meals = total_raw_food // 10  # ~10 raw food units ≈ 0.5 nutrition = 1 simple meal
        sub_cookable = total_raw_food > 0 and total_raw_food < 10
        food_pipeline = {
            "has_cooking_station": has_cooking_station,
            "has_bills": has_bills,
            "raw_food": total_raw_food,
            "meals": total_meals,
            "cookable_meals": cookable_meals,
            "sub_cookable": sub_cookable,
            "wild_animals": wild_animal_count,
            "food_in_stockpile": total_raw_food + total_meals,
        }

        # Cooking throughput tracking
        cooking = {}
        cur_game_hour = after.get("weather", {}).get("hour", 0) if isinstance(after, dict) else 0
        meals_delta = 0
        if prev_total_meals is not None:
            meals_delta = max(0, total_meals - prev_total_meals)
        hours_delta = 0
        if prev_game_hour is not None and cur_game_hour > prev_game_hour:
            hours_delta = cur_game_hour - prev_game_hour
        meals_per_hour = round(meals_delta / hours_delta, 2) if hours_delta > 0.1 else 0

        # Detect cook identity and idle reason
        cook_name = None
        cook_job = "unknown"
        cook_idle_reason = None
        for c_name, c_jobs in colonist_jobs.items():
            # Find colonist with Cooking=1 priority
            wp_data = after.get("work_priorities", {})
            if isinstance(wp_data, dict):
                prios = wp_data.get(c_name, {})
                if isinstance(prios, dict) and prios.get("Cooking", 0) == 1:
                    cook_name = c_name
                    cook_job = c_jobs
                    break
        if cook_name and cook_job:
            job_str = str(cook_job).lower()
            if "dobill" in job_str or "cook" in job_str:
                cook_idle_reason = None  # actively cooking
            elif "idle" in job_str or "wait" in job_str or "wander" in job_str:
                if not has_bills:
                    cook_idle_reason = "no_bills"
                elif total_raw_food == 0:
                    cook_idle_reason = "no_ingredients"
                else:
                    cook_idle_reason = "idle"
            else:
                cook_idle_reason = "other_work"

        cooking = {
            "meals_delta": meals_delta,
            "meals_per_hour": meals_per_hour,
            "cook_name": cook_name,
            "cook_job": cook_job if cook_name else None,
            "cook_idle_reason": cook_idle_reason,
        }
        prev_total_meals = total_meals
        prev_game_hour = cur_game_hour

        # Wealth tracking
        colony_stats = after.get("colony_stats", {})
        wealth = {
            "total": round(colony_stats.get("wealth_total", 0), 0),
            "buildings": round(colony_stats.get("wealth_buildings", 0), 0),
            "items": round(colony_stats.get("wealth_items", 0), 0),
        }

        # Core fields (always included — small, critical for auditor grep)
        entry = {
            "elapsed_s": int(elapsed),
            "pct": round(total / max_pts * 100, 1),
            "day": weather.get("dayOfYear", 0),
            "hour": round(weather.get("hour", 0), 1),
            "colonists_alive": len(colonists),
            "mood_avg": round(sum(c.get("mood", 0) for c in colonists) / max(len(colonists), 1), 2),
            "meals": resources.get("MealSimple", 0) + resources.get("MealFine", 0),
            "packs": resources.get("MealSurvivalPack", 0),
            "wood": resources.get("WoodLog", 0),
            "steel": resources.get("Steel", 0),
            "buildings": len(building_list),
            "blueprints_pending": bp_count,
            "wild_animals": wild_animal_count,
            "hunt_designated": hunt_designated_count,
            "jobs": colonist_jobs,
            "food_pipeline": food_pipeline,
            "cooking": cooking,
            "combat": {"active": combat_active, "fleeing": combat_fleeing, "downed": combat_downed},
            "alerts": alert_labels,
        }
        # Heavy fields — only include when changed from last snapshot
        heavy_fields = {
            "resources": {k: v for k, v in resources.items() if isinstance(v, (int, float))},
            "colonist_needs": colonist_needs,
            "need_buckets": need_buckets,
            "building_defs": building_defs,
            "rooms": room_summary,
            "zones": zone_summary,
            "mood_debuffs": mood_debuffs,
            "mood_buffs": mood_buffs,
            "mood_categories": mood_categories,
            "wealth": wealth,
            "breakdown": {k: round(v["score"], 2) for k, v in breakdown.items()
                          if not k.startswith("_")},
        }
        if not hasattr(sys.modules[__name__], '_prev_heavy'):
            sys.modules[__name__]._prev_heavy = {}
        prev_heavy = sys.modules[__name__]._prev_heavy
        for k, v in heavy_fields.items():
            if str(v) != str(prev_heavy.get(k)):
                entry[k] = v
                prev_heavy[k] = v

        # Telemetry health check — flag broken fields LOUDLY + log to file
        broken = []
        warnings = []
        if entry.get("wild_animals", -1) == -1:
            broken.append("wild_animals=-1")
        fp = entry.get("food_pipeline", {})
        if fp.get("has_cooking_station") and not fp.get("has_bills") and fp.get("raw_food", 0) > 0:
            # Not necessarily broken — bills may not have been added yet (campfire still building)
            # Only flag as BROKEN after 120s (enough time for campfire to complete + bills to be added)
            if elapsed > 120:
                broken.append(f"bills=False despite station+raw_food={fp['raw_food']} after {int(elapsed)}s")
            else:
                warnings.append(f"bills=False (station+raw_food={fp['raw_food']}, may still be setting up)")
        if broken:
            msg = f"[{int(elapsed)}s] TELEMETRY BROKEN: {', '.join(broken)}"
            sys.stderr.write(f"\n[monitor] {msg}\n")
            sys.stderr.flush()
            error_log = os.path.join(run_dir, 'telemetry_errors.log')
            with open(error_log, 'a') as ef:
                ef.write(msg + '\n')
        if warnings:
            msg = f"[{int(elapsed)}s] TELEMETRY NOTE: {', '.join(warnings)}"
            sys.stderr.write(f"\n[monitor] {msg}\n")
            sys.stderr.flush()

        with open(timeline_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        r.close()

        monitor_msg = f"[monitor] {int(elapsed)}s | Day {entry['day']} H{entry['hour']} | {entry['pct']}% | meals={entry['meals']} packs={entry['packs']} wood={entry['wood']} wild={entry.get('wild_animals', -1)}"
        sys.stdout.write(f"\r{monitor_msg}")
        sys.stdout.flush()

        # Write to live log for listener
        live_log = os.path.join(os.path.dirname(run_dir), '..', 'logs', 'agent_live.jsonl')
        try:
            with open(live_log, 'a') as lf:
                lf.write(monitor_msg + '\n')
        except Exception:
            pass

    except Exception as e:
        # Game might be loading, overseer mid-command, or connection refused
        try:
            r.close()
        except Exception:
            pass

    time.sleep(interval)

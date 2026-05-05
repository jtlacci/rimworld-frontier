#!/usr/bin/env python3
"""Analyze score_timeline.jsonl for a finished run and write timeline_analysis.json.

Used by runner_finish.sh. Prints the human-readable analysis to stdout/stderr;
writes the structured analysis to <result_dir>/timeline_analysis.json.
"""
import sys, json, os
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: _analyze_timeline.py <result_dir>", file=sys.stderr)
    sys.exit(1)

result_dir = sys.argv[1]
timeline_path = os.path.join(result_dir, "score_timeline.jsonl")

if not os.path.isfile(timeline_path):
    print("  No timeline data (monitor may not have started)")
    sys.exit(0)

entries = []
with open(timeline_path) as f:
    for line in f:
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass

if not entries:
    print("  Timeline empty")
    sys.exit(0)

print(f"  Timeline: {len(entries)} snapshots over {entries[-1]['elapsed_s']}s")

# ── Progression table ──
print()
print(f"  {'Time':>6s}  {'Day':>5s}  {'Score':>6s}  {'Meals':>5s}  {'Packs':>5s}  {'Wood':>6s}  {'Bldgs':>5s}  {'BPs':>4s}  {'Rooms'}")
print(f"  {'─'*6}  {'─'*5}  {'─'*6}  {'─'*5}  {'─'*5}  {'─'*6}  {'─'*5}  {'─'*4}  {'─'*20}")
for e in entries:
    day_str = f"{e['day']}.{int(e.get('hour',0)):02d}"
    rooms_str = ", ".join(
        f"{r['role']}({r['impressiveness']})"
        for r in e.get("rooms", [])
    ) if isinstance(e.get("rooms"), list) else str(e.get("rooms", 0))
    bp = e.get("blueprints_pending", "?")
    print(f"  {e['elapsed_s']:>5d}s  {day_str:>5s}  {e['pct']:>5.1f}%  {e['meals']:>5d}  {e['packs']:>5d}  {e['wood']:>6d}  {e['buildings']:>5d}  {bp:>4}  {rooms_str}")

# ── Need buckets ──
print()
has_needs = any(e.get("need_buckets") for e in entries)
if has_needs:
    print(f"  {'Time':>6s}  {'Day':>5s}  {'Survival':>8s}  {'Happiness':>9s}  {'Environ':>8s}  Per-colonist details")
    print(f"  {'─'*6}  {'─'*5}  {'─'*8}  {'─'*9}  {'─'*8}  {'─'*40}")
    for e in entries:
        nb = e.get("need_buckets", {})
        day_str = f"{e['day']}.{int(e.get('hour',0)):02d}"
        s = nb.get("survival", -1)
        h = nb.get("happiness", -1)
        ev = nb.get("environment", -1)
        s_str = f"{s:.2f}" if s >= 0 else "  n/a"
        h_str = f"{h:.2f}" if h >= 0 else "  n/a"
        ev_str = f"{ev:.2f}" if ev >= 0 else "  n/a"
        cn = e.get("colonist_needs", {})
        per_col = []
        for name, nd in cn.items():
            cs = nd.get("survival", -1)
            ch = nd.get("happiness", -1)
            ce = nd.get("environment", -1)
            per_col.append(f"{name}({cs:.1f}/{ch:.1f}/{ce:.1f})")
        print(f"  {e['elapsed_s']:>5d}s  {day_str:>5s}  {s_str:>8s}  {h_str:>9s}  {ev_str:>8s}  {' '.join(per_col)}")

# ── Job distribution ──
print()
job_counts = {}
total_snapshots = len(entries)
for e in entries:
    for col, job in e.get("jobs", {}).items():
        if col not in job_counts:
            job_counts[col] = {}
        job_counts[col][job] = job_counts[col].get(job, 0) + 1
if job_counts:
    print("  ── JOB DISTRIBUTION (% of snapshots) ──")
    for col in sorted(job_counts.keys()):
        jobs = job_counts[col]
        sorted_jobs = sorted(jobs.items(), key=lambda x: -x[1])
        parts = [f"{job} {count*100//total_snapshots}%" for job, count in sorted_jobs if count*100//total_snapshots >= 5]
        print(f"  {col:>12s}: {', '.join(parts)}")

# ── Issue detection ──
print()
issues = []

max_meals = max(e.get("meals", 0) for e in entries)
if max_meals == 0:
    issues.append("COOKING BROKEN: meals never rose above 0 — bills not firing or no fuel")

if len(entries) >= 2:
    first_packs = entries[0].get("packs", 0)
    last_packs = entries[-1].get("packs", 0)
    if first_packs > 0 and last_packs < first_packs * 0.5:
        issues.append(f"PACK BURN: survival packs {first_packs} -> {last_packs} (>{50}% consumed)")

if len(entries) >= 3:
    first_day = entries[0].get("day", 0) + entries[0].get("hour", 0) / 24
    last_day = entries[-1].get("day", 0) + entries[-1].get("hour", 0) / 24
    elapsed = entries[-1]["elapsed_s"] - entries[0]["elapsed_s"]
    if elapsed > 120 and (last_day - first_day) < 0.5:
        issues.append(f"GAME STALLED: only {last_day - first_day:.1f} days in {elapsed}s — speed 4 not working or game paused")

bp_entries = [e for e in entries if e.get("blueprints_pending", 0) > 0]
if len(bp_entries) >= 3:
    stuck_bps = [e for e in bp_entries[-3:] if e.get("blueprints_pending", 0) > 10]
    if len(stuck_bps) == 3:
        issues.append(f"CONSTRUCTION STALLED: {stuck_bps[-1]['blueprints_pending']} blueprints stuck for 3+ snapshots")

if len(entries) >= 4:
    last_scores = [e["pct"] for e in entries[-4:]]
    if max(last_scores) - min(last_scores) < 1.0:
        issues.append(f"SCORE PLATEAU: stuck at {last_scores[-1]:.1f}% for last {len(last_scores)} snapshots")

for e in entries:
    for rm in e.get("rooms", []):
        if isinstance(rm, dict) and rm.get("impressiveness", 0) < 0:
            issues.append(f"BAD ROOM: {rm['role']} at impressiveness {rm['impressiveness']} @ {e['elapsed_s']}s")
            break
    if issues and "BAD ROOM" in issues[-1]:
        break

all_colonists = set().union(*(e.get("colonist_needs", {}).keys() for e in entries))
for col_name in all_colonists:
    col_entries = [(e["elapsed_s"], e.get("colonist_needs", {}).get(col_name, {})) for e in entries
                   if col_name in e.get("colonist_needs", {})]
    if not col_entries:
        continue
    for bucket, warn_thresh, crit_thresh, label in [
        ("survival",    0.40, 0.20, "SURVIVAL"),
        ("happiness",   0.35, 0.20, "HAPPINESS"),
        ("environment", 0.30, 0.15, "ENVIRONMENT"),
        ("food",        0.35, 0.15, "FOOD"),
        ("rest",        0.30, 0.15, "REST"),
        ("joy",         0.30, 0.10, "JOY"),
    ]:
        vals = [(t, nd.get(bucket, -1)) for t, nd in col_entries if nd.get(bucket, -1) >= 0]
        if not vals:
            continue
        crit_snaps = [(t, v) for t, v in vals if v < crit_thresh]
        warn_snaps = [(t, v) for t, v in vals if v < warn_thresh]
        if crit_snaps:
            worst_t, worst_v = min(crit_snaps, key=lambda x: x[1])
            issues.append(f"NEED CRITICAL — {col_name} {label}={worst_v:.2f} @ {worst_t}s ({len(crit_snaps)}/{len(vals)} snapshots below {crit_thresh})")
        elif len(warn_snaps) >= 2:
            worst_t, worst_v = min(warn_snaps, key=lambda x: x[1])
            issues.append(f"NEED WARNING — {col_name} {label}={worst_v:.2f} @ {worst_t}s ({len(warn_snaps)}/{len(vals)} snapshots below {warn_thresh})")
    for need_key in ["food", "rest", "mood", "joy"]:
        first_val = col_entries[0][1].get(need_key, -1)
        last_val = col_entries[-1][1].get(need_key, -1)
        if first_val >= 0 and last_val >= 0 and (first_val - last_val) > 0.30:
            issues.append(f"NEED DECLINING — {col_name} {need_key} dropped {first_val:.2f} -> {last_val:.2f}")

for col, jobs in job_counts.items():
    idle_pct = jobs.get("idle", 0) * 100 // total_snapshots if total_snapshots else 0
    wait_pct = jobs.get("Wait_Combat", 0) * 100 // total_snapshots if total_snapshots else 0
    if idle_pct + wait_pct >= 40:
        issues.append(f"IDLE COLONIST: {col} idle/waiting {idle_pct + wait_pct}% of snapshots")

# Food pipeline diagnostics
meal_history = [e.get("meals", 0) for e in entries]
peak_meals = max(meal_history)
final_meals = meal_history[-1] if meal_history else 0
if peak_meals > 0 and final_meals == 0:
    wild_animals = [e.get("wild_animals", e.get("food_pipeline", {}).get("wild_animals", -1)) for e in entries]
    avg_wild = sum(w for w in wild_animals if w > 0) / max(1, sum(1 for w in wild_animals if w > 0))
    if avg_wild > 5:
        issues.append(f"FOOD THEFT: meals peaked at {peak_meals} but ended at 0 with ~{avg_wild:.0f} wild animals on map — animals likely eating from open stockpile. Fix: store food indoors or hunt animals first")
    else:
        issues.append(f"FOOD CONSUMED: meals peaked at {peak_meals} but ended at 0 — production rate too low for consumption")

has_food_pipeline = any(e.get("food_pipeline") for e in entries)
if has_food_pipeline:
    for e in entries[-3:]:
        fp = e.get("food_pipeline", {})
        wild = fp.get("wild_animals", 0)
        food_in_stockpile = fp.get("food_in_stockpile", 0)
        food_rooms = [r for r in e.get("rooms", [])
                      if isinstance(r, dict) and r.get("role", "").lower() in ("room", "storage", "stockpile")]
        food_indoors = len(food_rooms) > 0
        if wild > 8 and food_in_stockpile > 0 and not food_indoors:
            issues.append(f"FOOD EXPOSED: {wild} wild animals on map, {food_in_stockpile} food items in open stockpile — animals will eat it. Fix: build enclosed storage room")
            break

if has_food_pipeline:
    recent = entries[-3:] if len(entries) >= 3 else entries
    for e in recent:
        fp = e.get("food_pipeline", {})
        if fp.get("raw_food", 0) > 5 and fp.get("meals", 0) == 0 and fp.get("has_cooking_station", False):
            if not fp.get("has_bills", False):
                issues.append(f"BILLS MISSING: {fp['raw_food']} raw food available + cooking station exists but no bills active @ {e['elapsed_s']}s")
            else:
                issues.append(f"COOK IDLE: {fp['raw_food']} raw food + bills active but 0 meals @ {e['elapsed_s']}s — cook priority too low or pathing issue")
            break

if has_food_pipeline:
    late_entries = entries[len(entries)//2:]
    for e in late_entries:
        fp = e.get("food_pipeline", {})
        if fp.get("raw_food", 0) > 3 and not fp.get("has_cooking_station", False):
            issues.append(f"NO KITCHEN: {fp['raw_food']} raw food available but no cooking station built by {e['elapsed_s']}s — build campfire/stove earlier")
            break

wild_counts = [e.get("wild_animals", e.get("food_pipeline", {}).get("wild_animals", -1)) for e in entries]
valid_wild = [(i, w) for i, w in enumerate(wild_counts) if w >= 0]
if len(valid_wild) >= 3:
    first_wild = valid_wild[0][1]
    last_wild = valid_wild[-1][1]
    if first_wild > 10 and last_wild > first_wild * 0.8:
        issues.append(f"WILDLIFE NOT HUNTED: {first_wild} → {last_wild} wild animals — hunting should reduce food competition and produce meat")

if issues:
    print("  ── TIMELINE ISSUES ──")
    for issue in issues:
        print(f"    {issue}")
else:
    print("  No timeline issues detected")

# Score timeline metrics
sdk_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sdk')
sys.path.insert(0, sdk_path)
try:
    from timeline_scoring import score_timeline as _tl_score
    tl_scores, tl_weights = _tl_score(entries)
except Exception:
    tl_scores, tl_weights = {}, {}
if tl_scores:
    print()
    print("  ── TIMELINE SCORES ──")
    for metric in sorted(tl_scores):
        s = tl_scores[metric]
        w = tl_weights[metric]
        print(f"    {metric}: {s:.2f} (weight {w}, weighted {s*w:.1f})")

# Telemetry health check
telemetry_broken = []
wild_vals = [e.get("wild_animals", e.get("food_pipeline", {}).get("wild_animals", -1)) for e in entries]
if all(w == -1 for w in wild_vals):
    telemetry_broken.append("wild_animals=-1 for ALL snapshots (r.send('read_animals') failing)")
bill_vals = [e.get("food_pipeline", {}).get("has_bills", None) for e in entries]
cooking_vals = [e.get("food_pipeline", {}).get("has_cooking_station", False) for e in entries]
if any(cooking_vals) and not any(bill_vals):
    telemetry_broken.append("bills=False for ALL snapshots despite cooking station present (r.send('read_bills') failing)")
if telemetry_broken:
    print()
    print("  ── TELEMETRY BROKEN (instrumentation bug, not game issue) ──")
    error_log = os.path.join(result_dir, 'telemetry_errors.log')
    with open(error_log, 'a') as ef:
        ef.write(f"[post-run] {len(entries)} snapshots analyzed\n")
        for tb in telemetry_broken:
            print(f"    BUG: {tb}")
            ef.write(f"[post-run] {tb}\n")
    print("    FIX THESE BEFORE DIAGNOSING GAME ISSUES — data is unreliable")
    print(f"    Error log: {error_log}")

analysis = {
    "snapshots": len(entries),
    "duration_s": entries[-1]["elapsed_s"],
    "max_meals": max_meals,
    "final_score_pct": entries[-1]["pct"],
    "game_days": entries[-1].get("day", 0) + entries[-1].get("hour", 0) / 24,
    "issues": issues,
    "job_distribution": {col: {j: round(c / total_snapshots, 2) for j, c in jobs.items()}
                         for col, jobs in job_counts.items()},
    "need_trajectory": [e.get("need_buckets", {}) for e in entries],
    "timeline_scores": tl_scores,
    "timeline_weights": tl_weights,
}
with open(os.path.join(result_dir, "timeline_analysis.json"), "w") as f:
    json.dump(analysis, f, indent=2)

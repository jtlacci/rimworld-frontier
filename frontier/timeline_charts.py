"""Generate timeline charts from score_timeline.jsonl data."""

from __future__ import annotations

import json
import os
from collections import defaultdict


def generate_charts(result_dir: str) -> list[str]:
    """Generate PNG charts from timeline data. Returns list of saved file paths."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not available — skipping charts")
        return []

    timeline_path = os.path.join(result_dir, "score_timeline.jsonl")
    if not os.path.isfile(timeline_path):
        return []

    entries = []
    with open(timeline_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if len(entries) < 2:
        return []

    saved = []
    elapsed = [e["elapsed_s"] for e in entries]
    colonist_colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f39c12", "#1abc9c"]

    all_colonists = set()
    for e in entries:
        all_colonists.update(e.get("colonist_needs", {}).keys())
    sorted_colonists = sorted(all_colonists)

    # ── Chart 1: Score % over time ──
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(elapsed, [e["pct"] for e in entries], "b-o", linewidth=2, markersize=4)
    ax.set_xlabel("Elapsed (s)")
    ax.set_ylabel("Score %")
    ax.set_title("Colony Score Over Time")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    path = os.path.join(result_dir, "chart_score.png")
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)
    saved.append(path)

    # ── Chart 2: Resources by RimWorld category ──
    RESOURCE_CATEGORIES = {
        "Food": {
            "items": ["MealSimple", "MealFine", "MealLavish", "MealSurvivalPack",
                      "Pemmican", "Kibble", "RawBerries", "Meat",
                      "RawPotatoes", "RawCorn", "RawRice", "RawFungus",
                      "InsectJelly", "Milk", "Egg"],
            "color": "#27ae60", "prefix_match": ["Meat_", "Egg_"],
        },
        "Materials": {
            "items": ["WoodLog", "Steel", "Plasteel", "Jade", "Gold", "Uranium",
                      "ComponentIndustrial", "ComponentSpacer", "Chemfuel"],
            "color": "#e67e22", "prefix_match": ["Blocks"],
        },
        "Textiles": {
            "items": ["Cloth", "DevilstrandCloth", "Synthread", "Hyperweave"],
            "color": "#3498db", "prefix_match": ["Leather_"],
        },
        "Medicine": {
            "items": ["MedicineHerbal", "MedicineIndustrial", "MedicineUltratech",
                      "Penoxycyline", "Luciferium"],
            "color": "#e74c3c", "prefix_match": [],
        },
        "Silver": {
            "items": ["Silver"],
            "color": "#95a5a6", "prefix_match": [],
        },
    }

    def categorize_resource(def_name):
        for cat, info in RESOURCE_CATEGORIES.items():
            if def_name in info["items"]:
                return cat
            for prefix in info.get("prefix_match", []):
                if def_name.startswith(prefix):
                    return cat
        return None  # skip uncategorized

    has_full_resources = any(e.get("resources") for e in entries)
    if has_full_resources:
        # Break down food into individual lines for observability
        FOOD_LINES = {
            "Meals": {"items": ["MealSimple", "MealFine", "MealLavish"], "color": "#27ae60", "prefix_match": []},
            "Survival Packs": {"items": ["MealSurvivalPack"], "color": "#e74c3c", "prefix_match": []},
            "Raw Meat": {"items": ["Meat"], "color": "#c0392b", "prefix_match": ["Meat_"]},
            "Raw Plants": {"items": ["RawBerries", "RawRice", "RawCorn", "RawPotatoes", "RawFungus"],
                           "color": "#f39c12", "prefix_match": []},
            "Other Food": {"items": ["Pemmican", "Kibble", "InsectJelly", "Milk", "Egg"],
                           "color": "#95a5a6", "prefix_match": ["Egg_"]},
        }

        # Chart 2a: Food breakdown (own chart — most actionable resource)
        food_totals = {name: [] for name in FOOD_LINES}
        for e in entries:
            res = e.get("resources", {})
            for name in FOOD_LINES:
                food_totals[name].append(0)
            for def_name, count in res.items():
                for name, info in FOOD_LINES.items():
                    if def_name in info["items"]:
                        food_totals[name][-1] += count
                        break
                    if any(def_name.startswith(p) for p in info.get("prefix_match", [])):
                        food_totals[name][-1] += count
                        break

        fig, ax = plt.subplots(figsize=(10, 5))
        for name, info in FOOD_LINES.items():
            vals = food_totals[name]
            if any(v > 0 for v in vals):
                ax.plot(elapsed, vals, "-o", color=info["color"],
                        label=name, markersize=4, linewidth=2)
        ax.set_xlabel("Elapsed (s)")
        ax.set_ylabel("Count")
        ax.set_title("Food Supply Over Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        path = os.path.join(result_dir, "chart_food.png")
        fig.tight_layout()
        fig.savefig(path, dpi=100)
        plt.close(fig)
        saved.append(path)

        # Chart 2b: Materials (non-food resources)
        MATERIAL_CATS = {k: v for k, v in RESOURCE_CATEGORIES.items() if k != "Food"}
        cat_totals = {cat: [] for cat in MATERIAL_CATS}
        for e in entries:
            res = e.get("resources", {})
            for cat in MATERIAL_CATS:
                cat_totals[cat].append(0)
            for def_name, count in res.items():
                cat = categorize_resource(def_name)
                if cat and cat != "Food":
                    cat_totals[cat][-1] += count

        fig, ax = plt.subplots(figsize=(10, 5))
        for cat, info in MATERIAL_CATS.items():
            vals = cat_totals[cat]
            if any(v > 0 for v in vals):
                ax.plot(elapsed, vals, "-o", color=info["color"],
                        label=cat, markersize=4, linewidth=2)
        ax.set_xlabel("Elapsed (s)")
        ax.set_ylabel("Count")
        ax.set_title("Materials & Resources Over Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        path = os.path.join(result_dir, "chart_resources.png")
        fig.tight_layout()
        fig.savefig(path, dpi=100)
        plt.close(fig)
        saved.append(path)
    else:
        # Fallback: old-style individual resource lines
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(elapsed, [e.get("meals", 0) for e in entries], "g-o", label="Meals", markersize=4)
        ax.plot(elapsed, [e.get("packs", 0) for e in entries], "r-s", label="Survival Packs", markersize=4)
        ax.plot(elapsed, [e.get("wood", 0) / 100 for e in entries], "brown", linestyle="-", marker="^",
                label="Wood (÷100)", markersize=4)
        ax.set_xlabel("Elapsed (s)")
        ax.set_ylabel("Count")
        ax.set_title("Resources Over Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        path = os.path.join(result_dir, "chart_resources.png")
        fig.tight_layout()
        fig.savefig(path, dpi=100)
        plt.close(fig)
        saved.append(path)

    # ── Chart 3: Buildings & Blueprints ──
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(elapsed, [e.get("buildings", 0) for e in entries], "b-o", label="Buildings", markersize=4)
    ax.plot(elapsed, [e.get("blueprints_pending", 0) for e in entries], "r--s",
            label="Blueprints Pending", markersize=4)
    ax.set_xlabel("Elapsed (s)")
    ax.set_ylabel("Count")
    ax.set_title("Construction Progress")
    ax.legend()
    ax.grid(True, alpha=0.3)
    path = os.path.join(result_dir, "chart_construction.png")
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)
    saved.append(path)

    # ── Chart 4: Mood debuffs by category (actionable) ──
    # If we have mood_categories data, chart that; otherwise fall back to raw needs
    has_mood_cats = any(e.get("mood_categories") for e in entries)
    if has_mood_cats:
        category_order = ["temperature", "kitchen", "room", "health", "social", "environment", "other"]
        cat_colors = {
            "temperature": "#e74c3c",
            "kitchen": "#f39c12",
            "room": "#9b59b6",
            "health": "#e67e22",
            "social": "#3498db",
            "environment": "#27ae60",
            "other": "#95a5a6",
        }

        # Chart 4a: Colony-wide mood impact by category over time (stacked bar)
        fig, ax = plt.subplots(figsize=(12, 5))
        # For each category, plot the colony-wide total over time
        for cat in category_order:
            vals = [e.get("mood_categories", {}).get(cat, 0) for e in entries]
            if any(v != 0 for v in vals):
                ax.plot(elapsed, vals, "-o", color=cat_colors.get(cat, "#95a5a6"),
                        label=cat.capitalize(), markersize=4, linewidth=2)
        ax.axhline(y=0, color="black", linewidth=0.5)
        ax.set_xlabel("Elapsed (s)")
        ax.set_ylabel("Net Mood Impact")
        ax.set_title("Mood Impact by Category (colony total)")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        path = os.path.join(result_dir, "chart_mood_categories.png")
        fig.tight_layout()
        fig.savefig(path, dpi=100)
        plt.close(fig)
        saved.append(path)

        # Chart 4b: Per-colonist debuff breakdown (stacked horizontal bar, final snapshot)
        last = entries[-1]
        debuffs = last.get("mood_debuffs", {})
        buffs = last.get("mood_buffs", {})
        if debuffs:
            fig, ax = plt.subplots(figsize=(12, max(3, len(debuffs) * 1.2)))
            col_names = sorted(debuffs.keys())
            y_pos = range(len(col_names))

            for ci, cat in enumerate(category_order):
                debuff_vals = [debuffs.get(c, {}).get(cat, 0) for c in col_names]
                buff_vals = [buffs.get(c, {}).get(cat, 0) for c in col_names]
                color = cat_colors.get(cat, "#95a5a6")
                if any(v != 0 for v in debuff_vals):
                    left = [0] * len(col_names)
                    # Stack debuffs left of zero
                    for prev_cat in category_order[:ci]:
                        for j, c in enumerate(col_names):
                            left[j] += debuffs.get(c, {}).get(prev_cat, 0)
                    ax.barh(y_pos, debuff_vals, left=left, color=color,
                            label=f"{cat.capitalize()} (-)" if ci == 0 or any(v != 0 for v in debuff_vals) else "",
                            alpha=0.8, height=0.6)
                if any(v != 0 for v in buff_vals):
                    left_b = [0] * len(col_names)
                    for prev_cat in category_order[:ci]:
                        for j, c in enumerate(col_names):
                            left_b[j] += buffs.get(c, {}).get(prev_cat, 0)
                    ax.barh(y_pos, buff_vals, left=left_b, color=color,
                            alpha=0.4, height=0.6)

            ax.set_yticks(y_pos)
            ax.set_yticklabels(col_names)
            ax.axvline(x=0, color="black", linewidth=0.5)
            ax.set_xlabel("Mood Impact")
            ax.set_title("Mood Debuffs & Buffs by Category (final snapshot)")
            # Build legend manually to avoid duplicates
            handles = [plt.Rectangle((0, 0), 1, 1, color=cat_colors.get(cat, "#95a5a6"))
                        for cat in category_order]
            ax.legend(handles, [c.capitalize() for c in category_order],
                      fontsize=8, loc="lower right")
            ax.grid(True, alpha=0.3, axis="x")
            path = os.path.join(result_dir, "chart_mood_debuffs.png")
            fig.tight_layout()
            fig.savefig(path, dpi=100)
            plt.close(fig)
            saved.append(path)

    # Chart 4 fallback: raw needs if no mood category data
    elif all_colonists:
        needs_to_plot = [
            ("food", "Food", "#e74c3c", 0.25),
            ("rest", "Rest", "#3498db", 0.20),
            ("mood", "Mood", "#f39c12", 0.30),
            ("joy", "Joy", "#2ecc71", 0.15),
            ("beauty", "Beauty", "#9b59b6", None),
            ("comfort", "Comfort", "#1abc9c", 0.15),
        ]
        fig, axes = plt.subplots(2, 3, figsize=(15, 8), sharex=True)

        for idx, (need, label, _color, crit_line) in enumerate(needs_to_plot):
            ax = axes[idx // 3][idx % 3]
            for ci, col_name in enumerate(sorted_colonists):
                vals = []
                for e in entries:
                    cn = e.get("colonist_needs", {}).get(col_name, {})
                    v = cn.get(need, -1)
                    vals.append(v if v >= 0 else None)
                ax.plot(elapsed, vals, "-o", color=colonist_colors[ci % len(colonist_colors)],
                        label=col_name, markersize=3, linewidth=1.5)
            ax.set_title(label)
            ax.set_ylim(0, 1)
            if crit_line is not None:
                ax.axhline(y=crit_line, color="red", linestyle=":", alpha=0.5)
            ax.grid(True, alpha=0.3)
            if idx == 0:
                ax.legend(fontsize=8)

        for ax in axes[1]:
            ax.set_xlabel("Elapsed (s)")
        fig.suptitle("Colonist Needs Over Time", fontsize=14)
        fig.tight_layout()
        path = os.path.join(result_dir, "chart_needs.png")
        fig.savefig(path, dpi=100)
        plt.close(fig)
        saved.append(path)

    # ── Chart 5: Colony wealth over time ──
    has_wealth = any(e.get("wealth") for e in entries)
    if has_wealth:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(elapsed, [e.get("wealth", {}).get("total", 0) for e in entries],
                "b-o", label="Total", linewidth=2, markersize=4)
        ax.plot(elapsed, [e.get("wealth", {}).get("buildings", 0) for e in entries],
                "#e67e22", linestyle="-", marker="s", label="Buildings", markersize=4)
        ax.plot(elapsed, [e.get("wealth", {}).get("items", 0) for e in entries],
                "#27ae60", linestyle="-", marker="^", label="Items", markersize=4)
        ax.set_xlabel("Elapsed (s)")
        ax.set_ylabel("Wealth")
        ax.set_title("Colony Wealth Over Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        path = os.path.join(result_dir, "chart_wealth.png")
        fig.tight_layout()
        fig.savefig(path, dpi=100)
        plt.close(fig)
        saved.append(path)

    # ── Chart 6: Work time by job category (colony-wide stacked area) ──
    if all_colonists and len(entries) >= 3:
        # Map raw RimWorld JobDef defNames to high-level work categories
        JOB_CATEGORIES = {
            # Construction
            "FinishFrame": "Construction", "BuildRoof": "Construction",
            "PlaceNoCostFrame": "Construction", "PlaceBuildingNearThing": "Construction",
            "RemoveRoof": "Construction", "Deconstruct": "Construction",
            "SmoothFloor": "Construction", "SmoothWall": "Construction",
            "RemoveFloor": "Construction",
            # Hauling
            "HaulToCell": "Hauling", "HaulToContainer": "Hauling",
            "Haul": "Hauling", "Deliver": "Hauling", "Refuel": "Hauling",
            "UnloadCarriers": "Hauling", "UnloadYourInventory": "Hauling",
            "CarryToCryptosleepCasket": "Hauling", "CarryAndRelease": "Hauling",
            "FillFermentingBarrel": "Hauling",
            # Growing / Farming
            "Sow": "Growing", "SowOnCell": "Growing",
            "Harvest": "Growing", "HarvestDesignated": "Growing",
            "CutPlant": "Growing", "CutPlantDesignated": "Growing",
            # Cooking / Production (bills at workbenches)
            "DoBill": "Cooking", "Cook": "Cooking",
            # Research
            "Research": "Research",
            # Mining
            "Mine": "Mining", "DesignateMine": "Mining",
            # Hunting / Combat
            "Hunt": "Hunting",
            "AttackMelee": "Hunting", "AttackStatic": "Hunting",
            "Wait_Combat": "Hunting",
            # Medical
            "Tend": "Medical", "Rescue": "Medical", "FeedPatient": "Medical",
            "TendPatient": "Medical", "VisitSickPawn": "Medical",
            # Cleaning
            "Clean": "Cleaning",
            # Social / Recreation
            "SocialRelax": "Recreation", "Skygaze": "Recreation",
            "Play_HorseshoesPin": "Recreation", "Play_Horseshoes": "Recreation",
            "Play_Billiards": "Recreation", "Play_Chess": "Recreation",
            "Meditate": "Recreation", "Lovin": "Recreation",
            "Joy_Wander": "Recreation",
            # Rest / Eating
            "LayDown": "Sleeping", "Ingest": "Eating",
            # Idle / Movement
            "Wait": "Idle", "Wait_Wander": "Idle", "GotoWander": "Idle",
            "Goto": "Idle", "Wander": "Idle", "idle": "Idle", "Idle": "Idle",
        }

        def categorize_job(job_name):
            if job_name in JOB_CATEGORIES:
                return JOB_CATEGORIES[job_name]
            jl = job_name.lower()
            if "haul" in jl or "carry" in jl or "deliver" in jl: return "Hauling"
            if "build" in jl or "frame" in jl or "floor" in jl or "roof" in jl: return "Construction"
            if "cook" in jl or "bill" in jl: return "Cooking"
            if "hunt" in jl or "attack" in jl: return "Hunting"
            if "lay" in jl or "sleep" in jl or "rest" in jl: return "Sleeping"
            if "research" in jl: return "Research"
            if "clean" in jl: return "Cleaning"
            if "sow" in jl or "harvest" in jl or "cut" in jl or "grow" in jl: return "Growing"
            if "play" in jl or "joy" in jl or "meditat" in jl or "social" in jl or "sky" in jl: return "Recreation"
            if "eat" in jl or "ingest" in jl: return "Eating"
            if "tend" in jl or "rescue" in jl or "doctor" in jl or "medical" in jl: return "Medical"
            if "mine" in jl: return "Mining"
            if "wander" in jl or "wait" in jl or "goto" in jl or "idle" in jl: return "Idle"
            return "Other"

        CAT_COLORS = {
            "Construction": "#e74c3c", "Hauling": "#f39c12", "Growing": "#27ae60",
            "Cooking": "#2ecc71", "Research": "#3498db", "Mining": "#95a5a6",
            "Hunting": "#e67e22", "Medical": "#1abc9c",
            "Cleaning": "#bdc3c7", "Recreation": "#9b59b6", "Sleeping": "#34495e",
            "Eating": "#d35400", "Idle": "#ecf0f1",
            "Other": "#7f8c8d",
        }

        # Accumulate snapshot counts per work category (colony-wide)
        # When blueprints are pending, hauling is likely construction-related
        cat_counts: dict[str, list[int]] = defaultdict(lambda: [0] * len(entries))
        for ei, e in enumerate(entries):
            bps_pending = e.get("blueprints_pending", 0)
            building_grew = (ei > 0 and e.get("buildings", 0) > entries[ei - 1].get("buildings", 0))
            for col, job in e.get("jobs", {}).items():
                cat = categorize_job(job)
                # Reclassify hauling as construction when actively building
                if cat == "Hauling" and (bps_pending > 0 or building_grew):
                    cat = "Construction"
                cat_counts[cat][ei] += 1

        # Convert to cumulative hours-equivalent (each snapshot = interval seconds of work)
        intervals = []
        for i in range(len(entries)):
            if i == 0:
                intervals.append(entries[0]["elapsed_s"])
            else:
                intervals.append(entries[i]["elapsed_s"] - entries[i - 1]["elapsed_s"])

        # Cumulative work-seconds per category
        cum_work: dict[str, list[float]] = {}
        for cat, counts in cat_counts.items():
            cum = []
            running = 0.0
            for ei in range(len(entries)):
                running += counts[ei] * intervals[ei]
                cum.append(running / 60.0)  # convert to minutes
            cum_work[cat] = cum

        # Sort categories by total work (descending), skip near-zero
        active_cats = [(cat, vals) for cat, vals in cum_work.items() if vals[-1] > 0.5]
        active_cats.sort(key=lambda x: -x[1][-1])

        # Stacked area chart
        fig, ax = plt.subplots(figsize=(12, 6))
        bottom = [0.0] * len(entries)
        for cat, vals in active_cats:
            color = CAT_COLORS.get(cat, "#7f8c8d")
            ax.fill_between(elapsed, bottom, [b + v for b, v in zip(bottom, vals)],
                            label=cat, color=color, alpha=0.8)
            bottom = [b + v for b, v in zip(bottom, vals)]

        ax.set_xlabel("Elapsed (s)")
        ax.set_ylabel("Cumulative Work (colonist-minutes)")
        ax.set_title("Work Time by Category (all colonists)")
        ax.legend(fontsize=8, loc="upper left", ncol=3)
        ax.grid(True, alpha=0.2)
        path = os.path.join(result_dir, "chart_work.png")
        fig.tight_layout()
        fig.savefig(path, dpi=100)
        plt.close(fig)
        saved.append(path)

        # Per-colonist job breakdown (horizontal bar, final distribution %)
        fig, ax = plt.subplots(figsize=(12, max(3, len(sorted_colonists) * 1.5)))
        y_pos = range(len(sorted_colonists))

        # Count total snapshots per colonist per category
        col_cat_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for e in entries:
            for col, job in e.get("jobs", {}).items():
                cat = categorize_job(job)
                col_cat_counts[col][cat] += 1

        # Plot stacked horizontal bars
        plot_cats = [cat for cat, _ in active_cats]
        for cat in plot_cats:
            widths = []
            lefts = []
            for ci, col in enumerate(sorted_colonists):
                total = sum(col_cat_counts[col].values()) or 1
                pct = col_cat_counts[col].get(cat, 0) / total * 100
                widths.append(pct)
                left = 0
                for prev_cat in plot_cats:
                    if prev_cat == cat:
                        break
                    left += col_cat_counts[col].get(prev_cat, 0) / total * 100
                lefts.append(left)
            color = CAT_COLORS.get(cat, "#7f8c8d")
            ax.barh(list(y_pos), widths, left=lefts, color=color,
                    label=cat, height=0.6, alpha=0.85)

        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(sorted_colonists)
        ax.set_xlabel("Time Distribution (%)")
        ax.set_xlim(0, 100)
        ax.set_title("Per-Colonist Job Distribution")
        ax.legend(fontsize=7, loc="lower right", ncol=3)
        ax.grid(True, alpha=0.2, axis="x")
        path = os.path.join(result_dir, "chart_jobs.png")
        fig.tight_layout()
        fig.savefig(path, dpi=100)
        plt.close(fig)
        saved.append(path)

    # ── Chart 7: Need buckets (colony-wide survival/happiness/environment) ──
    has_buckets = any(e.get("need_buckets") for e in entries)
    if has_buckets:
        fig, ax = plt.subplots(figsize=(10, 4))
        for bucket, color, label in [
            ("survival", "#e74c3c", "Survival (food+rest)"),
            ("happiness", "#f39c12", "Happiness (mood+joy)"),
            ("environment", "#3498db", "Environment (beauty+comfort)"),
        ]:
            vals = []
            for e in entries:
                nb = e.get("need_buckets", {})
                v = nb.get(bucket, -1)
                vals.append(v if v >= 0 else None)
            ax.plot(elapsed, vals, "-o", color=color, label=label, markersize=4, linewidth=2)
        ax.set_xlabel("Elapsed (s)")
        ax.set_ylabel("Level (0-1)")
        ax.set_title("Colony Need Buckets")
        ax.set_ylim(0, 1)
        ax.axhline(y=0.3, color="red", linestyle=":", alpha=0.5)
        ax.legend()
        ax.grid(True, alpha=0.3)
        path = os.path.join(result_dir, "chart_need_buckets.png")
        fig.tight_layout()
        fig.savefig(path, dpi=100)
        plt.close(fig)
        saved.append(path)

    return saved


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python frontier/timeline_charts.py <result_dir>")
        sys.exit(1)
    paths = generate_charts(sys.argv[1])
    for p in paths:
        print(f"  Saved: {p}")

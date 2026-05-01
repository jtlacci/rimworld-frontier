"""Scenario-adaptive scoring wrapper around sdk/snapshot.py.

Adjusts rubric weights and thresholds based on scenario constraints.
For example: sand terrain disables self_sufficiency scoring, cold maps
double temp_safety weight, 50x50 maps lower building_progress thresholds.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# sdk/ lives at the repo root alongside frontier/
sys.path.insert(0, str(Path(__file__).parent.parent / "sdk"))

from snapshot import score_snapshot as _base_score_snapshot
from timeline_scoring import score_timeline
from frontier.scenario import ScenarioConfig


# Terrain types where farming is impossible or impractical
NO_FARM_TERRAINS = {"Sand", "Gravel"}

# Temperature thresholds
COLD_THRESHOLD = 5.0    # below this, cold-start rules apply
HOT_THRESHOLD = 35.0    # above this, heat-start rules apply


def scenario_weight_adjustments(config: ScenarioConfig) -> dict[str, float]:
    """Return weight multipliers per metric based on scenario constraints.

    Returns a dict of metric_name -> multiplier (1.0 = no change).
    """
    adj: dict[str, float] = {}

    # 50x50 maps have fewer resources — scale down building expectations
    if config.map_size <= 75:
        adj["building_progress"] = 0.7     # less material available
        adj["queue_health"] = 0.8          # tighter build queues expected
        adj["progress_pace"] = 0.8         # fewer buildings to track

    # Cold maps: need management is harder
    if config.temperature < COLD_THRESHOLD:
        adj["need_sustained"] = 1.5

    # No-farm terrains: food trajectory less meaningful
    if config.terrain in NO_FARM_TERRAINS:
        adj["food_trajectory"] = 0.5
        adj["self_sufficiency"] = 0.0      # can't farm, don't penalize

    # Low/no trees: wood is scarce
    if not config.trees or config.tree_density < 0.02:
        adj["self_sufficiency"] = adj.get("self_sufficiency", 1.0) * 0.5

    # Cold start: shelter and temperature safety matter more
    if config.temperature < COLD_THRESHOLD:
        adj["temp_safety"] = 2.0
        adj["shelter"] = 1.5
        # Less building expected when survival is the priority
        adj["building_progress"] = adj.get("building_progress", 1.0) * 0.8
        adj["avg_impressiveness"] = 0.5
        adj["avg_beauty"] = 0.3

    # Hot start: temperature safety matters more
    if config.temperature > HOT_THRESHOLD:
        adj["temp_safety"] = 1.5

    # Mountain maps: mining is expected, but building area is limited
    if config.mountains in ("ring", "border"):
        adj["building_progress"] = adj.get("building_progress", 1.0) * 0.8

    # Water maps: buildable area is reduced
    if config.water in ("lake", "border"):
        adj["building_progress"] = adj.get("building_progress", 1.0) * 0.8

    # ── Challenge-specific overrides (applied AFTER physical parameter adjustments) ──

    if config.name == "build_quality":
        # Override the 50x50 building_progress reduction back to full weight
        adj["building_progress"] = 1.0
        adj["avg_impressiveness"] = 1.0

    elif config.name == "mood_management":
        adj["avg_mood"] = adj.get("avg_mood", 1.0) * 1.5
        adj["quality_of_life"] = adj.get("quality_of_life", 1.0) * 2.0
        adj["worst_mood"] = adj.get("worst_mood", 1.0) * 2.0
        adj["no_breaks"] = adj.get("no_breaks", 1.0) * 2.0

    elif config.name == "research_sprint":
        adj["research_progress"] = adj.get("research_progress", 1.0) * 2.0
        adj["production_throughput"] = adj.get("production_throughput", 1.0) * 1.5

    elif config.name == "water_logistics":
        adj["progress_pace"] = adj.get("progress_pace", 1.0) * 1.5
        adj["workforce_usage"] = adj.get("workforce_usage", 1.0) * 1.5

    elif config.name == "resource_scarcity":
        adj["self_sufficiency"] = adj.get("self_sufficiency", 1.0) * 0.5
        adj["food_trajectory"] = adj.get("food_trajectory", 1.0) * 0.5

    elif config.name == "tight_space":
        adj["building_progress"] = adj.get("building_progress", 1.0) * 0.8

    # food_pressure, shelter_rush, self_sufficiency, balanced_hard:
    # no special adjustments needed (handled by physical parameters or standard weights)

    return adj


# ── Mission-specific scoring functions ──

MISSION_SCORERS = {}


def mission_scorer(name):
    """Decorator to register a mission scoring function."""
    def wrapper(fn):
        MISSION_SCORERS[name] = fn
        return fn
    return wrapper


@mission_scorer("feed_the_colony")
def _score_feed_the_colony(before: dict, after: dict, timeline: list[dict] | None,
                            duration_s: int, config: ScenarioConfig) -> dict[str, Any]:
    """Custom rubric: meals_produced(30), food_sustained(30), no_starvation(20),
    food_stockpile(10), all_alive(10). Total: 100pts."""
    breakdown = {}
    entries = timeline or []

    # meals_produced (30pts) — total meals that existed across all snapshots
    # Use peak meals as proxy for production capacity
    peak_meals = max((e.get("meals", 0) for e in entries), default=0)
    all_meals = [e.get("meals", 0) for e in entries]
    if peak_meals >= 15:
        score = 1.0
    elif peak_meals >= 10:
        score = 0.8
    elif peak_meals >= 5:
        score = 0.6
    elif peak_meals >= 1:
        score = 0.3
    else:
        score = 0.0
    breakdown["meals_produced"] = {"score": round(score, 2), "weight": 30,
                                    "weighted": round(score * 30, 1), "max": 30,
                                    "detail": f"peak={peak_meals}, timeline={all_meals}"}

    # food_sustained (30pts) — % of snapshots where ALL colonists have food > 0.25
    fed_snapshots = 0
    total_snapshots = len(entries)
    for e in entries:
        cn = e.get("colonist_needs", {})
        if not cn:
            continue
        all_fed = all(
            n.get("food", 1.0) > 0.25
            for n in cn.values()
            if isinstance(n, dict)
        )
        if all_fed:
            fed_snapshots += 1
    fed_pct = fed_snapshots / max(total_snapshots, 1)
    breakdown["food_sustained"] = {"score": round(fed_pct, 2), "weight": 30,
                                    "weighted": round(fed_pct * 30, 1), "max": 30,
                                    "detail": f"{fed_snapshots}/{total_snapshots} snapshots all fed"}

    # no_starvation (20pts) — 1.0 if no starvation alerts ever appeared
    any_starvation = False
    for e in entries:
        alerts = e.get("alerts", [])
        for a in alerts:
            if "starvation" in str(a).lower():
                any_starvation = True
                break
        if any_starvation:
            break
    starv_score = 0.0 if any_starvation else 1.0
    breakdown["no_starvation"] = {"score": starv_score, "weight": 20,
                                   "weighted": round(starv_score * 20, 1), "max": 20,
                                   "detail": f"starvation_alerts={'yes' if any_starvation else 'none'}"}

    # food_stockpile (10pts) — meals in stockpile at end
    final_meals = entries[-1].get("meals", 0) if entries else 0
    if final_meals >= 10:
        stock_score = 1.0
    elif final_meals >= 5:
        stock_score = 0.7
    elif final_meals >= 1:
        stock_score = 0.3
    else:
        stock_score = 0.0
    breakdown["food_stockpile"] = {"score": round(stock_score, 2), "weight": 10,
                                    "weighted": round(stock_score * 10, 1), "max": 10,
                                    "detail": f"final_meals={final_meals}"}

    # all_alive (10pts)
    before_count = len(before.get("colonists", {}).get("colonists", []))
    after_count = len(after.get("colonists", {}).get("colonists", []))
    alive_score = 1.0 if after_count >= before_count else 0.0
    breakdown["all_alive"] = {"score": alive_score, "weight": 10,
                               "weighted": round(alive_score * 10, 1), "max": 10,
                               "detail": f"{after_count}/{before_count} alive"}

    total = sum(info["weighted"] for info in breakdown.values())
    max_pts = sum(info["max"] for info in breakdown.values())
    pct = (total / max_pts * 100) if max_pts > 0 else 0

    return {
        "total": round(total, 1),
        "max": max_pts,
        "pct": round(pct, 1),
        "base_total": round(total, 1),
        "base_max": max_pts,
        "base_pct": round(pct, 1),
        "breakdown": breakdown,
        "efficiency": {},
        "adjustments": {},
        "scenario": config.name,
        "mission": config.mission,
        "rubric": "feed_the_colony",
        "difficulty": round(config.overall_difficulty(), 2),
    }


def _score_from_config(config: ScenarioConfig, before: dict, after: dict,
                       timeline: list[dict] | None, duration_s: int) -> dict[str, Any]:
    """Score using inline rubric from scenario JSON.

    Each metric in config.scoring is:
        {
            "weight": 30,
            "metric": "peak_meals" | "pct_fed" | "no_alert" | "final_meals" |
                      "all_alive" | "final_value" | "pct_snapshots_above",
            "thresholds": [1, 5, 10, 15],  # maps to [0.3, 0.6, 0.8, 1.0]
            "threshold": 0.25,             # for pct_fed: food need minimum
            "alert": "starvation",         # for no_alert
            "resource": "WoodLog",         # for final_value
            "need": "food",                # for pct_snapshots_above
        }
    """
    entries = timeline or []
    breakdown = {}

    for metric_name, spec in config.scoring.items():
        weight = spec.get("weight", 10)
        metric_type = spec.get("metric", "")
        score = 0.0
        detail = ""

        if metric_type == "peak_meals":
            peak = max((e.get("meals", 0) for e in entries), default=0)
            thresholds = spec.get("thresholds", [1, 5, 10, 15])
            scores = _threshold_score(peak, thresholds)
            score = scores
            detail = f"peak={peak}"

        elif metric_type == "pct_fed":
            threshold = spec.get("threshold", 0.25)
            need_key = spec.get("need", "food")
            fed = 0
            total = len(entries)
            for e in entries:
                cn = e.get("colonist_needs", {})
                if cn and all(n.get(need_key, 1.0) > threshold for n in cn.values() if isinstance(n, dict)):
                    fed += 1
            score = fed / max(total, 1)
            detail = f"{fed}/{total} snapshots above {need_key}>{threshold}"

        elif metric_type == "no_alert":
            alert_keyword = spec.get("alert", "starvation")
            found = any(alert_keyword in str(a).lower() for e in entries for a in e.get("alerts", []))
            score = 0.0 if found else 1.0
            detail = f"{alert_keyword}_alerts={'yes' if found else 'none'}"

        elif metric_type == "final_meals":
            final = entries[-1].get("meals", 0) if entries else 0
            thresholds = spec.get("thresholds", [1, 5, 10])
            score = _threshold_score(final, thresholds)
            detail = f"final_meals={final}"

        elif metric_type == "all_alive":
            bc = len(before.get("colonists", {}).get("colonists", []))
            ac = len(after.get("colonists", {}).get("colonists", []))
            score = 1.0 if ac >= bc else 0.0
            detail = f"{ac}/{bc} alive"

        elif metric_type == "final_value":
            resource = spec.get("resource", "WoodLog")
            resources = after.get("resources", {})
            val = resources.get(resource, 0)
            thresholds = spec.get("thresholds", [10, 50, 100])
            score = _threshold_score(val, thresholds)
            detail = f"{resource}={val}"

        elif metric_type == "pct_snapshots_above":
            need_key = spec.get("need", "food")
            threshold = spec.get("threshold", 0.5)
            above = 0
            total = len(entries)
            for e in entries:
                cn = e.get("colonist_needs", {})
                if cn and all(n.get(need_key, 1.0) > threshold for n in cn.values() if isinstance(n, dict)):
                    above += 1
            score = above / max(total, 1)
            detail = f"{above}/{total} snapshots {need_key}>{threshold}"

        elif metric_type == "rooms_count":
            min_rooms = spec.get("min", 1)
            rooms = [r for e in entries[-3:] for r in e.get("rooms", []) if isinstance(r, dict)]
            unique_roles = set(r.get("role", "") for r in rooms)
            count = len(unique_roles)
            score = min(count / min_rooms, 1.0) if min_rooms > 0 else 1.0
            detail = f"{count} room types, need {min_rooms}"

        elif metric_type == "avg_impressiveness":
            target = spec.get("target", 25)
            rooms = entries[-1].get("rooms", []) if entries else []
            imps = [r.get("impressiveness", 0) for r in rooms if isinstance(r, dict)]
            avg = sum(imps) / len(imps) if imps else 0
            score = min(avg / target, 1.0) if target > 0 else 1.0
            detail = f"avg_imp={avg:.1f}, target={target}"

        else:
            detail = f"unknown metric type: {metric_type}"

        breakdown[metric_name] = {
            "score": round(score, 2),
            "weight": weight,
            "adjusted_weight": weight,
            "weighted": round(score * weight, 1),
            "max": weight,
            "detail": detail,
        }

    total = sum(info["weighted"] for info in breakdown.values())
    max_pts = sum(info["max"] for info in breakdown.values())
    pct = (total / max_pts * 100) if max_pts > 0 else 0

    return {
        "total": round(total, 1),
        "max": max_pts,
        "pct": round(pct, 1),
        "base_total": round(total, 1),
        "base_max": max_pts,
        "base_pct": round(pct, 1),
        "breakdown": breakdown,
        "efficiency": {},
        "adjustments": {},
        "scenario": config.name,
        "mission": config.mission,
        "rubric": "inline",
        "difficulty": round(config.overall_difficulty(), 2),
    }


def _threshold_score(value: float, thresholds: list) -> float:
    """Map a value to 0-1 score based on threshold list.
    thresholds=[1, 5, 10, 15] maps to scores [0.3, 0.6, 0.8, 1.0]"""
    if not thresholds:
        return 0.0
    n = len(thresholds)
    for i, t in enumerate(thresholds):
        if value < t:
            return round((i / n) * (i / (i + 1)), 2) if i > 0 else 0.0
    return 1.0


def score_scenario(
    config: ScenarioConfig,
    before: dict,
    after: dict,
    duration_s: int = 0,
    overseer_tokens: int = 0,
    overseer_cost_usd: float = 0,
    timeline: list[dict] | None = None,
) -> dict[str, Any]:
    """Score a scenario run. Uses mission-specific rubric if available,
    otherwise falls back to baseline rubric with weight adjustments.

    Returns a dict with:
        total, max, pct, breakdown, efficiency, scenario, ...
    """
    # Check for inline scoring rubric in scenario JSON
    if config.scoring:
        print(f"  Using inline scoring rubric from scenario JSON")
        return _score_from_config(config, before, after, timeline, duration_s)

    # Check for mission-specific scorer (legacy hardcoded)
    if config.mission and config.mission in MISSION_SCORERS:
        print(f"  Using mission rubric: {config.mission}")
        return MISSION_SCORERS[config.mission](before, after, timeline, duration_s, config)

    # Fallback: baseline rubric with weight adjustments
    total, max_pts, breakdown, efficiency = _base_score_snapshot(
        before, after, duration_s, overseer_tokens, overseer_cost_usd
    )

    # Merge timeline metrics if available
    if timeline:
        tl_scores, tl_weights = score_timeline(timeline)
        for metric, score in tl_scores.items():
            breakdown[metric] = {
                "score": score,
                "weight": tl_weights[metric],
                "weighted": round(score * tl_weights[metric], 1),
                "explanation": f"timeline metric ({len(timeline)} snapshots)",
            }

    # Apply scenario-specific weight adjustments
    adjustments = scenario_weight_adjustments(config)
    adjusted_total = 0.0
    adjusted_max = 0.0

    for metric, info in breakdown.items():
        if metric.startswith("_"):
            continue
        multiplier = adjustments.get(metric, 1.0)
        original_weight = info["weight"]
        adjusted_weight = original_weight * multiplier

        info["adjusted_weight"] = round(adjusted_weight, 1)
        info["weight_multiplier"] = multiplier
        info["adjusted_weighted"] = round(info["score"] * adjusted_weight, 1)
        info["adjusted_max"] = round(adjusted_weight, 1)

        adjusted_total += info["score"] * adjusted_weight
        adjusted_max += adjusted_weight

    adjusted_pct = (adjusted_total / adjusted_max * 100) if adjusted_max > 0 else 0

    # Time efficiency: adjust for 5-min wall clock on 50x50
    if config.map_size <= 75 and "time_efficiency" in breakdown:
        if duration_s <= 300:
            breakdown["time_efficiency"]["score"] = 1.0
        elif duration_s <= 450:
            breakdown["time_efficiency"]["score"] = 0.8
        elif duration_s <= 600:
            breakdown["time_efficiency"]["score"] = 0.5
        else:
            breakdown["time_efficiency"]["score"] = 0.2

    return {
        "total": round(adjusted_total, 1),
        "max": round(adjusted_max, 1),
        "pct": round(adjusted_pct, 1),
        "base_total": total,
        "base_max": max_pts,
        "base_pct": round(total / max_pts * 100, 1) if max_pts > 0 else 0,
        "breakdown": breakdown,
        "efficiency": efficiency,
        "adjustments": adjustments,
        "scenario": config.name,
        "difficulty": round(config.overall_difficulty(), 2),
    }

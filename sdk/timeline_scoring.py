"""Timeline-based scoring — progression quality metrics from periodic snapshots.

Analyzes score_timeline.jsonl entries to detect patterns invisible to
final-snapshot scoring: sustained need deprivation, late food recovery,
construction stalls, and idle colonists.

Returns (scores, weights) in the same format as snapshot.py metrics,
ready to merge into score_scenario() breakdown.
"""

from __future__ import annotations


# Need thresholds: (warning, critical)
NEED_THRESHOLDS = {
    "food": (0.40, 0.25),
    "rest": (0.35, 0.20),
    "mood": (0.40, 0.30),
    "joy":  (0.25, 0.15),
}

# Jobs that count as idle (not productive work)
IDLE_JOBS = {"Wait", "GotoWander", "Wait_Wander", "Goto", "idle", "Wander", "Wait_Combat"}


def score_timeline(entries: list[dict]) -> tuple[dict, dict]:
    """Score timeline progression from score_monitor.py snapshots.

    Args:
        entries: List of dicts from score_timeline.jsonl

    Returns:
        (scores, weights) where scores maps metric_name -> 0.0-1.0
        and weights maps metric_name -> int weight.
        Returns ({}, {}) if < 3 snapshots (graceful degradation).
    """
    if len(entries) < 3:
        return {}, {}

    scores = {}
    weights = {}

    # 1. need_sustained (weight 10)
    scores["need_sustained"] = _score_need_sustained(entries)
    weights["need_sustained"] = 10

    # 2. food_trajectory (weight 5)
    scores["food_trajectory"] = _score_food_trajectory(entries)
    weights["food_trajectory"] = 5

    # 3. progress_pace (weight 5)
    scores["progress_pace"] = _score_progress_pace(entries)
    weights["progress_pace"] = 5

    # 4. workforce_usage (weight 3)
    scores["workforce_usage"] = _score_workforce_usage(entries)
    weights["workforce_usage"] = 3

    return scores, weights


def _score_need_sustained(entries: list[dict]) -> float:
    """Score based on sustained need deprivation across all colonists."""
    n_snapshots = len(entries)
    worst_crisis_fraction = 0.0
    any_need_over_half_critical = False

    # Collect all colonist names across all snapshots
    all_colonists = set()
    for e in entries:
        all_colonists.update(e.get("colonist_needs", {}).keys())

    for col_name in all_colonists:
        col_critical_total = 0
        col_snapshot_count = 0

        for need, (warn_thresh, crit_thresh) in NEED_THRESHOLDS.items():
            need_critical_count = 0
            need_snapshot_count = 0

            for e in entries:
                cn = e.get("colonist_needs", {}).get(col_name, {})
                val = cn.get(need, -1)
                if val < 0:
                    continue
                need_snapshot_count += 1
                if val < crit_thresh:
                    need_critical_count += 1

            if need_snapshot_count > 0:
                need_crit_frac = need_critical_count / need_snapshot_count
                # Any single need > 50% critical → cap at 0.2
                if need_crit_frac > 0.50:
                    any_need_over_half_critical = True
                col_critical_total += need_critical_count
                col_snapshot_count += need_snapshot_count

        # Crisis fraction: fraction of (colonist × need × snapshot) combos in critical
        if col_snapshot_count > 0:
            col_crisis = col_critical_total / col_snapshot_count
            worst_crisis_fraction = max(worst_crisis_fraction, col_crisis)

    # Score based on worst colonist's crisis fraction
    if worst_crisis_fraction == 0:
        score = 1.0
    elif worst_crisis_fraction < 0.10:
        score = 0.8
    elif worst_crisis_fraction < 0.25:
        score = 0.6
    elif worst_crisis_fraction < 0.50:
        score = 0.3
    else:
        score = 0.0

    if any_need_over_half_critical:
        score = min(score, 0.2)

    return round(score, 2)


def _score_food_trajectory(entries: list[dict]) -> float:
    """Score food pipeline timing — early establishment vs late recovery."""
    n = len(entries)
    third = max(1, n // 3)

    early = entries[:third]
    mid = entries[third:2 * third]
    late = entries[2 * third:]

    def avg_food(chunk: list[dict]) -> float:
        vals = []
        for e in chunk:
            for cn in e.get("colonist_needs", {}).values():
                v = cn.get("food", -1)
                if v >= 0:
                    vals.append(v)
        return sum(vals) / len(vals) if vals else 0.5

    early_avg = avg_food(early)
    mid_avg = avg_food(mid)
    late_avg = avg_food(late)

    # Declining trend: each third is lower than the previous
    declining = early_avg > mid_avg > late_avg and (early_avg - late_avg) > 0.15

    if declining:
        score = 0.2
    elif early_avg < 0.35 and late_avg >= 0.5:
        # Late recovery — masking pattern
        score = 0.4
    elif early_avg >= 0.5 and mid_avg >= 0.5 and late_avg >= 0.5:
        score = 1.0
    elif early_avg >= 0.4 and late_avg >= 0.4:
        score = 0.7
    else:
        score = 0.3

    # Bonus: meals appeared early (by 40% of run)
    cutoff_idx = max(1, int(n * 0.4))
    early_entries = entries[:cutoff_idx]
    meals_appeared = any(e.get("meals", 0) > 0 for e in early_entries)
    if meals_appeared and score <= 0.8:
        score = min(score + 0.2, 1.0)

    return round(score, 2)


def _score_progress_pace(entries: list[dict]) -> float:
    """Score construction steadiness — growth snapshots and stall detection."""
    # Skip first 2 snapshots (setup phase)
    if len(entries) <= 2:
        return 0.5
    work_entries = entries[2:]
    n = len(work_entries)
    if n == 0:
        return 0.5

    growth_count = 0
    stall_count = 0
    consecutive_no_growth = 0

    prev_buildings = work_entries[0].get("buildings", 0)
    for e in work_entries[1:]:
        cur_buildings = e.get("buildings", 0)
        if cur_buildings > prev_buildings:
            growth_count += 1
            consecutive_no_growth = 0
        else:
            consecutive_no_growth += 1
            # Stall: 3+ consecutive no-growth while blueprints pending
            if consecutive_no_growth >= 3 and e.get("blueprints_pending", 0) > 0:
                stall_count += 1
                consecutive_no_growth = 0  # Reset to avoid counting overlapping stalls
        prev_buildings = cur_buildings

    growth_frac = growth_count / max(n - 1, 1)

    if growth_frac >= 0.40:
        score = 1.0
    elif growth_frac >= 0.30:
        score = 0.7
    elif growth_frac >= 0.15:
        score = 0.4
    else:
        score = 0.1

    # Stall penalty
    score = max(0.0, score - stall_count * 0.15)

    return round(score, 2)


def _score_workforce_usage(entries: list[dict]) -> float:
    """Score based on colonist idle percentage across the run."""
    colonist_idle = {}   # {name: [is_idle_bool, ...]}

    for e in entries:
        jobs = e.get("jobs", {})
        for col, job in jobs.items():
            if col not in colonist_idle:
                colonist_idle[col] = []
            colonist_idle[col].append(job in IDLE_JOBS)

    if not colonist_idle:
        return 0.5

    # Average idle % across colonists
    idle_pcts = []
    for col, idles in colonist_idle.items():
        if idles:
            idle_pcts.append(sum(idles) / len(idles))

    avg_idle = sum(idle_pcts) / len(idle_pcts) if idle_pcts else 0.0

    if avg_idle < 0.15:
        score = 1.0
    elif avg_idle < 0.25:
        score = 0.7
    elif avg_idle < 0.40:
        score = 0.4
    else:
        score = 0.0

    return round(score, 2)

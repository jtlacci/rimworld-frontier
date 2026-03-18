"""Failure analysis — categorize why a scenario run failed and target fixes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from frontier.scenario import ScenarioConfig


@dataclass
class FailureAnalysis:
    """Categorized failure from a scenario run."""

    scenario_name: str
    score_pct: float
    category: str           # e.g., "food_pipeline", "shelter", "temperature", "resources"
    severity: str           # "critical" (< 30%), "major" (30-60%), "minor" (60-85%)
    description: str
    fix_target: str         # "sdk/rimworld.py", "AGENT_OVERSEER.md", "Source/*.cs"
    fix_suggestion: str
    metrics_affected: list[str] = field(default_factory=list)


# Maps metric names to failure categories and fix targets
FAILURE_MAP: dict[str, dict[str, str]] = {
    "alive": {
        "category": "survival",
        "target": "sdk/rimworld.py",
        "suggestion": "Add emergency response to colony_health_check() — colonist death means critical failure in food/temp/combat",
    },
    "food_safety": {
        "category": "food_pipeline",
        "target": "sdk/rimworld.py",
        "suggestion": "setup_cooking() needs terrain-aware fallback; check if campfire possible without wood",
    },
    "temp_safety": {
        "category": "temperature",
        "target": "sdk/rimworld.py",
        "suggestion": "colony_health_check() needs temperature monitoring; add emergency_heating() for cold starts",
    },
    "shelter": {
        "category": "shelter",
        "target": "sdk/rimworld.py",
        "suggestion": "build_barracks() needs compact variant for small maps; add build_emergency_shelter() for 3x3 heated room",
    },
    "self_sufficiency": {
        "category": "food_pipeline",
        "target": "sdk/rimworld.py",
        "suggestion": "day1_setup() should check terrain fertility before placing grow zones",
    },
    "building_progress": {
        "category": "construction",
        "target": "sdk/rimworld.py",
        "suggestion": "build_barracks() material auto-selection based on availability; compact mode for small maps",
    },
    "production_throughput": {
        "category": "production",
        "target": "sdk/rimworld.py",
        "suggestion": "setup_production() should prioritize based on available resources",
    },
    "avg_impressiveness": {
        "category": "quality",
        "target": "sdk/rimworld.py",
        "suggestion": "build_barracks() and build_storage_room() need furniture placement even in compact mode",
    },
    "game_progress": {
        "category": "time_overrun",
        "target": "AGENT_OVERSEER.md",
        "suggestion": "Adaptive sleep based on blueprint count; reduce build queue on complex maps",
    },
    "time_efficiency": {
        "category": "time_overrun",
        "target": "AGENT_OVERSEER.md",
        "suggestion": "Cap reactive loop iterations; shorter unpause durations on small maps",
    },
    "need_sustained": {
        "category": "survival",
        "target": "sdk/rimworld.py",
        "suggestion": "Colonists had sustained need deprivation — colony_health_check() should trigger emergency responses earlier",
    },
    "food_trajectory": {
        "category": "food_pipeline",
        "target": "sdk/rimworld.py",
        "suggestion": "Food pipeline established too late or declining — setup_cooking() should be called earlier, verify bills are firing",
    },
    "progress_pace": {
        "category": "construction",
        "target": "sdk/rimworld.py",
        "suggestion": "Construction stalled or too slow — check material availability, colonist priorities, blueprint count",
    },
    "workforce_usage": {
        "category": "construction",
        "target": "AGENT_OVERSEER.md",
        "suggestion": "Colonists idle too much — check work priorities, ensure hauling/construction enabled for all pawns",
    },
}


def analyze_run(
    config: ScenarioConfig,
    score_data: dict[str, Any],
) -> list[FailureAnalysis]:
    """Analyze a run's score breakdown and return categorized failures.

    Focuses on metrics that lost significant points.
    """
    failures: list[FailureAnalysis] = []
    breakdown = score_data.get("breakdown", {})
    overall_pct = score_data.get("pct", 0)

    for metric, info in breakdown.items():
        if metric.startswith("_"):
            continue
        if not isinstance(info, dict):
            continue

        score = info.get("score", 1.0)
        weight = info.get("adjusted_weight", info.get("weight", 0))
        points_lost = weight * (1.0 - min(score, 1.0))

        # Only flag significant losses (>= 2 points)
        if points_lost < 2.0:
            continue

        fmap = FAILURE_MAP.get(metric, {
            "category": "other",
            "target": "sdk/rimworld.py",
            "suggestion": f"Investigate {metric} failure",
        })

        if score < 0.3:
            severity = "critical"
        elif score < 0.6:
            severity = "major"
        else:
            severity = "minor"

        # Build context-aware description
        desc = _describe_failure(metric, score, config, info)

        failures.append(FailureAnalysis(
            scenario_name=config.name,
            score_pct=overall_pct,
            category=fmap["category"],
            severity=severity,
            description=desc,
            fix_target=fmap["target"],
            fix_suggestion=fmap["suggestion"],
            metrics_affected=[metric],
        ))

    # Sort by severity (critical first)
    severity_order = {"critical": 0, "major": 1, "minor": 2}
    failures.sort(key=lambda f: severity_order.get(f.severity, 3))

    return failures


def _describe_failure(
    metric: str,
    score: float,
    config: ScenarioConfig,
    info: dict,
) -> str:
    """Build a human-readable description of why a metric failed."""
    parts = [f"{metric}={score:.2f}"]

    if metric == "food_safety" and config.terrain in ("Sand", "Gravel"):
        parts.append(f"terrain={config.terrain} (no farming possible)")
    elif metric == "temp_safety" and abs(config.temperature - 20) > 15:
        parts.append(f"temperature={config.temperature}C (extreme)")
    elif metric == "shelter" and config.map_size <= 50:
        parts.append(f"map_size={config.map_size} (tight space)")
    elif metric == "building_progress" and config.mountains != "none":
        parts.append(f"mountains={config.mountains} (restricted area)")
    elif metric == "self_sufficiency" and not config.trees:
        parts.append("no trees (no wood for campfire)")

    return "; ".join(parts)


def summarize_failures(failures: list[FailureAnalysis]) -> str:
    """Produce a concise summary of failures for the auditor."""
    if not failures:
        return "No significant failures detected."

    lines = [f"  {len(failures)} failures detected:"]
    for f in failures:
        lines.append(
            f"  [{f.severity.upper()}] {f.category}: {f.description}"
            f"\n    Fix: {f.fix_target} — {f.fix_suggestion}"
        )
    return "\n".join(lines)

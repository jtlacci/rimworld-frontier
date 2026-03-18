"""ASCII visualization of the capability frontier."""

from __future__ import annotations

from frontier.tracker import FrontierTracker, ScenarioStatus


# Status display codes
STATUS_DISPLAY = {
    ScenarioStatus.TOO_EASY: "EASY",
    ScenarioStatus.MASTERED: "MAST",
    ScenarioStatus.FRONTIER: "FRNT",
    ScenarioStatus.IMPOSSIBLE: " IMP",
    ScenarioStatus.UNKNOWN: " ???",
}


def frontier_heatmap(tracker: FrontierTracker) -> str:
    """Generate an ASCII heatmap of the capability frontier.

    Shows terrain vs temperature grid with status codes.
    """
    terrains = ["Soil", "Gravel", "Sand", "Mud"]
    temps = [-10, 0, 10, 20, 35, 45]
    temp_labels = [f"{t}C" for t in temps]

    # Build lookup from scenario results
    # Map (terrain, temp_bucket) -> status
    grid: dict[tuple[str, int], ScenarioStatus] = {}

    for name, entry in tracker.state["scenarios"].items():
        status = ScenarioStatus(entry["status"])
        # Try to match scenario to grid cell
        config = _load_scenario_config(tracker, name)
        if config is None:
            continue
        terrain = config.get("terrain", "Soil")
        temp = config.get("temperature", 20)
        # Bucket temperature to nearest grid point
        nearest_temp = min(temps, key=lambda t: abs(t - temp))
        if terrain in terrains:
            grid[(terrain, nearest_temp)] = status

    # Render
    lines = []
    total_runs = tracker.state["total_runs"]
    cost = tracker.state["total_cost_usd"]
    lines.append(f"=== CAPABILITY FRONTIER (run {total_runs}, ${cost:.2f}) — all 50x50 ===")
    lines.append("")

    # Header
    header = f"{'':>12s}" + "".join(f"{t:>8s}" for t in temp_labels)
    lines.append(header)

    # Rows
    for terrain in terrains:
        cells = []
        for temp in temps:
            status = grid.get((terrain, temp), ScenarioStatus.UNKNOWN)
            cells.append(f"{STATUS_DISPLAY[status]:>8s}")
        lines.append(f"{terrain:>12s}" + "".join(cells))

    # Feature rows (mountains, water)
    lines.append("")
    for feature_name, feature_values in [("Mountains", ["ring"]), ("Water", ["river", "lake"])]:
        cells = []
        for temp in temps:
            found = ScenarioStatus.UNKNOWN
            for fv in feature_values:
                key = (feature_name.lower(), fv, temp)
                # Look up by matching scenario
                for name, entry in tracker.state["scenarios"].items():
                    cfg = _load_scenario_config(tracker, name)
                    if cfg and cfg.get(feature_name.lower() + "s" if feature_name == "Mountain" else "water", "none") in feature_values:
                        cfg_temp = cfg.get("temperature", 20)
                        if abs(cfg_temp - temp) < 5:
                            found = ScenarioStatus(entry["status"])
                            break
            cells.append(f"{STATUS_DISPLAY[found]:>8s}")
        lines.append(f"{feature_name:>12s}" + "".join(cells))

    lines.append("")
    lines.append("Key: EASY=too easy  MAST=mastered  FRNT=frontier  IMP=impossible  ???=untested")

    # Summary stats
    summary = tracker.scenario_summary()
    parts = [f"{s}: {c}" for s, c in sorted(summary.items())]
    lines.append(f"Summary: {', '.join(parts)}")

    return "\n".join(lines)


def frontier_summary(tracker: FrontierTracker) -> str:
    """One-line summary of frontier state."""
    s = tracker.scenario_summary()
    total = tracker.state["total_runs"]
    frontier = s.get(ScenarioStatus.FRONTIER.value, 0)
    mastered = s.get(ScenarioStatus.MASTERED.value, 0) + s.get(ScenarioStatus.TOO_EASY.value, 0)
    impossible = s.get(ScenarioStatus.IMPOSSIBLE.value, 0)
    return (
        f"Runs: {total} | Mastered: {mastered} | Frontier: {frontier} | "
        f"Impossible: {impossible} | Cost: ${tracker.state['total_cost_usd']:.2f}"
    )


def _load_scenario_config(tracker: FrontierTracker, name: str) -> dict | None:
    """Load a scenario config from the scenarios/ dir or from calibration."""
    from pathlib import Path
    import json

    # Try saved config
    config_path = tracker.state_path.parent / "scenarios" / f"{name}.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())
        except Exception:
            pass

    # Try calibration scenarios
    from frontier.calibration import get_scenario
    cal = get_scenario(name)
    if cal:
        from dataclasses import asdict
        return asdict(cal)

    return None

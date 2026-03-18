"""Frontier state tracker — persistent classification of scenario results."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any


class ScenarioStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    TOO_EASY = "TOO_EASY"
    MASTERED = "MASTERED"
    FRONTIER = "FRONTIER"
    IMPOSSIBLE = "IMPOSSIBLE"


@dataclass
class RunResult:
    """Result of a single scenario run."""

    scenario_name: str
    run_id: int
    score_pct: float
    base_score_pct: float
    adjusted_score_pct: float
    duration_s: int
    cost_usd: float
    timestamp: float = field(default_factory=time.time)
    failure_categories: list[str] = field(default_factory=list)
    top_losses: list[dict] = field(default_factory=list)

    # Populated from score breakdown
    alive: bool = True
    colonist_deaths: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> RunResult:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def classify_scenario(results: list[RunResult]) -> ScenarioStatus:
    """Classify a scenario based on its run history.

    - TOO_EASY: Score >= 95% on first run
    - MASTERED: Score 85-100% across 2+ runs
    - FRONTIER: Score 50-85%, or high variance
    - IMPOSSIBLE: Score < 50% consistently, or colonist death
    - UNKNOWN: Never tested
    """
    if not results:
        return ScenarioStatus.UNKNOWN

    scores = [r.adjusted_score_pct for r in results]
    avg = sum(scores) / len(scores)
    any_deaths = any(not r.alive for r in results)

    # Single run classification
    if len(results) == 1:
        if scores[0] >= 95:
            return ScenarioStatus.TOO_EASY
        elif scores[0] >= 85:
            return ScenarioStatus.MASTERED
        elif scores[0] >= 50:
            return ScenarioStatus.FRONTIER
        else:
            return ScenarioStatus.IMPOSSIBLE

    # Multi-run classification
    if any_deaths and avg < 50:
        return ScenarioStatus.IMPOSSIBLE

    # Check variance — high variance means FRONTIER regardless of avg
    if len(scores) >= 2:
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)
        if variance > 200:  # std dev > ~14%
            return ScenarioStatus.FRONTIER

    if avg >= 95:
        return ScenarioStatus.TOO_EASY
    elif avg >= 85:
        return ScenarioStatus.MASTERED
    elif avg >= 50:
        return ScenarioStatus.FRONTIER
    else:
        return ScenarioStatus.IMPOSSIBLE


class FrontierTracker:
    """Persistent state tracking for all scenario runs and classifications."""

    def __init__(self, state_path: Path | None = None):
        if state_path is None:
            state_path = Path(__file__).parent / "frontier_state.json"
        self.state_path = state_path
        self.state = self._load()

    def _default_state(self) -> dict:
        return {
            "total_runs": 0,
            "total_cost_usd": 0.0,
            "map_size": 50,
            "wall_clock_limit_s": 450,
            "scenarios": {},
            "frontiers": {},
        }

    def _load(self) -> dict:
        if self.state_path.exists():
            text = self.state_path.read_text().strip()
            if text:
                data = json.loads(text)
                # Ensure all required keys exist (handles partial/empty state)
                defaults = self._default_state()
                for k, v in defaults.items():
                    if k not in data:
                        data[k] = v
                return data
        return {
            "total_runs": 0,
            "total_cost_usd": 0.0,
            "map_size": 50,
            "wall_clock_limit_s": 300,
            "scenarios": {},
            "frontiers": {},
        }

    def save(self):
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def record_run(self, result: RunResult):
        """Record a run result and update classification."""
        self.state["total_runs"] += 1
        self.state["total_cost_usd"] = round(
            self.state["total_cost_usd"] + result.cost_usd, 4
        )

        name = result.scenario_name
        if name not in self.state["scenarios"]:
            self.state["scenarios"][name] = {
                "status": ScenarioStatus.UNKNOWN.value,
                "avg_score": 0.0,
                "runs": [],
                "results": [],
            }

        entry = self.state["scenarios"][name]
        entry["runs"].append(result.run_id)
        entry["results"].append(result.to_dict())

        # Reclassify
        all_results = [RunResult.from_dict(r) for r in entry["results"]]
        new_status = classify_scenario(all_results)
        entry["status"] = new_status.value
        scores = [r.adjusted_score_pct for r in all_results]
        entry["avg_score"] = round(sum(scores) / len(scores), 1) if scores else 0.0

        self._update_frontiers()
        self.save()

    def _update_frontiers(self):
        """Update frontier boundary tracking per dimension."""
        # Track the mastered/failed boundary for temperature
        temp_mastered = None
        temp_failed = None
        for name, entry in self.state["scenarios"].items():
            results = entry.get("results", [])
            if not results:
                continue
            # Try to extract temperature from the scenario config
            # (stored in results dir or inferred from name)
            status = ScenarioStatus(entry["status"])
            # Simple heuristic: parse known scenario names
            temp = self._infer_temperature(name)
            if temp is None:
                continue
            if status in (ScenarioStatus.MASTERED, ScenarioStatus.TOO_EASY):
                if temp_mastered is None or temp < temp_mastered:
                    temp_mastered = temp
            if status == ScenarioStatus.IMPOSSIBLE:
                if temp_failed is None or temp > temp_failed:
                    temp_failed = temp

        if temp_mastered is not None or temp_failed is not None:
            self.state["frontiers"]["temperature"] = {
                "mastered": temp_mastered,
                "failed": temp_failed,
            }

    def _infer_temperature(self, scenario_name: str) -> float | None:
        """Try to infer temperature from scenario config files."""
        config_path = Path(__file__).parent / "scenarios" / f"{scenario_name}.json"
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                return data.get("temperature")
            except Exception:
                pass
        return None

    def get_status(self, scenario_name: str) -> ScenarioStatus:
        entry = self.state["scenarios"].get(scenario_name)
        if entry is None:
            return ScenarioStatus.UNKNOWN
        return ScenarioStatus(entry["status"])

    def get_frontier_scenarios(self) -> list[str]:
        """Return names of all FRONTIER scenarios."""
        return [
            name for name, entry in self.state["scenarios"].items()
            if entry["status"] == ScenarioStatus.FRONTIER.value
        ]

    def get_untested_count(self) -> int:
        """How many calibration scenarios haven't been tested yet."""
        from frontier.calibration import CALIBRATION_SCENARIOS
        tested = set(self.state["scenarios"].keys())
        return sum(1 for s in CALIBRATION_SCENARIOS if s.name not in tested)

    def scenario_summary(self) -> dict[str, int]:
        """Count scenarios by status."""
        counts: dict[str, int] = {}
        for entry in self.state["scenarios"].values():
            s = entry["status"]
            counts[s] = counts.get(s, 0) + 1
        return counts

    def to_capability_profile(self) -> dict[str, Any]:
        """Build a capability profile from all results."""
        profile: dict[str, Any] = {
            "total_runs": self.state["total_runs"],
            "total_cost_usd": self.state["total_cost_usd"],
            "by_status": self.scenario_summary(),
            "frontiers": self.state["frontiers"],
            "scenarios": {},
        }
        for name, entry in self.state["scenarios"].items():
            profile["scenarios"][name] = {
                "status": entry["status"],
                "avg_score": entry["avg_score"],
                "num_runs": len(entry["runs"]),
            }
        return profile

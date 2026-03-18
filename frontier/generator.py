"""Adversarial scenario generator — picks the next scenario to test.

Three phases:
1. Calibration: run pre-defined probes (one dimension at a time)
2. Frontier exploitation (70%): bisect at frontier boundaries
3. Exploration (30%): test under-explored dimension combinations
"""

from __future__ import annotations

import random
from typing import Optional

from frontier.scenario import (
    ScenarioConfig,
    TERRAIN_DIFFICULTY,
    MOUNTAIN_DIFFICULTY,
    WATER_DIFFICULTY,
)
from frontier.tracker import FrontierTracker, ScenarioStatus
from frontier.calibration import CALIBRATION_SCENARIOS


class AdversarialGenerator:
    """Picks the next scenario based on current frontier state."""

    def __init__(self, tracker: FrontierTracker, rng_seed: int = 42):
        self.tracker = tracker
        self.rng = random.Random(rng_seed)

    def next_scenario(self) -> ScenarioConfig:
        """Pick the next scenario to run.

        Priority:
        1. Untested calibration scenarios
        2. Frontier exploitation (70% chance)
        3. Exploration (30% chance)
        """
        # Phase 1: Calibration
        untested = self._untested_calibration()
        if untested:
            return untested[0]

        # Phase 2/3: Frontier exploitation vs exploration
        if self.rng.random() < 0.7:
            scenario = self._frontier_exploit()
            if scenario:
                return scenario

        return self._explore()

    def _untested_calibration(self) -> list[ScenarioConfig]:
        """Return calibration scenarios that haven't been tested yet."""
        tested = set(self.tracker.state["scenarios"].keys())
        return [s for s in CALIBRATION_SCENARIOS if s.name not in tested]

    def _frontier_exploit(self) -> Optional[ScenarioConfig]:
        """Bisect at frontier boundaries to narrow the capability edge.

        Find the dimension with the most valuable unresolved frontier,
        then generate a scenario at the midpoint between mastered and failed.
        """
        frontiers = self.tracker.state.get("frontiers", {})

        # Temperature frontier bisection
        temp_data = frontiers.get("temperature", {})
        mastered_temp = temp_data.get("mastered")
        failed_temp = temp_data.get("failed")

        if mastered_temp is not None and failed_temp is not None:
            gap = mastered_temp - failed_temp
            if gap > 3:  # still room to bisect
                mid_temp = round((mastered_temp + failed_temp) / 2, 1)
                name = f"temp_bisect_{mid_temp:.0f}C"
                if self.tracker.get_status(name) == ScenarioStatus.UNKNOWN:
                    return ScenarioConfig(
                        name=name,
                        terrain="Soil",
                        temperature=mid_temp,
                    )

        # Terrain frontier: escalate mastered terrains to harder variants
        terrain_order = ["Soil", "SoilRich", "Gravel", "Sand", "Mud"]
        for terrain in terrain_order:
            name = terrain.lower()
            status = self.tracker.get_status(name)
            if status in (ScenarioStatus.MASTERED, ScenarioStatus.TOO_EASY):
                # Try combining with another dimension
                for temp in [10, 5, 0, -5]:
                    combo_name = f"{name}_temp{temp}"
                    if self.tracker.get_status(combo_name) == ScenarioStatus.UNKNOWN:
                        return ScenarioConfig(
                            name=combo_name,
                            terrain=terrain,
                            temperature=float(temp),
                        )

        # Escalate FRONTIER scenarios by making them slightly harder
        frontier_names = self.tracker.get_frontier_scenarios()
        if frontier_names:
            name = self.rng.choice(frontier_names)
            config_path = self.tracker.state_path.parent / "scenarios" / f"{name}.json"
            if config_path.exists():
                base = ScenarioConfig.load(config_path)
                return self._escalate(base)

        return None

    def _escalate(self, base: ScenarioConfig) -> ScenarioConfig:
        """Make a scenario slightly harder along its weakest dimension."""
        vec = base.difficulty_vector()
        # Find the dimension with the lowest difficulty (most room to push)
        dims = ["terrain", "mountains", "water", "tree_density", "temperature"]
        min_idx = vec.index(min(vec))
        dim = dims[min_idx]

        from dataclasses import replace
        if dim == "temperature":
            delta = -5 if base.temperature <= 20 else 5
            new_temp = base.temperature + delta
            return replace(base, name=f"{base.name}_esc", temperature=new_temp)
        elif dim == "terrain":
            harder = {"Soil": "Gravel", "SoilRich": "Gravel", "Gravel": "Sand", "Sand": "Mud"}
            new_terrain = harder.get(base.terrain, base.terrain)
            return replace(base, name=f"{base.name}_esc", terrain=new_terrain)
        elif dim == "mountains":
            harder = {"none": "corners", "corners": "random", "random": "ring", "ring": "border"}
            new_mt = harder.get(base.mountains, base.mountains)
            return replace(base, name=f"{base.name}_esc", mountains=new_mt)
        elif dim == "tree_density":
            new_density = max(0.0, base.tree_density - 0.03)
            return replace(base, name=f"{base.name}_esc", tree_density=new_density)
        else:
            # Water
            harder = {"none": "corners", "corners": "river", "river": "lake", "lake": "border"}
            new_water = harder.get(base.water, base.water)
            return replace(base, name=f"{base.name}_esc", water=new_water)

    def _explore(self) -> ScenarioConfig:
        """Generate a scenario in an under-tested region of the space.

        Combine dimensions that haven't been tested together.
        """
        terrains = list(TERRAIN_DIFFICULTY.keys())
        mountains = list(MOUNTAIN_DIFFICULTY.keys())
        waters = list(WATER_DIFFICULTY.keys())
        temps = [20, 10, 0, -5, 30, 40]

        # Generate random combos and pick one that's untested
        for _ in range(50):
            t = self.rng.choice(terrains)
            m = self.rng.choice(mountains)
            w = self.rng.choice(waters)
            temp = self.rng.choice(temps)
            td = self.rng.uniform(0.0, 0.15)

            name = f"explore_{t.lower()}_{m}_{w}_{temp}C"
            if self.tracker.get_status(name) == ScenarioStatus.UNKNOWN:
                return ScenarioConfig(
                    name=name,
                    terrain=t,
                    mountains=m,
                    water=w,
                    temperature=float(temp),
                    trees=td > 0.01,
                    tree_density=round(td, 3),
                    seed=self.rng.randint(1, 9999),
                )

        # Fallback: just perturb baseline
        temp = self.rng.uniform(-10, 40)
        return ScenarioConfig(
            name=f"explore_fallback_{temp:.0f}C",
            terrain="Soil",
            temperature=temp,
            seed=self.rng.randint(1, 9999),
        )

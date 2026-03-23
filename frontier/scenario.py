"""Scenario configuration for frontier training."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path


TERRAIN_DIFFICULTY = {"Soil": 0, "SoilRich": 0, "Gravel": 0.5, "Sand": 0.7, "Mud": 0.8}
MOUNTAIN_DIFFICULTY = {"none": 0, "corners": 0.3, "random": 0.5, "ring": 0.7, "border": 0.9}
WATER_DIFFICULTY = {"none": 0, "corners": 0.2, "river": 0.4, "lake": 0.6, "border": 0.8}


def _agent_repo() -> Path:
    """Resolve the agent repo path from AGENT_REPO env var or default sibling."""
    env = os.environ.get("AGENT_REPO")
    if env:
        return Path(env)
    # Default: sibling directory of this repo
    frontier_root = Path(__file__).parent.parent
    candidate = frontier_root.parent / "rimworld-tcp"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        "AGENT_REPO not set and ../rimworld-tcp not found. "
        "Set AGENT_REPO env var to point to the agent repo."
    )


@dataclass
class ScenarioConfig:
    """Defines a single test scenario for frontier training.

    All maps are 50x50 — resource-constrained, fast runs (~5 min wall clock).
    """

    name: str
    map_size: int = 50
    terrain: str = "Soil"
    mountains: str = "none"
    water: str = "none"
    trees: bool = True
    tree_density: float = 0.08
    temperature: float = 20.0
    keep_ruins: bool = False
    seed: int = 42
    berry_bushes: int = 0
    keep_wildlife: bool = False
    starting_packs: int | None = None
    wildlife_count: int = 0
    starting_items: dict[str, int] | None = None  # e.g. {"Steel": 500, "WoodLog": 200}
    completed_research: list[str] | None = None    # e.g. ["Electricity", "Batteries"]
    wildlife_species: list[str] | None = None      # e.g. ["Turkey", "Deer"] — only spawn these
    wildlife_distribution: dict[str, int] | None = None  # e.g. {"Boar": 3, "Deer": 4, "Hare": 3} — exact counts per species
    scheduled_spawns: list[dict] | None = None           # e.g. [{"game_hour": 36, "species": "Warg", "count": 2, "manhunter": true}]
    ruins: list[dict] | None = None                # e.g. [{"x": 10, "z": 10, "width": 8, "height": 6, "stuff": "BlocksGranite"}]
    ponds: list[dict] | None = None                # e.g. [{"x": 30, "z": 30, "radius": 5}]
    mountain_side: str | None = None               # "left", "right", "top", "bottom"
    mountain_resources: list[dict] | None = None   # e.g. [{"x": 2, "z": 5, "width": 3, "height": 3, "type": "MineableSteel"}]
    grass: bool = True                              # generate wild grass
    grass_density: float = 0.6                      # 0.0-1.0, fraction of open cells with grass
    mission: str | None = None                      # mission identifier (matches SCENARIO_*.md)
    mission_description: str | None = None          # short description of the mission goal
    scoring: dict[str, dict] | None = None           # custom scoring rubric, see frontier/scoring.py

    def difficulty_vector(self) -> list[float]:
        """Normalized 0-1 per dimension, higher = harder."""
        return [
            TERRAIN_DIFFICULTY.get(self.terrain, 0.5),
            MOUNTAIN_DIFFICULTY.get(self.mountains, 0.5),
            WATER_DIFFICULTY.get(self.water, 0.5),
            1.0 - min(self.tree_density / 0.15, 1.0),
            min(abs(self.temperature - 20) / 40, 1.0),
        ]

    def overall_difficulty(self) -> float:
        """Single 0-1 difficulty score (mean of dimensions)."""
        v = self.difficulty_vector()
        return sum(v) / len(v) if v else 0.0

    def save_name(self) -> str:
        """Name for the generated .rws save file."""
        return f"Frontier-{self.name}"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def save(self, path: Path):
        path.write_text(self.to_json())

    @classmethod
    def from_json(cls, text: str) -> ScenarioConfig:
        return cls(**json.loads(text))

    @classmethod
    def load(cls, path: Path) -> ScenarioConfig:
        return cls.from_json(path.read_text())

    def generate_save(self, saves_dir: Path | None = None) -> Path:
        """Generate a .rws save file using tools/savegen.py from the agent repo.

        Returns the path to the generated save file.
        """
        import sys
        agent_repo = _agent_repo()
        sys.path.insert(0, str(agent_repo / "tools"))
        from savegen import generate_save as _generate_save

        if saves_dir is None:
            import sys as _sys
            if _sys.platform == "darwin":
                saves_dir = Path.home() / "Library/Application Support/RimWorld/Saves"
            elif _sys.platform == "win32":
                saves_dir = Path.home() / "AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios/Saves"
            else:
                saves_dir = Path.home() / ".config/unity3d/Ludeon Studios/RimWorld by Ludeon Studios/Saves"

        source = saves_dir / "Baseline-Starter.rws"
        if not source.exists():
            raise FileNotFoundError(f"Template save not found: {source}")

        output = saves_dir / f"{self.save_name()}.rws"

        _generate_save(
            source_path=str(source),
            output_path=str(output),
            map_size=self.map_size,
            terrain=self.terrain,
            mountains=self.mountains,
            water=self.water,
            trees=self.trees,
            tree_density=self.tree_density,
            keep_ruins=self.keep_ruins,
            temperature=self.temperature,
            seed=self.seed,
            berry_bushes=self.berry_bushes,
            keep_wildlife=self.keep_wildlife,
            starting_packs=self.starting_packs,
            wildlife_count=self.wildlife_count,
            starting_items=self.starting_items,
            completed_research=self.completed_research,
            wildlife_species=self.wildlife_species,
            wildlife_distribution=self.wildlife_distribution,
            ruins=self.ruins,
            ponds=self.ponds,
            mountain_side=self.mountain_side,
            mountain_resources=self.mountain_resources,
            grass=self.grass,
            grass_density=self.grass_density,
        )

        return output

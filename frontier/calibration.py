"""Pre-defined calibration scenarios spanning the difficulty space.

Phase 1: Run these to establish the initial capability frontier.
Each scenario varies one or two dimensions from baseline.
Challenge scenarios test specific gameplay skills with tuned scoring weights.
"""

from frontier.scenario import ScenarioConfig


# ── Challenge scenarios (skill-oriented, scored with weight overrides) ──

CHALLENGE_SCENARIOS = [
    ScenarioConfig(
        name="build_quality",
        terrain="Soil",
        temperature=20,
        tree_density=0.15,
    ),
    ScenarioConfig(
        name="mood_management",
        terrain="Soil",
        temperature=20,
    ),
    ScenarioConfig(
        name="research_sprint",
        terrain="Soil",
        temperature=20,
    ),
    ScenarioConfig(
        name="water_logistics",
        terrain="Soil",
        water="river",
        temperature=20,
    ),
    ScenarioConfig(
        name="food_pressure",
        terrain="Gravel",
        temperature=10,
        berry_bushes=0,
        trees=True,
        tree_density=0.03,
    ),
    ScenarioConfig(
        name="shelter_rush",
        terrain="Soil",
        temperature=-5,
    ),
    ScenarioConfig(
        name="resource_scarcity",
        terrain="Sand",
        trees=False,
        tree_density=0.0,
        temperature=30,
    ),
    ScenarioConfig(
        name="tight_space",
        terrain="Soil",
        mountains="ring",
        temperature=20,
    ),
    ScenarioConfig(
        name="self_sufficiency",
        terrain="SoilRich",
        temperature=20,
        berry_bushes=4,
    ),
    ScenarioConfig(
        name="balanced_hard",
        terrain="Gravel",
        mountains="corners",
        water="corners",
        temperature=5,
        tree_density=0.04,
    ),
]

# Baseline scenario
BASELINE = ScenarioConfig(
    name="baseline",
    terrain="Soil",
    temperature=20,
)

CALIBRATION_SCENARIOS = [BASELINE] + CHALLENGE_SCENARIOS


def get_scenario(name: str) -> ScenarioConfig | None:
    """Look up a calibration scenario by name."""
    for s in CALIBRATION_SCENARIOS:
        if s.name == name:
            return s
    return None

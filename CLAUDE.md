# RimWorld Playtest Harness — Agent Notes

The user-facing onboarding doc is `README.md`. This file is a short summary for Claude Code agents working in this repo.

## What this repo is

A playtest harness for RimWorld mod builders. The builder writes a scenario JSON declaring map setup + `pass_criteria` + `observe` questions; the harness runs RimWorld, drives gameplay with a fixed agent, and emits `playtest_report.md` per run.

The **agent that plays the game** lives in `$AGENT_REPO` (defaults to `../rimworld-tcp`), not here. This repo:

- Defines the scenario format (`frontier/scenario.py`)
- Orchestrates one run (`frontier/runner.sh`)
- Evaluates pass criteria (`frontier/criteria.py`)
- Spawns a reporter agent that writes the builder-facing report (`agents/run_reporter.sh`, `AGENT_REPORTER.md`)
- Provides batch + scaffolding tools (`frontier/playtest.sh`, `frontier/new_scenario.py`, `frontier/list_runs.py`)

The harness does NOT modify the agent's code or prompt — that lives in `$AGENT_REPO/AGENT_OVERSEER.md` and is the builder's stable, fixed component.

## Run flow (one scenario)

`runner.sh <scenario.json> <run_id>` phases:

1. `savegen` — generate `.rws` save via `$AGENT_REPO/tools/savegen.py`
2. `load_save` — load into running RimWorld via `RimClient` (TCP to Harmony mod)
3. `before_snapshot` — `take_snapshot()` → `before.json`
4. `smoke_test` — verify telemetry; start background `score_monitor.py`
5. `overseer` — spawn agent with `$AGENT_REPO/AGENT_OVERSEER.md` + scenario `mission_description`; agent drives via SDK
6. `after_snapshot` + `scoring` → `after.json`, `score.json` (if `scoring` rubric declared)
7. `charts` → `charts/*.png`
8. `criteria` — evaluate `pass_criteria` deterministically → `playtest_report.json`
9. `colony_map` → `colony_map.txt`
10. `reporter` — LLM agent reads artifacts, writes `playtest_report.md`

`playtest.sh <scenarios>` just iterates `runner.sh` per scenario and prints a summary table.

## Key files

- `frontier/scenario.py` — `ScenarioConfig` dataclass (every field a scenario can set)
- `frontier/criteria.py` — `CHECKERS` dict; add new criterion types here
- `frontier/runner.sh` — orchestrator; phase markers in `phases.jsonl`
- `frontier/scoring.py` — optional quantitative rubric (`_score_from_config()`)
- `agents/run_reporter.sh` + `AGENT_REPORTER.md` — the LLM that writes `playtest_report.md`
- `config.sh` — `AGENT_REPO`, `FRONTIER_DIR`, model selections, API keys

## Adding a new criterion type

1. Write `_check_<name>(run_dir, crit) -> tuple[bool, str]` in `frontier/criteria.py`.
2. Register in `CHECKERS`.
3. Document in `README.md`'s pass-criteria table.

## SDK quirks (from accumulated bug-finding)

- `RimClient` lives at `$AGENT_REPO/sdk/`; runner imports via `sys.path.insert`
- `colonists()` returns `{'colonists': [...]}`, not a flat list
- `build(blueprint, x, z)` — positional or `z=`, never `y=`
- Game state lookups in scoring use `after["colonists"]["colonists"]` and `after["resources"]`
- macOS has no GNU `timeout` — `runner.sh` uses background PID + kill polling
- See `$AGENT_REPO/REFERENCE_RIMWORLD.md` for the full list

## Things this harness intentionally does NOT do

- **No agent training.** The trainer/auditor/challenger system from earlier versions is gone. The agent prompt is fixed; this harness just exercises it.
- **No cross-run memory.** Each scenario is independent. We removed the `build_context.py` memory injection — a playtest should be reproducible, not biased by past runs.
- **No frontier classification.** Scenarios are pass/fail, not MASTERED/FRONTIER/IMPOSSIBLE. There's no scenario picker — the builder runs what they choose.

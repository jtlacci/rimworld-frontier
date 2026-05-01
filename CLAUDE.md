# RimWorld Playtest Harness — Agent Notes

The user-facing onboarding doc is `README.md`. This file is a short summary for Claude Code agents working in this repo.

## What this repo is

A playtest harness for RimWorld mod builders. Single repo containing the harness, the gameplay agent's prompt, the Python SDK, and the C# Harmony mod that the SDK talks to.

The builder writes a scenario JSON declaring map setup + `pass_criteria` + `observe` questions; the harness runs RimWorld, drives gameplay with a fixed agent, and emits `playtest_report.md` per run.

## Repo layout (one repo, no companion)

- `frontier/` — orchestrator code (scenario format, runner, criteria, scoring, scaffolding)
- `agents/` — reporter and background telemetry monitor
- `sdk/` — Python SDK (`RimClient`, `snapshot.py`, `timeline_scoring.py`, types)
- `tools/` — `savegen.py` (custom `.rws` builder), `read_state.py`
- `skills/` — pre-built scripts the overseer invokes (`bootstrap.py`, `hunt_all.py`, etc.)
- `schema/commands.json` — machine-readable TCP protocol schema (must stay in sync with `Source/GameBridge.cs`)
- `wiki/` — RimWorld game knowledge, QMD-indexed
- `Source/` — C# Harmony mod (Caroline Console)
- `About/About.xml` — RimWorld mod manifest
- `AGENT_OVERSEER.md` — the **fixed** prompt that drives gameplay; the harness reads it but does not modify it
- `AGENT_REPORTER.md` — reporter agent prompt
- `REFERENCE_RIMWORLD.md`, `REFERENCE_TOOLS.md`, `REFERENCE_WIKI.md` — reference docs
- `config.sh` — sets `FRONTIER_DIR`, model assignments, API config

## Run flow (one scenario)

`runner.sh <scenario.json> <run_id>` phases:

1. `savegen` — generate `.rws` save via `tools/savegen.py`
2. `load_save` — load into running RimWorld via `RimClient` (TCP to Harmony mod)
3. `before_snapshot` — `take_snapshot()` → `before.json`
4. `smoke_test` — verify telemetry; start background `score_monitor.py`
5. `overseer` — snapshots `AGENT_OVERSEER.md` into the run dir, then spawns the agent with that prompt + scenario `mission_description`; agent drives via SDK
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
- `config.sh` — `FRONTIER_DIR`, model selections, API keys

## Adding a new criterion type

1. Write `_check_<name>(run_dir, crit) -> tuple[bool, str]` in `frontier/criteria.py`.
2. Register in `CHECKERS`.
3. Document in `README.md`'s pass-criteria table.

## C# mod build & install

```bash
cd Source && dotnet build -c Release
# Mac: copy DLL into all 3 mod locations
cp Source/bin/Release/CarolineConsole.dll ~/Library/Application\ Support/Steam/steamapps/common/RimWorld/RimWorldMac.app/Mods/CarolineConsole/Assemblies/
cp Source/bin/Release/CarolineConsole.dll ~/Library/Application\ Support/Steam/steamapps/common/RimWorld/Mods/CarolineConsole/Assemblies/
cp Source/bin/Release/CarolineConsole.dll ~/Library/Application\ Support/RimWorld/Mods/CarolineConsole/Assemblies/
```

Game restart required after DLL changes. `schema/validate.py` verifies `GameBridge.cs` and `commands.json` stay in sync.

## SDK quirks (from accumulated bug-finding)

- `RimClient` lives at `sdk/`; runner imports via `sys.path.insert(0, "$FRONTIER_DIR/sdk")`
- `colonists()` returns `{'colonists': [...]}`, not a flat list
- `build(blueprint, x, z)` — positional or `z=`, never `y=`
- Game state lookups in scoring use `after["colonists"]["colonists"]` and `after["resources"]`
- macOS has no GNU `timeout` — `runner.sh` uses background PID + kill polling
- See `REFERENCE_RIMWORLD.md` for the full list

## Things this harness intentionally does NOT do

- **No agent training.** The trainer/auditor/challenger system from earlier versions is gone. The agent prompt is fixed; this harness just exercises it.
- **No cross-run memory.** Each scenario is independent. We removed the `build_context.py` memory injection — a playtest should be reproducible, not biased by past runs.
- **No frontier classification.** Scenarios are pass/fail, not MASTERED/FRONTIER/IMPOSSIBLE. There's no scenario picker — the builder runs what they choose.

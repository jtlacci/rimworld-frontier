# RimWorld Playtest Harness — Agent Notes

The user-facing onboarding doc is `README.md`. This file is a short summary for Claude Code agents working in this repo.

## What this repo is

A playtest harness for RimWorld mod builders. The builder writes a scenario JSON declaring map setup + `pass_criteria` + `observe` questions; Claude Code runs RimWorld via the harness scripts, drives gameplay with a Claude subagent (the **overseer**), and writes `playtest_report.md` per run.

## How playtests run now

The harness has no built-in LLM client. The overseer is a **Claude Code subagent** that you (the orchestrating Claude Code session) spawn via the Agent tool. The reporter is just you reading the artifacts and writing `playtest_report.md`. There is no DashScope / Qwen / external API anywhere in the loop.

A playtest is therefore **driven from a Claude Code session**, not from a cron job or shell wrapper. The user asks Claude Code to run a playtest; Claude Code orchestrates the phases.

### Phase orchestration

1. **`./frontier/runner_setup.sh <scenario.json> [run_id]`** — savegen → load → before_snapshot → smoke_test → starts background score_monitor. Emits a single JSON line to stdout with the paths the overseer needs (`result_dir`, `system_prompt_path`, `user_message_path`, `command_log`, `sdk_path`, `monitor_pid`, `game_day_limit`, `overseer_timeout_s`). All chatter goes to stderr.

2. **You spawn the overseer subagent** via the Agent tool (`subagent_type: general-purpose`):
   - System prompt: contents of `<result_dir>/overseer_system_prompt.md` (already includes `AGENT_OVERSEER.md` + scenario context + mission)
   - User message: contents of `<result_dir>/overseer_user_message.txt`
   - Tools: `Bash`, `Read`, `Write`
   - Set `RIM_SDK_LOG=<command_log>` and `SDK_PATH=<sdk_path>` in the agent's environment via the prompt (the prompt already references `$SDK_PATH`).
   - While it runs, poll `weather()['dayOfYear']` every ~30s. Stop the subagent if game day ≥ `game_day_limit` or wall clock ≥ `overseer_timeout_s`.

3. **`./frontier/runner_finish.sh <result_dir> [overseer_exit_code]`** — stops monitor → after_snapshot → scoring → timeline_analysis → charts → criteria → colony_map. Pass `124` as exit code if you stopped the overseer for the timeout/day-cap (it triggers an emergency save). Emits a JSON summary line to stdout.

4. **You write `playtest_report.md`** directly using `AGENT_REPORTER.md` as a guide. Read `playtest_report.json`, `score.json`, `timeline_analysis.json`, then grep `command_log.jsonl` / `score_timeline.jsonl` for failure evidence.

## Repo layout

- `frontier/` — phase scripts and Python orchestrators
  - `runner_setup.sh` — pre-overseer phases (0-2b)
  - `runner_finish.sh` — post-overseer phases (4-6)
  - `_analyze_timeline.py` — timeline diagnostics, called by runner_finish
  - `scenario.py`, `criteria.py`, `scoring.py` — config dataclass, pass/fail evaluator, optional rubric
  - `new_scenario.py`, `list_runs.py`, `summarize_run.py`, `timeline_charts.py`
  - `scenarios/` — scenario JSONs (commit these)
  - `results/` — per-run artifacts (gitignored)
- `agents/` — `score_monitor.py` (background telemetry), `listen.sh`/`listen_formatter.py` (live log viewer)
- `sdk/` — Python SDK (`RimClient`, `snapshot.py`, `timeline_scoring.py`, types)
- `tools/` — `savegen.py` (custom `.rws` builder), `read_state.py`
- `skills/` — pre-built scripts the overseer invokes (`bootstrap.py`, `hunt_all.py`, etc.)
- `schema/commands.json` — TCP protocol schema (must stay in sync with `Source/GameBridge.cs`)
- `wiki/` — RimWorld game knowledge, QMD-indexed
- `Source/` — C# Harmony mod (Caroline Console)
- `About/About.xml` — RimWorld mod manifest
- `AGENT_OVERSEER.md` — overseer subagent prompt; the harness copies it into the run dir, does not modify it
- `AGENT_REPORTER.md` — guide for writing `playtest_report.md`
- `REFERENCE_RIMWORLD.md`, `REFERENCE_TOOLS.md`, `REFERENCE_WIKI.md`
- `config.sh` — sets `FRONTIER_DIR`

## Running multiple scenarios (a "playtest loop")

There is no `playtest.sh` batch wrapper anymore. To run several scenarios, iterate yourself: for each scenario JSON, do setup → spawn overseer → finish → write report. Spawn separate Agent subagents per scenario so transcripts stay isolated.

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

- `RimClient` lives at `sdk/`; phase scripts import via `sys.path.insert(0, "$FRONTIER_DIR/sdk")`
- `colonists()` returns `{'colonists': [...]}`, not a flat list
- `build(blueprint, x, z)` — positional or `z=`, never `y=`
- Game state lookups in scoring use `after["colonists"]["colonists"]` and `after["resources"]`
- macOS has no GNU `timeout` — orchestrator uses background PID + kill polling
- See `REFERENCE_RIMWORLD.md` for the full list

## Things this harness intentionally does NOT do

- **No external LLM API.** The overseer is a Claude Code subagent. There is no DashScope / OpenAI / Anthropic-direct configuration to manage.
- **No standalone runner script.** Playtests require a Claude Code session to drive them — the overseer is a subagent, not a process you can fork from cron.
- **No agent training.** The trainer/auditor/challenger system from earlier versions is gone. The overseer prompt is fixed; this harness just exercises it.
- **No cross-run memory.** Each scenario is independent. We removed the `build_context.py` memory injection — a playtest should be reproducible, not biased by past runs.
- **No frontier classification.** Scenarios are pass/fail, not MASTERED/FRONTIER/IMPOSSIBLE. There's no scenario picker — the builder runs what they choose.

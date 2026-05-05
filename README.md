# RimWorld Playtest Harness

Automated playtesting for RimWorld mods.

You write a **scenario** describing what to test. The harness loads RimWorld with the right map and items, drives gameplay with a fixed agent, and emits a report telling you whether your mod did what you expected — and what broke if it didn't.

```
scenario.json  →  harness loads RimWorld  →  agent plays  →  pass/fail report
```

---

## Why this exists

Playtesting a mod by hand is slow. You launch RimWorld, set up a scenario, play for an hour, see whether your workbench got built and used, then start over when you change a def. This harness does the loop for you in ~20 minutes per scenario, and tells you — in plain language — what the agent observed.

The agent is fixed: it's the same gameplay-driving agent across all your scenarios. **You don't write or train an agent.** You write the test conditions and the success criteria.

---

## Requirements

- macOS, Linux, or Windows + RimWorld installed
- Python 3.11+
- .NET SDK (to build the Harmony mod under `Source/`)
- Claude Code (the harness drives playtests via a Claude subagent — no external LLM API)

---

## Install

```bash
# 1. Clone this repo
git clone <this-repo> rimworld-frontier
cd rimworld-frontier

# 2. Build and install the Harmony mod
cd Source && dotnet build -c Release && cd ..
# Copy Source/bin/Release/CarolineConsole.dll into your RimWorld Mods/CarolineConsole/Assemblies/
# (see CLAUDE.md for the platform-specific paths)
```

Verify by asking Claude Code in this directory: **"run a playtest on `example_mod_test`"**.

---

## The 3-step workflow

### 1. Scaffold a scenario

```bash
python3 frontier/new_scenario.py my_workbench_test \
    --mod-id Foo.MyMod --mod-name "My Mod"
```

Creates `frontier/scenarios/my_workbench_test.json` with sensible defaults. Edit it to describe your test.

### 2. Run it

Ask Claude Code: **"run a playtest on `my_workbench_test`"** (or a list of scenarios for a loop).

Claude Code orchestrates the phases: it runs `./frontier/runner_setup.sh`, spawns a subagent as the **overseer** (which drives RimWorld via the SDK), then runs `./frontier/runner_finish.sh` and writes `playtest_report.md` itself.

Each run produces artifacts at `frontier/results/<scenario>/run_NNN/`.

### 3. Review the report

```bash
# List the latest result of every scenario:
python3 frontier/list_runs.py

# Drill into one scenario:
python3 frontier/list_runs.py my_workbench_test

# Read the human-friendly report directly:
cat frontier/results/my_workbench_test/run_001/playtest_report.md
```

---

## Writing a scenario

A scenario is a single JSON file. The minimum useful shape:

```json
{
  "name": "my_workbench_test",
  "map_size": 50,
  "terrain": "SoilRich",
  "starting_packs": 10,
  "starting_items": {"Steel": 1000, "WoodLog": 300},
  "completed_research": ["ComplexFurniture"],

  "mission_description": "Build a small colony, then build and use the workbench from MyMod.",

  "mod_under_test": {
    "id": "Foo.MyMod",
    "name": "My Mod"
  },

  "pass_criteria": [
    {"name": "no_red_errors",  "type": "no_red_errors"},
    {"name": "all_alive",      "type": "all_colonists_alive"},
    {"name": "workbench_built","type": "thing_exists", "def": "MyMod_Workbench"},
    {"name": "steel_used",     "type": "resource_at_least", "resource": "Steel", "min": 100},
    {"name": "ai_engaged",     "type": "custom",
     "description": "The agent should attempt to assign at least one bill to MyMod_Workbench."}
  ],

  "observe": [
    "Did colonists interact with MyMod_Workbench, or did they ignore it?",
    "Did any mod-added research entries appear and become selectable?"
  ]
}
```

See `frontier/scenarios/example_mod_test.json` for the working template, and `frontier/scenario.py` for every supported field.

### Pass criteria types

| Type | Required fields | What it checks |
|---|---|---|
| `no_red_errors` | — | No SDK errors and no Verse-style exceptions surfaced during the run |
| `all_colonists_alive` | — | Same number of colonists alive at end as at start |
| `thing_exists` | `def` | At least one Thing of `def` exists at end of run |
| `resource_at_least` | `resource`, `min` | Final stockpile of `resource` ≥ `min` |
| `custom` | `description` | Plain-English — deferred to the reporter; the batch status is `REVIEW` until a human reads the report |

Add more types in `frontier/criteria.py` (the `CHECKERS` dict).

### Observe questions

`observe` is a list of plain-English questions the reporter answers using run evidence. Use these for things that are hard to express as a deterministic check ("did colonists path-find around the new tile?", "did the new research show up in the tab?"). You'll get a direct answer with citations.

### Optional: scoring rubric

If you want quantitative scoring on top of pass/fail (useful for measuring mod balance), declare a `scoring` block. See `frontier/scoring.py:_score_from_config()` for supported metric types.

---

## Reading a report

After a run, the most useful files are at `frontier/results/<scenario>/run_NNN/`:

| File | What it is |
|---|---|
| `playtest_report.md` | **Builder-facing summary** — pass/fail, what broke, answers to your observe questions, suggested next steps |
| `playtest_report.json` | Machine-readable pass/fail per criterion |
| `score.json` | Quantitative score (if you declared a `scoring` rubric) |
| `overseer_conversation.txt` | Full transcript of what the agent thought and did |
| `command_log.jsonl` | Every SDK call the agent made — useful for diagnosing "agent tried X but it failed" |
| `score_timeline.jsonl` | Periodic colony-state snapshots during the run |
| `colony_map.txt` | ASCII map of the colony at end of run |
| `before.json` / `after.json` | Full colony state snapshots |
| `charts/*.png` | Observability charts (if matplotlib is available) |

The agent-written report (`playtest_report.md`) is the primary artifact. It's structured: pass/fail table, observation answers, what broke, suggested next steps.

---

## Tools cheat sheet

```bash
# Scaffold a new scenario:
python3 frontier/new_scenario.py <name> [--mod-id ...] [--mod-name ...]

# List all runs (latest per scenario):
python3 frontier/list_runs.py

# Drill into one scenario's run history:
python3 frontier/list_runs.py <name>
```

To run scenarios, ask Claude Code from a session in this directory.

---

## How it works (one paragraph)

`runner_setup.sh` does the deterministic setup for one scenario: it generates a save (via `tools/savegen.py`), loads it into a running RimWorld instance, snapshots colony state, and kicks off a 5-second-interval telemetry monitor. It then prints a JSON line with paths Claude Code uses to spawn an **overseer subagent** — fed `AGENT_OVERSEER.md` plus your `mission_description` — that plays the game for up to ~22 minutes wall-clock or 5 in-game days. When the subagent finishes, `runner_finish.sh` snapshots the final state, scores the run, evaluates `pass_criteria` deterministically, captures the colony map, and Claude Code itself writes `playtest_report.md` using `AGENT_REPORTER.md` as a guide.

For more architectural detail, see `CLAUDE.md`.

---

## Troubleshooting

- **Overseer subagent runs but does nothing useful** — check `command_log.jsonl` for the SDK calls it actually made. It may have hit an SDK error early.
- **Scenario fails with "TODO" in mission_description** — you forgot to fill in the scaffold. Edit the JSON.
- **`thing_exists` always fails** — the def name in your scenario must match the def the mod actually registers (case-sensitive). Check `command_log.jsonl` for the agent's attempted operations.
- **RimWorld won't connect over TCP** — make sure the Caroline Console mod is enabled in RimWorld's mods list and the game is on the main menu or in a save.

---

## Repo layout

```
frontier/
  runner_setup.sh       phases 0-2b (savegen → snapshot → start monitor)
  runner_finish.sh      phases 4-6 (snapshot → score → criteria → map)
  _analyze_timeline.py  timeline diagnostics
  new_scenario.py       scaffold a new scenario
  list_runs.py          review run history
  criteria.py           pass/fail evaluator
  scoring.py            optional quantitative scoring
  scenario.py           ScenarioConfig dataclass
  scenarios/            scenarios you've written (commit these)
  results/              per-run artifacts (gitignored)

agents/
  score_monitor.py      background telemetry monitor
  listen.sh             live log viewer for active runs

sdk/                    Python SDK — RimClient, snapshot, scoring
tools/                  savegen.py (custom .rws builder), read_state.py
skills/                 Pre-built scripts the overseer invokes
schema/                 commands.json (machine-readable protocol)
wiki/                   RimWorld game knowledge (QMD-indexed)
Source/                 C# Harmony mod (build with dotnet)
About/                  RimWorld mod metadata

AGENT_OVERSEER.md       overseer subagent prompt (drives gameplay)
AGENT_REPORTER.md       guide for writing playtest_report.md
REFERENCE_*.md          SDK/wiki/RimWorld reference docs
config.sh               sets FRONTIER_DIR
CLAUDE.md               orchestration notes for Claude Code
```

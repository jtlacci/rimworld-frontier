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
- A DashScope API key for the Qwen-based overseer/reporter agents

---

## Install

```bash
# 1. Clone this repo
git clone <this-repo> rimworld-frontier
cd rimworld-frontier

# 2. Install Python deps
pip install openai anthropic

# 3. Build and install the Harmony mod
cd Source && dotnet build -c Release && cd ..
# Copy Source/bin/Release/CarolineConsole.dll into your RimWorld Mods/CarolineConsole/Assemblies/
# (see CLAUDE.md for the platform-specific paths)

# 4. Set your API key
export DASHSCOPE_API_KEY=sk-...
```

Verify by running the bundled example:

```bash
./frontier/run_scenario.sh example_mod_test
```

---

## The 3-step workflow

### 1. Scaffold a scenario

```bash
python3 frontier/new_scenario.py my_workbench_test \
    --mod-id Foo.MyMod --mod-name "My Mod"
```

Creates `frontier/scenarios/my_workbench_test.json` with sensible defaults. Edit it to describe your test.

### 2. Run it

```bash
./frontier/run_scenario.sh my_workbench_test
# or, run a batch:
./frontier/playtest.sh frontier/scenarios/*.json
```

Each run produces artifacts at `frontier/results/<scenario>/run_NNN/`. The console prints a one-line pass/fail summary.

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

# Run a single scenario:
./frontier/run_scenario.sh <name> [run_id]

# Run a batch and get a pass/fail table:
./frontier/playtest.sh frontier/scenarios/*.json

# List all runs (latest per scenario):
python3 frontier/list_runs.py

# Drill into one scenario's run history:
python3 frontier/list_runs.py <name>
```

---

## How it works (one paragraph)

`runner.sh` orchestrates phases for one scenario: it generates a save (via `tools/savegen.py`), loads it into a running RimWorld instance, snapshots colony state, kicks off a 5-second-interval telemetry monitor, spawns the **overseer agent** (driven by `AGENT_OVERSEER.md` plus your `mission_description`) to play the game for up to ~22 minutes wall-clock or 5 in-game days, snapshots final state, evaluates `pass_criteria` deterministically, then spawns the **reporter agent** to write `playtest_report.md` from the artifacts. `playtest.sh` just runs `runner.sh` per scenario in a list and prints a summary table.

For more architectural detail, see `CLAUDE.md`.

---

## Troubleshooting

- **"DASHSCOPE_API_KEY not set"** — required for the Qwen-based agents. Get one from Alibaba Cloud DashScope.
- **Agent runs but does nothing useful** — check `overseer_conversation.txt` for the agent's reasoning. It may have hit an SDK error early.
- **Scenario fails with "TODO" in mission_description** — you forgot to fill in the scaffold. Edit the JSON.
- **`thing_exists` always fails** — the def name in your scenario must match the def the mod actually registers (case-sensitive). Check `command_log.jsonl` for the agent's attempted operations.

---

## Repo layout

```
frontier/
  runner.sh             single-scenario runner
  run_scenario.sh       run by name
  playtest.sh           batch runner with pass/fail table
  new_scenario.py       scaffold a new scenario
  list_runs.py          review run history
  criteria.py           pass/fail evaluator
  scoring.py            optional quantitative scoring
  scenario.py           ScenarioConfig dataclass
  scenarios/            scenarios you've written (commit these)
  results/              per-run artifacts (gitignored)

agents/
  run_reporter.sh       reporter agent invocation
  score_monitor.py      background telemetry monitor

sdk/                    Python SDK — RimClient, snapshot, scoring
tools/                  savegen.py (custom .rws builder), read_state.py
skills/                 Pre-built scripts the overseer invokes
schema/                 commands.json (machine-readable protocol)
wiki/                   RimWorld game knowledge (QMD-indexed)
Source/                 C# Harmony mod (build with dotnet)
About/                  RimWorld mod metadata

AGENT_OVERSEER.md       overseer agent prompt (the one driving gameplay)
AGENT_REPORTER.md       reporter agent prompt
REFERENCE_*.md          SDK/wiki/RimWorld reference docs
config.sh               environment paths + model assignments
CLAUDE.md               architecture summary for Claude Code agents
```

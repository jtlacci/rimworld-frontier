# RimWorld Frontier — Training Harness

Training infrastructure that evaluates and improves a RimWorld agent-playing mod.
The agent code lives in a separate repo (`rimworld-tcp` / `rimworld-agent`).

## Architecture

```
┌─────────────────────────────────────────────┐
│  AUDITOR (Opus, persistent conversation)    │
│  Reviews batch results, fixes SDK/C#/prompt │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│  TRAIN LOOP (frontier/train.sh N)           │
│  Auto-selects scenarios, runs N, summarizes │
│                                             │
│  For each run:                              │
│    Scenario config → savegen → runner →     │
│    overseer plays → monitor captures →      │
│    score → charts → classify                │
└──────────┬──────────────────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌────────┐  ┌──────────────┐
│OVERSEER│  │SCORE MONITOR │
│(Sonnet)│  │(20s snapshots)│
│plays   │  │needs, jobs,  │
│via SDK │  │resources,    │
│        │  │wealth, mood  │
└────────┘  └──────────────┘
```

## Repo Split

This is the **training harness**. The **agent** (product being trained) lives at `$AGENT_REPO`.

### This repo (rimworld-frontier)
- Training loop, scoring, scenario management, failure analysis
- Agent orchestration scripts (auditor, trainer, challenger, evaluator)
- Run results, charts, frontier state
- Agent prompts (AGENT_AUDITOR.md, AGENT_TRAINER.md, AGENT_CHALLENGER.md)

### Agent repo ($AGENT_REPO)
- C# Harmony mod (Source/) — TCP bridge, game commands
- Python SDK (sdk/) — RimClient, snapshot, scoring
- Overseer prompt (AGENT_OVERSEER.md)
- Save generator (tools/savegen.py)
- Reference docs (REFERENCE_RIMWORLD.md, REFERENCE_WIKI.md)

### Configuration

All scripts source `config.sh` which sets:
- `FRONTIER_DIR` — root of this repo (auto-detected)
- `AGENT_REPO` — root of the agent repo (defaults to `../rimworld-tcp`, override with env var)

```bash
# Override agent repo location:
export AGENT_REPO=/path/to/rimworld-agent
```

### Boundary

| Question | Answer |
|----------|--------|
| Trainer commits where? | Agent repo only |
| Auditor reads from where? | Both (agent for code, frontier for results) |
| Challenger writes where? | Frontier repo (scenarios/) |
| Runner lives where? | Frontier repo (orchestrates both) |
| Score monitor lives where? | Frontier repo (uses agent SDK) |
| Scoring/tracker lives where? | Frontier repo |
| Results stored where? | Frontier repo |
| C# changes? | Agent repo (trainer modifies) |
| SDK changes? | Agent repo (trainer modifies) |

## Quick Start

```bash
# Single scenario run
./frontier/runner.sh frontier/scenarios/baseline.json 1

# Run by name (auto-finds config)
./frontier/run_scenario.sh baseline 1

# Analyze results (produces audit.json)
./agents/run_auditor.sh frontier/results/baseline/run_001

# Apply fixes from audit (commits to AGENT_REPO)
./agents/run_trainer.sh frontier/results/baseline/run_001/audit.json

# Run eval set to check for regressions
./agents/run_evaluator.sh

# Auto-loop: run N scenarios, pick frontiers automatically
./frontier/train.sh 5
```

## Project Structure

```
config.sh                      # AGENT_REPO + FRONTIER_DIR paths

agents/
  run_auditor.sh               # Deep failure investigation (opus, read-only)
  run_trainer.sh               # Apply fixes from audit (opus, writes to agent repo)
  run_challenger.sh            # Generate stress-test scenarios (sonnet)
  run_evaluator.sh             # Regression check across eval set
  listen.sh                    # Real-time event listener
  listen_formatter.py          # Event formatter
  score_monitor.py             # Background monitor (20s telemetry snapshots)

frontier/
  train.sh                     # Auto-loop: select scenarios, run batch, summarize
  runner.sh                    # Single scenario runner (savegen → overseer → score → charts)
  run_scenario.sh              # Run by name helper
  run_calibration.sh           # Run all calibration scenarios
  log_event.sh                 # Event logging utility
  scenario.py                  # ScenarioConfig dataclass
  scoring.py                   # Scenario-adaptive scoring (weight adjustments)
  tracker.py                   # Frontier state (MASTERED/FRONTIER/IMPOSSIBLE per scenario)
  analyzer.py                  # Failure categorization
  timeline_charts.py           # 10 observability charts
  visualize.py                 # ASCII heatmap of capability frontier
  generator.py                 # Scenario generator
  calibration.py               # Calibration scenarios
  scenarios/                   # Scenario configs (JSON)
  summarize_run.py             # Generate run_summary.md for QMD indexing
  results/<scenario>/run_NNN/  # Per-run artifacts (see Run Artifacts below)
  frontier_state.json          # Scenario classification state

AGENT_AUDITOR.md               # Auditor prompt — failure investigation
AGENT_TRAINER.md               # Trainer prompt — code fixes + strategy updates
AGENT_CHALLENGER.md            # Challenger prompt — stress-test scenario design
SCENARIO_*.md                  # Mission specs for specific scenarios
```

## Scoring (~153 points base + open-ended)

Colony livability (shelter, food, impressiveness) dominates. Efficiency/meta metrics are low-weight.

| Category | Pts | Key Metrics |
|----------|-----|-------------|
| Survival | 16 | alive (5), not_downed (2), food_safety (6), temp_safety (3) |
| **Needs** | **26** | **shelter (10)**, stockpiles (1), **self_sufficiency (15)** |
| Infra | 24 | bedrooms (6), storage_room (3), production_throughput (8+), queue_health (2), no_deterioration (2), research_progress (3) |
| **Quality** | **43** | **building_progress (15+)**, **avg_beauty (8)**, **avg_impressiveness (20)** |
| Wellbeing | 10 | avg_mood (3), worst_mood (1), no_breaks (1), quality_of_life (5) |
| Efficiency | 9 | game_progress (3), time_efficiency (2), token_efficiency (3), no_sub_errors (1) |
| Errors | 2 | unresolved_alerts (2) |
| **Timeline** | **23** | **need_sustained (10)**, progress_pace (5), food_trajectory (5), workforce_usage (3) |

## Frontier System

Scenarios are classified by performance:
- **TOO_EASY** (>=95%) — skip, not useful for training
- **MASTERED** (85-95%) — solved, use for regression testing
- **FRONTIER** (50-85%) — the learning edge, run these
- **IMPOSSIBLE** (<50%) — blocked, needs SDK/mechanical fixes first

## Workflow

```
1. RUN:          ./frontier/runner.sh <scenario.json> <run_id>
2. REVIEW:       Read score, timeline issues, charts, food pipeline diagnostics
3. DIAGNOSE:     ./agents/run_auditor.sh <result_dir>
4. FIX:          ./agents/run_trainer.sh <audit.json>  (commits to agent repo)
5. VERIFY:       Re-run same scenario to validate fixes
6. REVERT:       cd $AGENT_REPO && git revert HEAD  (if score regressed)
7. STRESS TEST:  ./agents/run_challenger.sh <scenario.json>
8. REPEAT
```

### Trainer Rollback Policy

The trainer commits to the **agent repo**. After it commits, re-run the same scenario.
Only revert on **major regressions** (>10pt drop or new colonist deaths).
Minor regressions (<5pts) are acceptable if the failure profile improved.

```bash
# Review what trainer changed:
cd $AGENT_REPO && git diff HEAD~1

# Revert if score dropped:
cd $AGENT_REPO && git revert HEAD
```

## Run Artifacts

Each run at `results/<scenario>/run_NNN/` produces:

| File | Source | Description |
|------|--------|-------------|
| `score.json` | scoring | Final score breakdown |
| `score_timeline.jsonl` | score_monitor | 20s telemetry snapshots |
| `command_log.jsonl` | SDK (RimClient) | Every SDK command with args, timing, success/error |
| `phases.jsonl` | runner.sh | Phase start/end timestamps |
| `overseer_conversation.txt` | runner.sh | Full overseer output |
| `before.json` / `after.json` | runner.sh | Colony state snapshots |
| `audit.json` | run_auditor.sh | Failure chains, execution gaps, recommendations |
| `trainer_changelog.json` | run_trainer.sh | Structured list of code changes and issue addressed |
| `run_summary.md` | summarize_run.py | QMD-indexed summary of all above |
| `charts/*.png` | timeline_charts.py | 10 observability charts |

## Run History Search (QMD)

`run_summary.md` is auto-generated after each run (and regenerated after audits/trainer fixes) with: score breakdown, phase durations, timeline trends (food/buildings/mood arcs), SDK call stats (error rates, top commands), audit findings, and trainer changes. Indexed by QMD for semantic search.

```bash
# Search across all runs
qmd query "cooking bill failures" -c frontier-runs
qmd query "runs where food dropped mid-game" -c frontier-runs
qmd query "high SDK error rate" -c frontier-runs
qmd query "what fixes were tried for shelter" -c frontier-runs

# Re-index after manual changes
qmd update && qmd embed
```

## Key Gotchas

- `build(blueprint, x, z)` — use positional args or `z=` keyword, NOT `y=`
- `colonists()` returns `{'colonists': [...]}` not a flat list
- macOS has no GNU `timeout` — scripts use background PID + kill polling
- `--output-format stream-json` — timeout kills lose usage data
- See $AGENT_REPO/REFERENCE_RIMWORLD.md for full list

#!/usr/bin/env python3
"""List playtest runs and their pass/fail status.

By default: prints a table of the latest run per scenario.
With --all: prints every run.
With <scenario_name>: prints all runs for that scenario, with criterion details.

Usage:
    python3 frontier/list_runs.py
    python3 frontier/list_runs.py --all
    python3 frontier/list_runs.py my_workbench_test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_report(run_dir: Path) -> dict | None:
    p = run_dir / "playtest_report.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def iter_runs(scenario_dir: Path):
    """Yield (run_id_int, run_dir) sorted ascending."""
    if not scenario_dir.is_dir():
        return
    runs = []
    for d in scenario_dir.iterdir():
        if d.is_dir() and d.name.startswith("run_"):
            try:
                rid = int(d.name.split("_", 1)[1])
                runs.append((rid, d))
            except ValueError:
                continue
    runs.sort(key=lambda x: x[0])
    yield from runs


def status_marker(status: str) -> str:
    return {
        "pass": "PASS",
        "fail": "FAIL",
        "review": "REVIEW",
        "no_criteria": "—",
    }.get(status, status.upper())


def print_summary(results_dir: Path, show_all: bool) -> int:
    if not results_dir.is_dir():
        print(f"No runs found at {results_dir}", file=sys.stderr)
        return 0

    scenarios = sorted([d for d in results_dir.iterdir() if d.is_dir()])
    if not scenarios:
        print(f"No runs found at {results_dir}", file=sys.stderr)
        return 0

    rows = []
    for sc_dir in scenarios:
        runs = list(iter_runs(sc_dir))
        if not runs:
            continue
        if show_all:
            for rid, run_dir in runs:
                report = load_report(run_dir)
                rows.append((sc_dir.name, rid, report))
        else:
            rid, run_dir = runs[-1]
            report = load_report(run_dir)
            rows.append((sc_dir.name, rid, report))

    if not rows:
        print("No completed runs found.")
        return 0

    print(f"{'SCENARIO':<30} {'RUN':>4}  {'STATUS':<6}  {'CRITERIA':>10}  REPORT")
    print(f"{'─' * 30} {'───':>4}  {'──────':<6}  {'──────────':>10}  {'──────'}")
    for name, rid, report in rows:
        if report is None:
            print(f"{name:<30} {rid:>4}  {'?':<6}  {'—':>10}  (no playtest_report.json)")
            continue
        s = report.get("summary", {})
        crit = f"{s.get('pass', 0)}/{s.get('total', 0)}"
        status = status_marker(report.get("overall", "?"))
        md = f"frontier/results/{name}/run_{rid:03d}/playtest_report.md"
        print(f"{name:<30} {rid:>4}  {status:<6}  {crit:>10}  {md}")
    return 0


def print_scenario_detail(results_dir: Path, scenario: str) -> int:
    sc_dir = results_dir / scenario
    if not sc_dir.is_dir():
        print(f"No runs for scenario '{scenario}' at {sc_dir}", file=sys.stderr)
        return 1

    runs = list(iter_runs(sc_dir))
    if not runs:
        print(f"No runs for scenario '{scenario}'", file=sys.stderr)
        return 1

    print(f"Scenario: {scenario}")
    print(f"Runs: {len(runs)}")
    print()

    for rid, run_dir in runs:
        report = load_report(run_dir)
        if report is None:
            print(f"run_{rid:03d}: (no playtest_report.json)")
            continue
        s = report.get("summary", {})
        status = status_marker(report.get("overall", "?"))
        print(f"run_{rid:03d}: {status} ({s.get('pass', 0)}/{s.get('total', 0)} pass, {s.get('fail', 0)} fail, {s.get('deferred', 0)} deferred)")
        for c in report.get("criteria", []):
            mark = {"pass": "+", "fail": "-", "deferred": "?", "error": "!"}.get(c.get("status", ""), "?")
            print(f"  [{mark}] {c.get('name', '?')}: {c.get('detail', '')}")
        md = run_dir / "playtest_report.md"
        if md.exists():
            print(f"  → {md.relative_to(results_dir.parent.parent)}")
        print()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("scenario", nargs="?", help="If given, show full detail for this scenario")
    p.add_argument("--all", action="store_true", help="Show every run, not just the latest per scenario")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    results_dir = repo_root / "frontier" / "results"

    if args.scenario:
        return print_scenario_detail(results_dir, args.scenario)
    return print_summary(results_dir, args.all)


if __name__ == "__main__":
    sys.exit(main())

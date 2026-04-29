"""Pass/fail criteria evaluation for playtest scenarios.

A scenario JSON declares `pass_criteria` as a list of typed checks. After a run
completes, this module evaluates each criterion against the run artifacts and
emits playtest_report.json with a structured pass/fail result per criterion.

Supported criterion types:
    - no_red_errors        — no Verse.Log "Error" lines surfaced during the run
    - all_colonists_alive  — same number of colonists alive at end as at start
    - thing_exists         — at least one Thing of `def` exists at end of run
    - resource_at_least    — final stockpile of `resource` >= `min`
    - custom               — free-text `description`; reporter agent judges it

Each criterion entry:
    {
        "name": "human-readable label",
        "type": "no_red_errors" | ...,
        "def": "MyMod_Workbench",       # for thing_exists
        "resource": "Steel",             # for resource_at_least
        "min": 100,                      # for resource_at_least
        "description": "..."             # for custom (passed to reporter agent)
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _check_no_red_errors(run_dir: Path, _crit: dict) -> tuple[bool, str]:
    """Pass if no Verse error lines were captured during the run.

    Looks at command_log.jsonl for SDK errors and overseer_conversation.txt for
    Verse-style "Exception" / "Error in" lines.
    """
    cmds = _load_jsonl(run_dir / "command_log.jsonl")
    sdk_errors = [c for c in cmds if c.get("error") or c.get("success") is False]

    convo = run_dir / "overseer_conversation.txt"
    verse_errors = 0
    if convo.exists():
        for line in convo.read_text(errors="replace").splitlines():
            low = line.lower()
            if "exception" in low or "error in " in low or "verse.log_error" in low:
                verse_errors += 1

    total = len(sdk_errors) + verse_errors
    if total == 0:
        return True, "no errors observed"
    return False, f"{len(sdk_errors)} SDK errors, {verse_errors} verse-style errors"


def _check_all_colonists_alive(run_dir: Path, _crit: dict) -> tuple[bool, str]:
    before = _load_json(run_dir / "before.json") or {}
    after = _load_json(run_dir / "after.json") or {}
    bc = len(before.get("colonists", {}).get("colonists", []))
    ac = len(after.get("colonists", {}).get("colonists", []))
    return ac >= bc and bc > 0, f"{ac}/{bc} alive"


def _check_thing_exists(run_dir: Path, crit: dict) -> tuple[bool, str]:
    """Pass if any Thing with the given def is present at end of run.

    Searches after.json for things in:
        - after["things"]            (flat list)
        - after["buildings"]         (snapshot building list)
        - score timeline last entry's "buildings" or "rooms"
    """
    target = crit.get("def")
    if not target:
        return False, "no `def` specified in criterion"

    after = _load_json(run_dir / "after.json") or {}

    candidates: list[dict] = []
    candidates.extend(_iter_things(after.get("things")))
    candidates.extend(_iter_things(after.get("buildings")))

    timeline = _load_jsonl(run_dir / "score_timeline.jsonl")
    if timeline:
        last = timeline[-1]
        candidates.extend(_iter_things(last.get("buildings")))
        candidates.extend(_iter_things(last.get("things")))

    for thing in candidates:
        if not isinstance(thing, dict):
            continue
        def_name = thing.get("def") or thing.get("defName") or thing.get("def_name")
        if def_name == target:
            return True, f"found {target}"

    return False, f"{target} not found in run artifacts"


def _iter_things(value: Any) -> list[dict]:
    if not value:
        return []
    if isinstance(value, list):
        return [t for t in value if isinstance(t, dict)]
    if isinstance(value, dict):
        out = []
        for v in value.values():
            if isinstance(v, dict):
                out.append(v)
            elif isinstance(v, list):
                out.extend(t for t in v if isinstance(t, dict))
        return out
    return []


def _check_resource_at_least(run_dir: Path, crit: dict) -> tuple[bool, str]:
    resource = crit.get("resource")
    minimum = crit.get("min", 0)
    if not resource:
        return False, "no `resource` specified in criterion"
    after = _load_json(run_dir / "after.json") or {}
    val = after.get("resources", {}).get(resource, 0)
    ok = val >= minimum
    return ok, f"{resource}={val} (need >={minimum})"


CHECKERS = {
    "no_red_errors": _check_no_red_errors,
    "all_colonists_alive": _check_all_colonists_alive,
    "thing_exists": _check_thing_exists,
    "resource_at_least": _check_resource_at_least,
}


def evaluate(run_dir: Path, criteria: list[dict]) -> dict:
    """Evaluate every criterion. Returns a dict suitable for playtest_report.json.

    `custom` criteria are NOT evaluated here — they're returned with status
    "deferred" and handed off to the reporter agent for qualitative judgment.
    """
    results = []
    pass_count = 0
    fail_count = 0
    deferred_count = 0

    for crit in criteria:
        name = crit.get("name") or crit.get("type", "unnamed")
        ctype = crit.get("type", "")

        if ctype == "custom":
            results.append({
                "name": name,
                "type": ctype,
                "status": "deferred",
                "detail": crit.get("description", ""),
            })
            deferred_count += 1
            continue

        checker = CHECKERS.get(ctype)
        if checker is None:
            results.append({
                "name": name,
                "type": ctype,
                "status": "error",
                "detail": f"unknown criterion type: {ctype}",
            })
            fail_count += 1
            continue

        ok, detail = checker(run_dir, crit)
        results.append({
            "name": name,
            "type": ctype,
            "status": "pass" if ok else "fail",
            "detail": detail,
        })
        if ok:
            pass_count += 1
        else:
            fail_count += 1

    overall = "pass" if fail_count == 0 and pass_count > 0 else ("fail" if fail_count > 0 else "no_criteria")

    return {
        "overall": overall,
        "summary": {
            "pass": pass_count,
            "fail": fail_count,
            "deferred": deferred_count,
            "total": len(criteria),
        },
        "criteria": results,
    }


def write_report(run_dir: Path, criteria: list[dict]) -> dict:
    report = evaluate(run_dir, criteria)
    (run_dir / "playtest_report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    import sys
    from .scenario import ScenarioConfig

    if len(sys.argv) != 3:
        print("Usage: python -m frontier.criteria <run_dir> <scenario.json>", file=sys.stderr)
        sys.exit(2)

    run_dir = Path(sys.argv[1])
    scenario = ScenarioConfig.load(Path(sys.argv[2]))
    report = write_report(run_dir, scenario.pass_criteria or [])
    print(json.dumps(report, indent=2))

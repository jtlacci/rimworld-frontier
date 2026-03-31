#!/usr/bin/env python3
"""Build run context: recent history, confirmed lessons, trainer changes.

Generates a compact text block to inject into agent prompts so they
don't need to search QMD for memory.

Usage: python3 build_context.py <scenario_dir> [current_run_id]
"""
import json, os, sys, glob


def build_context(scenario_dir, current_run=None):
    lines = []

    # Find recent runs
    run_dirs = sorted(glob.glob(os.path.join(scenario_dir, "run_*")))
    if current_run:
        run_dirs = [d for d in run_dirs if int(os.path.basename(d).replace("run_", "")) < current_run]
    recent = run_dirs[-5:]  # last 5 runs

    # Score history
    if recent:
        lines.append("## Recent Score History")
        for d in recent:
            run_id = os.path.basename(d)
            score_path = os.path.join(d, "score.json")
            if os.path.exists(score_path):
                s = json.load(open(score_path))
                lines.append(f"  {run_id}: {s.get('pct', 0):.1f}%")
        lines.append("")

    # Last trainer change
    if recent:
        for d in reversed(recent):
            cl_path = os.path.join(d, "trainer_changelog.json")
            if os.path.exists(cl_path):
                cl = json.load(open(cl_path))
                lines.append("## Last Trainer Change")
                lines.append(f"  Issue: {cl.get('issue_addressed', '?')}")
                for c in cl.get("changes", [])[:3]:
                    lines.append(f"  - {c.get('file', '?')}: {c.get('description', '?')[:100]}")
                lines.append("")
                break

    # Last audit findings
    if recent:
        for d in reversed(recent):
            findings_path = os.path.join(d, "audit_findings.md")
            if os.path.exists(findings_path):
                text = open(findings_path).read().strip()
                if text and len(text) > 20:
                    lines.append("## Last Audit Findings (summary)")
                    # Take first 500 chars
                    lines.append(text[:500])
                    if len(text) > 500:
                        lines.append("  ...")
                    lines.append("")
                    break

    # Confirmed lessons (capped at 50 lines to prevent prompt bloat)
    lessons_path = os.path.join(os.path.dirname(scenario_dir), "..", "LESSONS.md")
    if os.path.exists(lessons_path):
        lesson_lines = open(lessons_path).read().strip().splitlines()[:50]
        if lesson_lines:
            lines.append("## Confirmed Lessons (verified across runs)")
            lines.extend(lesson_lines)
            if len(open(lessons_path).readlines()) > 50:
                lines.append("  ... (truncated at 50 lines)")
            lines.append("")

    # Total output cap — 2000 chars max
    result = "\n".join(lines)
    if len(result) > 2000:
        result = result[:2000] + "\n... (memory truncated)"

    return result


if __name__ == "__main__":
    scenario_dir = sys.argv[1]
    current_run = int(sys.argv[2]) if len(sys.argv) > 2 else None
    print(build_context(scenario_dir, current_run))

#!/usr/bin/env python3
"""Generate run_summary.md from run artifacts for QMD indexing.

Extracts narrative content from score.json, audit.json, and
overseer_conversation.txt into a single searchable markdown file.

Usage: python3 frontier/summarize_run.py <result_dir>
"""

import json
import os
import sys


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def summarize(result_dir):
    lines = []

    # --- Header ---
    scenario = load_json(os.path.join(result_dir, "scenario.json"))
    score = load_json(os.path.join(result_dir, "score.json"))

    name = scenario.get("name", "unknown") if scenario else "unknown"
    run_id = os.path.basename(result_dir)

    lines.append(f"# {name} — {run_id}\n")

    # --- Score ---
    if score:
        pct = score.get("pct", 0)
        total = score.get("total", 0)
        max_score = score.get("max", 0)
        lines.append(f"## Score: {pct:.1f}% ({total:.0f}/{max_score:.0f})\n")

        # Category breakdown
        breakdown = score.get("breakdown", {})
        if breakdown:
            lines.append("### Score Breakdown\n")
            for category, details in breakdown.items():
                if isinstance(details, dict):
                    cat_score = details.get("score", 0)
                    cat_max = details.get("max", 0)
                    lines.append(f"- **{category}**: {cat_score:.1f}/{cat_max:.1f}")
                else:
                    lines.append(f"- **{category}**: {details}")
            lines.append("")

        # Zero-score metrics (failures)
        metrics = score.get("metrics", score.get("scores", {}))
        if metrics:
            zeros = [k for k, v in metrics.items()
                     if isinstance(v, (int, float)) and v == 0]
            if zeros:
                lines.append("### Zero-Score Metrics (Failures)\n")
                for m in sorted(zeros):
                    lines.append(f"- {m}")
                lines.append("")

    # --- Scenario Config ---
    if scenario:
        lines.append("## Scenario Config\n")
        for key in ["terrain", "temperature", "map_size", "trees",
                     "mountains", "water", "challenge", "mission"]:
            val = scenario.get(key)
            if val is not None:
                lines.append(f"- **{key}**: {val}")
        lines.append("")

    # --- Audit (if available) ---
    audit = load_json(os.path.join(result_dir, "audit.json"))
    if audit:
        lines.append("## Auditor Analysis\n")

        failure_chains = audit.get("failure_chains", [])
        if failure_chains:
            lines.append("### Failure Chains\n")
            for chain in failure_chains:
                if isinstance(chain, dict):
                    root = chain.get("root_cause", chain.get("cause", ""))
                    effect = chain.get("effect", chain.get("impact", ""))
                    lines.append(f"- **{root}** → {effect}")
                else:
                    lines.append(f"- {chain}")
            lines.append("")

        exec_gaps = audit.get("execution_gaps", [])
        if exec_gaps:
            lines.append("### Execution Gaps\n")
            for gap in exec_gaps:
                if isinstance(gap, dict):
                    lines.append(f"- {gap.get('description', gap)}")
                else:
                    lines.append(f"- {gap}")
            lines.append("")

        recurring = audit.get("recurring_issues", [])
        if recurring:
            lines.append("### Recurring Issues\n")
            for issue in recurring:
                if isinstance(issue, dict):
                    lines.append(f"- {issue.get('description', issue)}")
                else:
                    lines.append(f"- {issue}")
            lines.append("")

        recommendations = audit.get("recommendations", audit.get("fixes", []))
        if recommendations:
            lines.append("### Recommendations\n")
            for rec in recommendations:
                if isinstance(rec, dict):
                    lines.append(f"- [{rec.get('priority', '?')}] {rec.get('description', rec)}")
                else:
                    lines.append(f"- {rec}")
            lines.append("")

    # --- Trainer Summary (if available) ---
    trainer_path = os.path.join(result_dir, "trainer_summary.txt")
    if os.path.exists(trainer_path):
        with open(trainer_path) as f:
            trainer_text = f.read().strip()
        if trainer_text:
            lines.append("## Trainer Fixes\n")
            lines.append(trainer_text)
            lines.append("")

    # --- Overseer Highlights ---
    convo_path = os.path.join(result_dir, "overseer_conversation.txt")
    if os.path.exists(convo_path):
        with open(convo_path) as f:
            convo = f.read()

        # Extract FAILED lines and final status
        failed_lines = [l.strip() for l in convo.splitlines()
                        if "FAILED:" in l or "ERROR:" in l or "error:" in l.lower()]
        if failed_lines:
            lines.append("## Overseer Errors\n")
            for fl in failed_lines[:20]:  # cap at 20
                lines.append(f"- `{fl[:200]}`")
            lines.append("")

    # --- Error (if run crashed) ---
    error = load_json(os.path.join(result_dir, "error.json"))
    if error:
        lines.append("## Run Error\n")
        lines.append(f"```\n{error.get('error', json.dumps(error, indent=2))}\n```\n")

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: summarize_run.py <result_dir>", file=sys.stderr)
        sys.exit(1)

    result_dir = sys.argv[1]
    if not os.path.isdir(result_dir):
        print(f"Not a directory: {result_dir}", file=sys.stderr)
        sys.exit(1)

    summary = summarize(result_dir)
    out_path = os.path.join(result_dir, "run_summary.md")
    with open(out_path, "w") as f:
        f.write(summary)
    print(f"Summary written to {out_path}")

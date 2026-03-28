#!/usr/bin/env python3
"""Generate run_summary.md from run artifacts for QMD indexing.

Extracts narrative content from score.json, audit.json, and
overseer_conversation.txt into a single searchable markdown file.

Usage: python3 frontier/summarize_run.py <result_dir>
"""

import json
import os
import sys
from collections import Counter


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_jsonl(path):
    entries = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except FileNotFoundError:
        pass
    return entries


def format_phase_durations(result_dir):
    """Read phases.jsonl, compute wall-clock time per phase."""
    events = load_jsonl(os.path.join(result_dir, "phases.jsonl"))
    if not events:
        return None
    starts = {}
    durations = []
    for ev in events:
        phase = ev.get("phase", "")
        if ev.get("event") == "start":
            starts[phase] = ev.get("ts", 0)
        elif ev.get("event") == "end" and phase in starts:
            dur = ev.get("ts", 0) - starts[phase]
            durations.append((phase, dur))
    if not durations:
        return None
    lines = ["## Phase Durations\n"]
    total = sum(d for _, d in durations)
    for phase, dur in durations:
        pct = (dur / total * 100) if total > 0 else 0
        lines.append(f"- **{phase}**: {dur}s ({pct:.0f}%)")
    lines.append(f"- **total**: {total}s")
    lines.append("")
    return "\n".join(lines)


def format_timeline_trends(result_dir):
    """Read score_timeline.jsonl, extract key trajectories."""
    entries = load_jsonl(os.path.join(result_dir, "score_timeline.jsonl"))
    if len(entries) < 2:
        return None
    lines = ["## Timeline Trends\n"]

    # Food trajectory
    meals = [e.get("meals", 0) for e in entries]
    lines.append(f"- **Food (meals)**: {meals[0]} → {meals[-1]} "
                 f"(peak {max(meals)}, low {min(meals)})")

    # Building count
    bldgs = [e.get("buildings", 0) for e in entries]
    lines.append(f"- **Buildings**: {bldgs[0]} → {bldgs[-1]}")

    # Mood arc
    moods = [e.get("mood_avg", -1) for e in entries]
    valid_moods = [m for m in moods if m >= 0]
    if valid_moods:
        lines.append(f"- **Avg mood**: {valid_moods[0]:.0f}% → {valid_moods[-1]:.0f}% "
                     f"(low {min(valid_moods):.0f}%)")

    # Score progression
    scores = [e.get("pct", 0) for e in entries]
    lines.append(f"- **Score**: {scores[0]:.1f}% → {scores[-1]:.1f}%")

    # Warnings (searchable by QMD)
    if len(meals) >= 4:
        mid = len(meals) // 2
        if meals[mid] > meals[-1] and meals[mid] - meals[-1] > 3:
            lines.append(f"- **WARNING: food dropped mid-game** "
                         f"({meals[mid]} at midpoint → {meals[-1]} final)")

    if valid_moods and min(valid_moods) < 25:
        lines.append(f"- **WARNING: mood crisis** (dropped to {min(valid_moods):.0f}%)")

    lines.append("")
    return "\n".join(lines)


def format_sdk_stats(result_dir):
    """Read command_log.jsonl, compute call stats."""
    entries = load_jsonl(os.path.join(result_dir, "command_log.jsonl"))
    if not entries:
        return None

    total = len(entries)
    errors = sum(1 for e in entries if not e.get("ok", True))
    cached = sum(1 for e in entries if e.get("cached", False))
    error_rate = errors / total * 100 if total > 0 else 0

    cmd_counts = Counter(e.get("cmd", "?") for e in entries)
    top_cmds = cmd_counts.most_common(5)

    non_cached = [e for e in entries if not e.get("cached") and e.get("ms", 0) > 0]
    slowest = sorted(non_cached, key=lambda e: -e.get("ms", 0))[:3]

    lines = ["## SDK Call Stats\n"]
    lines.append(f"- **Total calls**: {total} ({cached} cached)")
    lines.append(f"- **Errors**: {errors} ({error_rate:.1f}%)")
    lines.append(f"- **Top commands**: "
                 + ", ".join(f"{cmd} ({n})" for cmd, n in top_cmds))
    if slowest:
        lines.append(f"- **Slowest**: "
                     + ", ".join(f"{e.get('cmd')} ({e.get('ms', 0):.0f}ms)"
                                for e in slowest))

    if error_rate > 10:
        lines.append(f"- **WARNING: high SDK error rate** ({error_rate:.1f}%)")

    error_cmds = Counter(e.get("cmd", "?") for e in entries if not e.get("ok", True))
    if error_cmds:
        top_errors = error_cmds.most_common(3)
        lines.append(f"- **Error commands**: "
                     + ", ".join(f"{cmd} ({n})" for cmd, n in top_errors))

    lines.append("")
    return "\n".join(lines)


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

    # --- Phase Durations ---
    phase_text = format_phase_durations(result_dir)
    if phase_text:
        lines.append(phase_text)

    # --- Timeline Trends ---
    timeline_text = format_timeline_trends(result_dir)
    if timeline_text:
        lines.append(timeline_text)

    # --- SDK Call Stats ---
    sdk_text = format_sdk_stats(result_dir)
    if sdk_text:
        lines.append(sdk_text)

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
    # audit.md is the full investigation — include it directly
    audit_md_path = os.path.join(result_dir, "audit.md")
    audit_json_path = os.path.join(result_dir, "audit.json")
    if os.path.exists(audit_md_path):
        with open(audit_md_path) as f:
            audit_text = f.read().strip()
        if audit_text:
            lines.append("## Auditor Investigation\n")
            lines.append(audit_text)
            lines.append("")
    elif os.path.exists(audit_json_path):
        # Legacy: old JSON audits
        audit = load_json(audit_json_path)
        if audit:
            lines.append("## Auditor Analysis (legacy JSON)\n")
            lines.append(f"```json\n{json.dumps(audit, indent=2)[:2000]}\n```\n")

    # --- Trainer Fixes ---
    trainer_changelog = load_json(os.path.join(result_dir, "trainer_changelog.json"))
    trainer_path = os.path.join(result_dir, "trainer_summary.txt")

    if trainer_changelog:
        lines.append("## Trainer Fixes\n")
        issue = trainer_changelog.get("issue_addressed", "")
        if issue:
            lines.append(f"**Issue addressed**: {issue}\n")
        changes = trainer_changelog.get("changes", [])
        for ch in changes:
            lines.append(f"- `{ch.get('file', '?')}`: {ch.get('description', '?')}")
        if changes:
            lines.append("")
        validation = trainer_changelog.get("validation", "")
        if validation:
            lines.append(f"**Validation**: {validation}\n")
    elif os.path.exists(trainer_path):
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

    # --- Sub-agent summary (if sub-agents were used) ---
    subagent_dir = os.path.join(result_dir, "subagents")
    if os.path.isdir(subagent_dir):
        md_files = sorted(f for f in os.listdir(subagent_dir) if f.endswith(".md"))
        if md_files:
            lines.append(f"## Sub-Agents ({len(md_files)} spawned)\n")
            for md_file in md_files:
                agent_type = "reader" if "reader" in md_file else "executor" if "executor" in md_file else "agent"
                lines.append(f"- **{md_file}** ({agent_type})")
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

    # Copy raw artifacts to .md so QMD indexes them (collection pattern is **/*.md)
    # audit.md is already markdown — no copy needed
    copy_as_md = [
        ("overseer_conversation.txt", "overseer_conversation.md"),
    ]
    for src_name, dst_name in copy_as_md:
        src = os.path.join(result_dir, src_name)
        dst = os.path.join(result_dir, dst_name)
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, dst)

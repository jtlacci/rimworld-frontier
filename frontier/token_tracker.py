#!/usr/bin/env python3
"""Track token usage per agent across all runs.

Records: overseer, auditor, trainer, challenger — each as separate entries.
Appends to token_usage.jsonl at frontier root.

Usage:
  python3 frontier/token_tracker.py overseer <result_dir>
  python3 frontier/token_tracker.py auditor <result_dir>
  python3 frontier/token_tracker.py trainer <result_dir>
  python3 frontier/token_tracker.py challenger <result_dir>
  python3 frontier/token_tracker.py --report
"""
import json, os, sys

TRACKER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "token_usage.jsonl")


def track_overseer(result_dir):
    usage_path = os.path.join(result_dir, "overseer_usage.json")
    if not os.path.exists(usage_path): return
    u = json.load(open(usage_path))
    score = 0
    score_path = os.path.join(result_dir, "score.json")
    if os.path.exists(score_path):
        score = json.load(open(score_path)).get("pct", 0)
    entry = {
        "agent": "overseer",
        "run": result_dir,
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "cost_usd": u.get("total_cost_usd", 0),
        "turns": u.get("num_turns", 0),
        "duration_s": u.get("duration_ms", 0) / 1000,
        "score_pct": score,
    }
    _append(entry)


def track_auditor(result_dir):
    audit_path = os.path.join(result_dir, "audit.md")
    findings_path = os.path.join(result_dir, "audit_findings.md")
    if not os.path.exists(audit_path): return
    entry = {
        "agent": "auditor",
        "run": result_dir,
        "output_bytes": os.path.getsize(audit_path),
        "findings_bytes": os.path.getsize(findings_path) if os.path.exists(findings_path) else 0,
    }
    _append(entry)


def track_trainer(result_dir):
    changelog_path = os.path.join(result_dir, "trainer_changelog.json")
    summary_path = os.path.join(result_dir, "trainer_summary.txt")
    if not os.path.exists(summary_path) and not os.path.exists(changelog_path): return
    entry = {"agent": "trainer", "run": result_dir}
    if os.path.exists(changelog_path):
        cl = json.load(open(changelog_path))
        entry["changes"] = len(cl.get("changes", []))
        entry["issue"] = cl.get("issue_addressed", "")
    if os.path.exists(summary_path):
        text = open(summary_path).read()
        # Extract token line if present
        for line in text.splitlines():
            if line.startswith("Tokens:"):
                try:
                    parts = line.split()
                    entry["total_tokens"] = int(parts[1].replace(",", ""))
                except: pass
        entry["output_bytes"] = len(text)
    _append(entry)


def track_challenger(result_dir):
    summary_path = os.path.join(result_dir, "challenger_summary.txt")
    if not os.path.exists(summary_path): return
    entry = {
        "agent": "challenger",
        "run": result_dir,
        "output_bytes": os.path.getsize(summary_path),
    }
    _append(entry)


def _append(entry):
    with open(TRACKER_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    agent = entry.get("agent", "?")
    tokens = entry.get("input_tokens", 0) + entry.get("output_tokens", 0) or entry.get("total_tokens", 0) or entry.get("output_bytes", 0)
    print(f"  [{agent}] {tokens} tokens/bytes")


def report():
    if not os.path.exists(TRACKER_PATH):
        print("No tracking data yet")
        return

    entries = []
    with open(TRACKER_PATH) as f:
        for line in f:
            try: entries.append(json.loads(line.strip()))
            except: pass

    agents = {}
    for e in entries:
        a = e.get("agent", "?")
        if a not in agents: agents[a] = []
        agents[a].append(e)

    print(f"{'Agent':<12s} {'Runs':>5s} {'Avg Tokens':>12s} {'Total Tokens':>14s} {'Avg Cost':>10s} {'Total Cost':>12s}")
    print("-" * 70)

    for agent in ["overseer", "auditor", "trainer", "challenger"]:
        runs = agents.get(agent, [])
        if not runs: continue

        if agent == "overseer":
            tokens = [r.get("input_tokens", 0) + r.get("output_tokens", 0) for r in runs]
            costs = [r.get("cost_usd", 0) for r in runs]
        elif agent == "trainer":
            tokens = [r.get("total_tokens", 0) or r.get("output_bytes", 0) for r in runs]
            costs = [0] * len(runs)
        else:
            tokens = [r.get("output_bytes", 0) for r in runs]
            costs = [0] * len(runs)

        avg_tok = sum(tokens) / len(tokens) if tokens else 0
        avg_cost = sum(costs) / len(costs) if costs else 0

        print(f"{agent:<12s} {len(runs):>5d} {avg_tok:>12,.0f} {sum(tokens):>14,.0f} ${avg_cost:>9.4f} ${sum(costs):>11.4f}")

    # Overseer efficiency
    overseer_runs = agents.get("overseer", [])
    if overseer_runs:
        scores = [r.get("score_pct", 0) for r in overseer_runs]
        tokens = [r.get("input_tokens", 0) + r.get("output_tokens", 0) for r in overseer_runs]
        print(f"\nOverseer efficiency:")
        print(f"  Avg score: {sum(scores)/len(scores):.1f}%")
        print(f"  Avg tokens/run: {sum(tokens)/len(tokens):,.0f}")
        scored = [(t, s) for t, s in zip(tokens, scores) if s > 0]
        if scored:
            avg_tpp = sum(t/s for t, s in scored) / len(scored)
            print(f"  Avg tokens/score-point: {avg_tpp:,.0f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: token_tracker.py <agent> <result_dir> | --report")
        sys.exit(1)

    if sys.argv[1] == "--report":
        report()
    elif len(sys.argv) >= 3:
        agent = sys.argv[1]
        result_dir = sys.argv[2]
        {"overseer": track_overseer, "auditor": track_auditor,
         "trainer": track_trainer, "challenger": track_challenger}.get(agent, lambda x: print(f"Unknown agent: {agent}"))(result_dir)
    else:
        print("Usage: token_tracker.py <agent> <result_dir> | --report")

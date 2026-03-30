#!/usr/bin/env python3
"""Track token usage and context efficiency across runs.

Reads overseer_usage.json, audit.md size, trainer output from each run
and appends to a cumulative token_usage.jsonl at the frontier root.

Usage: python3 frontier/token_tracker.py <result_dir>
       python3 frontier/token_tracker.py --report  # print summary
"""
import json, os, sys

TRACKER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "token_usage.jsonl")


def track_run(result_dir):
    entry = {"run_dir": result_dir}

    # Overseer tokens
    usage_path = os.path.join(result_dir, "overseer_usage.json")
    if os.path.exists(usage_path):
        u = json.load(open(usage_path))
        entry["overseer"] = {
            "input_tokens": u.get("input_tokens", 0),
            "output_tokens": u.get("output_tokens", 0),
            "total_tokens": u.get("input_tokens", 0) + u.get("output_tokens", 0),
            "cost_usd": u.get("total_cost_usd", 0),
            "turns": u.get("num_turns", 0),
            "duration_s": u.get("duration_ms", 0) / 1000,
        }

    # Score
    score_path = os.path.join(result_dir, "score.json")
    if os.path.exists(score_path):
        entry["score_pct"] = json.load(open(score_path)).get("pct", 0)

    # Auditor size (proxy for token usage — no direct tracking)
    audit_path = os.path.join(result_dir, "audit.md")
    if os.path.exists(audit_path):
        entry["auditor"] = {"output_bytes": os.path.getsize(audit_path)}

    # Trainer changelog
    changelog_path = os.path.join(result_dir, "trainer_changelog.json")
    if os.path.exists(changelog_path):
        cl = json.load(open(changelog_path))
        entry["trainer"] = {
            "changes": len(cl.get("changes", [])),
            "issue": cl.get("issue_addressed", ""),
        }

    # Scenario
    scenario_path = os.path.join(result_dir, "scenario.json")
    if os.path.exists(scenario_path):
        s = json.load(open(scenario_path))
        entry["scenario"] = s.get("name", "?")

    # Context efficiency: tokens per score point
    total_tok = entry.get("overseer", {}).get("total_tokens", 0)
    score = entry.get("score_pct", 0)
    if total_tok > 0 and score > 0:
        entry["tokens_per_pct"] = round(total_tok / score)

    with open(TRACKER_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"Tracked: {entry.get('scenario', '?')} — {score:.1f}% — {total_tok} tokens")


def report():
    if not os.path.exists(TRACKER_PATH):
        print("No tracking data yet")
        return

    entries = []
    with open(TRACKER_PATH) as f:
        for line in f:
            try: entries.append(json.loads(line.strip()))
            except: pass

    if not entries:
        print("No tracking data")
        return

    # Group by scenario
    scenarios = {}
    for e in entries:
        s = e.get("scenario", "?")
        if s not in scenarios: scenarios[s] = []
        scenarios[s].append(e)

    print(f"{'Scenario':<30s} {'Runs':>4s} {'Avg Score':>9s} {'Avg Tokens':>10s} {'Tok/Pct':>8s} {'Avg Turns':>9s}")
    print("-" * 75)

    total_tokens = 0
    total_cost = 0
    total_runs = 0

    for scenario, runs in sorted(scenarios.items()):
        scores = [r.get("score_pct", 0) for r in runs]
        tokens = [r.get("overseer", {}).get("total_tokens", 0) for r in runs]
        costs = [r.get("overseer", {}).get("cost_usd", 0) for r in runs]
        turns = [r.get("overseer", {}).get("turns", 0) for r in runs]
        tpp = [r.get("tokens_per_pct", 0) for r in runs if r.get("tokens_per_pct")]

        avg_score = sum(scores) / len(scores) if scores else 0
        avg_tokens = sum(tokens) / len(tokens) if tokens else 0
        avg_tpp = sum(tpp) / len(tpp) if tpp else 0
        avg_turns = sum(turns) / len(turns) if turns else 0

        print(f"{scenario:<30s} {len(runs):>4d} {avg_score:>8.1f}% {avg_tokens:>10.0f} {avg_tpp:>8.0f} {avg_turns:>9.1f}")

        total_tokens += sum(tokens)
        total_cost += sum(costs)
        total_runs += len(runs)

    print("-" * 75)
    print(f"{'TOTAL':<30s} {total_runs:>4d} {'':>9s} {total_tokens:>10.0f} {'':>8s} {'':>9s}")
    print(f"Total cost: ${total_cost:.4f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: token_tracker.py <result_dir> | --report")
        sys.exit(1)

    if sys.argv[1] == "--report":
        report()
    else:
        track_run(sys.argv[1])

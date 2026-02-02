#!/usr/bin/env python3
"""Index experiments summaries into a CSV at reports/experiments.csv"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import csv


def scan_reports(root: Path) -> list:
    rows = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        s = d / "summary.json"
        if not s.exists():
            continue
        try:
            j = json.loads(s.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append(j)
    return rows


def write_csv(rows: list, out_path: Path):
    headers = [
        "exp_id", "tag", "timestamp", "commit", "branch", "config_hash",
        "policy", "mcts_sims", "n_episodes", "max_steps",
        "winrate", "avg_steps", "avg_keys_end", "avg_sanity_end",
        "runs_dir", "dataset_path", "model_path", "status"
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            row = {h: "" for h in headers}
            row["exp_id"] = r.get("exp_id")
            row["tag"] = r.get("tag")
            row["timestamp"] = r.get("timestamp")
            row["commit"] = (r.get("git") or {}).get("commit")
            row["branch"] = (r.get("git") or {}).get("branch")
            row["config_hash"] = r.get("config_hash")
            sim = r.get("simulation", {})
            row["policy"] = sim.get("policy")
            row["mcts_sims"] = (sim.get("policy_kwargs") or {}).get("mcts_sims")
            row["n_episodes"] = (r.get("results") or {}).get("n_runs")
            row["max_steps"] = sim.get("max_steps")
            res = r.get("results") or {}
            row["winrate"] = res.get("winrate")
            row["avg_steps"] = res.get("avg_steps")
            row["avg_keys_end"] = res.get("avg_keys_end")
            row["avg_sanity_end"] = res.get("avg_sanity_end")
            paths = r.get("paths") or {}
            row["runs_dir"] = paths.get("runs_dir")
            row["dataset_path"] = paths.get("dataset_path")
            row["model_path"] = paths.get("model_path")
            row["status"] = r.get("status")
            writer.writerow(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=str, default="reports")
    args = ap.parse_args()
    root = Path(args.root)
    rows = scan_reports(root)
    out = root / "experiments.csv"
    write_csv(rows, out)
    print(f"Indexed {len(rows)} experiments -> {out}")


if __name__ == "__main__":
    main()

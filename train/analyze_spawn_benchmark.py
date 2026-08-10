#!/usr/bin/env python3
"""Analiza el benchmark de spawn randomization vs baseline.

Uso:
  python3 train/analyze_spawn_benchmark.py <benchmark_summary.json> [--baseline <baseline_summary.json>]

Extrae:
- Win-rate del modelo entrenado con jitter vs best_evolved vs GOAL
- Novelas (seeds ganadas por el modelo jitter que NO gana best_evolved ni GOAL)
- Overlap con GOAL y best_evolved
- Redondeo de techo empírico (unión)
"""

import json
import argparse
from pathlib import Path


def extract_wins(summary_path: str) -> dict:
    """Returns {model_name: set(winning_seeds)}"""
    with open(summary_path) as f:
        data = json.load(f)
    wins = {}
    if "results" in data:
        for entry in data["results"]:
            model = entry.get("model", "unknown")
            if entry.get("win"):
                wins.setdefault(model, set()).add(entry["seed"])
    elif "detail" in data:
        for model, seeds in data["detail"].items():
            wins[model] = {int(s) for s, r in seeds.items() if r.get("win")}
    return wins


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("benchmark", help="Path to benchmark_summary.json")
    parser.add_argument("--baseline", help="Path to baseline benchmark for comparison")
    args = parser.parse_args()

    wins = extract_wins(args.benchmark)
    print(f"=== Benchmark: {Path(args.benchmark).name} ===\n")

    for model, win_set in sorted(wins.items()):
        print(
            f"  {model}: {len(win_set)}/{len(win_set)} wins ({100 * len(win_set) / 300:.1f}% of 300)"
        )
        print(f"    Seeds: {sorted(win_set)[:20]}{'...' if len(win_set) > 20 else ''}")

    if args.baseline and Path(args.baseline).exists():
        baseline_wins = extract_wins(args.baseline)
        print(f"\n=== Baseline comparison: {Path(args.baseline).name} ===\n")
        for model in wins:
            if model in baseline_wins:
                novelas = wins[model] - baseline_wins[model]
                lost = baseline_wins[model] - wins[model]
                print(f"  {model}:")
                print(f"    Baseline: {len(baseline_wins[model])} wins")
                print(f"    Jitter:   {len(wins[model])} wins")
                print(f"    Novelas (new wins): {len(novelas)} {sorted(novelas)}")
                if lost:
                    print(
                        f"    Lost (was winning, now losing): {len(lost)} {sorted(lost)}"
                    )

    # Union (techo empírico)
    all_wins = set()
    for s in wins.values():
        all_wins |= s
    print(
        f"\n  UNION (techo empírico): {len(all_wins)}/300 = {100 * len(all_wins) / 300:.1f}%"
    )

    # Seeds nunca ganadas
    never_won = set(range(300)) - all_wins
    print(f"  Never won: {len(never_won)}/300 = {100 * len(never_won) / 300:.1f}%")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Quick winrate benchmark across N seeds."""
import argparse
import subprocess
import sys
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--max-steps", type=int, default=800)
    ap.add_argument("--policy", type=str, default="GOAL")
    ap.add_argument("--start-seed", type=int, default=1)
    args = ap.parse_args()

    root = Path(__file__).parent.parent
    results = []
    outcomes = {}

    for seed in range(args.start_seed, args.start_seed + args.seeds):
        r = subprocess.run(
            [sys.executable, "-m", "sim.runner",
             "--seed", str(seed),
             "--max-steps", str(args.max_steps),
             "--policy", args.policy],
            capture_output=True, text=True, cwd=str(root)
        )
        last = r.stdout.strip().split("\n")[-1] if r.stdout.strip() else r.stderr.strip().split("\n")[-1]
        print(f"seed={seed}: {last}")
        results.append(last)
        # Parse outcome
        if "WIN" in last:
            outcomes["WIN"] = outcomes.get("WIN", 0) + 1
        elif "LOSE" in last:
            # extract specific loss reason
            parts = last.split()
            for i, p in enumerate(parts):
                if p.startswith("LOSE"):
                    outcomes[p] = outcomes.get(p, 0) + 1
                    break
            else:
                outcomes["LOSE_OTHER"] = outcomes.get("LOSE_OTHER", 0) + 1
        else:
            outcomes["ERROR/TIMEOUT"] = outcomes.get("ERROR/TIMEOUT", 0) + 1

    wins = outcomes.get("WIN", 0)
    total = len(results)
    print(f"\n=== RESULTS ({args.policy}, max_steps={args.max_steps}) ===")
    print(f"Winrate: {wins}/{total} = {wins/total:.1%}")
    print("Breakdown:")
    for k, v in sorted(outcomes.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()

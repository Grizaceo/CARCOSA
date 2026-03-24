#!/usr/bin/env python3
"""
Dataset generator for CARCOSA bot training.

Runs N episodes (optionally in parallel) and saves transition records
as .jsonl files + summaries per episode. Uses the existing run_episode
infrastructure which writes state→action→next_state records per step.

Usage:
    # Quick test (10 episodes, sequential)
    python tools/generate_dataset.py --episodes 10

    # Production run (500 episodes, 4 parallel workers)
    python tools/generate_dataset.py --episodes 500 --workers 4 --out-dir datasets/v1

    # Multiple policies
    python tools/generate_dataset.py --episodes 200 --workers 4 --policy GOAL
    python tools/generate_dataset.py --episodes 200 --workers 4 --policy BERSERKER

Output per episode:
    datasets/v1/seed000001.jsonl         (step-by-step transitions)
    datasets/v1/seed000001_summary.json  (game outcome, stats)
    datasets/v1/dataset_index.json       (aggregate stats for this run)
"""
import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _run_one(args_tuple):
    """Run a single episode; called in worker process."""
    seed, max_steps, policy_name, out_dir = args_tuple
    from sim.runner import run_episode
    out_path = str(Path(out_dir) / f"seed{seed:06d}.jsonl")
    try:
        state = run_episode(
            seed=seed,
            max_steps=max_steps,
            out_path=out_path,
            policy_name=policy_name,
        )
        return {
            "seed": seed,
            "outcome": str(state.outcome) if state.outcome is not None else "UNKNOWN",
            "round": state.round,
            "game_over": state.game_over,
            "ok": True,
        }
    except Exception as e:
        import traceback
        return {"seed": seed, "ok": False, "error": str(e), "tb": traceback.format_exc()[-500:]}


def main():
    ap = argparse.ArgumentParser(description="Generate CARCOSA training dataset")
    ap.add_argument("--episodes", type=int, default=100,
                    help="Number of episodes to generate")
    ap.add_argument("--start-seed", type=int, default=1,
                    help="Starting seed value (seeds are start to start+episodes-1)")
    ap.add_argument("--max-steps", type=int, default=900,
                    help="Max steps per episode")
    ap.add_argument("--policy", type=str, default="GOAL",
                    choices=["GOAL", "COWARD", "BERSERKER", "SPEEDRUNNER", "RANDOM"],
                    help="Player policy (GOAL is the heuristic bot)")
    ap.add_argument("--workers", type=int, default=1,
                    help="Parallel workers (1 = sequential, 4+ recommended for large runs)")
    ap.add_argument("--out-dir", type=str, default=None,
                    help="Output directory (default: datasets/TIMESTAMP_POLICY/)")
    args = ap.parse_args()

    # Setup output directory
    if args.out_dir:
        out_dir = Path(args.out_dir)
        if not out_dir.is_absolute():
            out_dir = ROOT / out_dir
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = ROOT / "datasets" / f"{ts}_{args.policy}"
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = list(range(args.start_seed, args.start_seed + args.episodes))
    tasks = [(s, args.max_steps, args.policy, str(out_dir)) for s in seeds]

    print(f"=== CARCOSA Dataset Generator ===")
    print(f"  Episodes:   {args.episodes}")
    print(f"  Seeds:      [{seeds[0]}, {seeds[-1]}]")
    print(f"  Policy:     {args.policy}")
    print(f"  Max steps:  {args.max_steps}")
    print(f"  Workers:    {args.workers}")
    print(f"  Output:     {out_dir}")
    print()

    results = []
    outcomes = {}
    errors = 0
    t0 = time.time()

    if args.workers <= 1:
        for i, task in enumerate(tasks, 1):
            res = _run_one(task)
            results.append(res)
            if res["ok"]:
                outcome = res["outcome"]
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
                rnd = res.get("round", "?")
                wins = outcomes.get("WIN", 0)
                print(f"[{i:4d}/{args.episodes}] seed={res['seed']:6d} | {outcome:<25s} | r={rnd:3} | wins={wins}")
            else:
                errors += 1
                print(f"[{i:4d}/{args.episodes}] seed={res['seed']:6d} | ERROR: {res.get('error', '?')[:80]}")
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(_run_one, task): task[0] for task in tasks}
            completed = 0
            for future in as_completed(futures):
                completed += 1
                res = future.result()
                results.append(res)
                if res["ok"]:
                    outcome = res["outcome"]
                    outcomes[outcome] = outcomes.get(outcome, 0) + 1
                    rnd = res.get("round", "?")
                    elapsed = time.time() - t0
                    rate = elapsed / completed
                    eta = rate * (args.episodes - completed)
                    wins = outcomes.get("WIN", 0)
                    print(f"[{completed:4d}/{args.episodes}] seed={res['seed']:6d} | {outcome:<25s} | r={rnd:3} | wins={wins} | ETA={eta:.0f}s")
                else:
                    errors += 1
                    print(f"[{completed:4d}/{args.episodes}] seed={res['seed']:6d} | ERROR: {res.get('error', '?')[:80]}")

    elapsed = time.time() - t0
    wins = outcomes.get("WIN", 0)
    total_ok = len(results) - errors

    print(f"\n=== GENERATION COMPLETE ===")
    print(f"  Total episodes:  {args.episodes}")
    print(f"  Successful:      {total_ok}")
    print(f"  Errors:          {errors}")
    print(f"  Winrate:         {wins}/{total_ok} = {wins / max(1, total_ok):.1%}")
    print(f"  Time:            {elapsed:.1f}s  ({elapsed/max(1,total_ok):.1f}s/episode)")
    print(f"  Output:          {out_dir}")
    print(f"\n  Outcome breakdown:")
    for k, v in sorted(outcomes.items(), key=lambda x: -x[1]):
        print(f"    {k:<35s}: {v:4d}  ({100*v/max(1,total_ok):.1f}%)")

    # Write aggregate index
    index = {
        "generated_at": datetime.now().isoformat(),
        "episodes_requested": args.episodes,
        "episodes_ok": total_ok,
        "errors": errors,
        "policy": args.policy,
        "max_steps": args.max_steps,
        "seed_range": [seeds[0], seeds[-1]],
        "winrate": wins / max(1, total_ok),
        "outcomes": outcomes,
        "elapsed_seconds": round(elapsed, 1),
        "seconds_per_episode": round(elapsed / max(1, total_ok), 2),
    }
    idx_path = out_dir / "dataset_index.json"
    idx_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    print(f"\n  Index:  {idx_path}")


if __name__ == "__main__":
    main()

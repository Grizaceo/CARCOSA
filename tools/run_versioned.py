#!/usr/bin/env python3
"""
Run simulator with automatic versioning based on git commit hash.
Each run session gets its own subfolder under runs/ to avoid mixing data.

Uso:
    python tools/run_versioned.py --n-seeds 10 --policy GOAL
    python tools/run_versioned.py --seeds 1 5 10 --policy GOAL
    python tools/run_versioned.py --seed 1 --max-steps 2000
"""
import subprocess
import json
from pathlib import Path
from datetime import datetime
import argparse
import sys


def get_git_commit_short():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def get_git_branch():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def run_seed(seed: int, session_dir: Path, max_steps: int, policy: str, mcts_rollouts: int = None):
    out_file = str(session_dir / f"seed{seed}.jsonl")
    cmd = [
        sys.executable, "-m", "sim.runner",
        "--seed", str(seed),
        "--max-steps", str(max_steps),
        "--policy", policy,
        "--out", out_file,
        ]
    if mcts_rollouts is not None:
        cmd.extend(["--mcts-rollouts", str(mcts_rollouts)])

    result = subprocess.run(
        cmd,
        capture_output=True, text=True
    )
    for line in result.stdout.strip().splitlines():
        if "Finished:" in line or "Saved" in line:
            print(f"  [seed {seed}] {line}")
    if result.returncode != 0:
        print(f"  [seed {seed}] ERROR:\n{result.stderr[-500:]}")
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Batch simulator con versionado automático.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--n-seeds", type=int, default=None, help="Correr seeds 1..N")
    group.add_argument("--seeds", type=int, nargs="+", default=None, help="Lista explícita de seeds")
    group.add_argument("--seed", type=int, default=None, help="Un solo seed")
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--policy", type=str, default="GOAL",
                        choices=["GOAL", "COWARD", "BERSERKER", "SPEEDRUNNER", "RANDOM", "MCTS"])
    parser.add_argument("--tag", type=str, default=None, help="Sufijo descriptivo del directorio")
    parser.add_argument("--version-dir", type=str, default=None,
                        help="Directorio de sesión explícito (compatibilidad con experiment.py)")
    parser.add_argument("--mcts-rollouts", type=int, default=None, help="MCTS rollouts si policy=MCTS")
    args = parser.parse_args()

    # Determinar seeds
    if args.n_seeds:
        seeds = list(range(1, args.n_seeds + 1))
    elif args.seeds:
        seeds = args.seeds
    elif args.seed:
        seeds = [args.seed]
    else:
        seeds = [1]

    commit = get_git_commit_short()
    branch = get_git_branch()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.version_dir:
        session_dir = Path(args.version_dir)
        session_name = session_dir.name
    else:
        tag = args.tag or args.policy.lower()
        session_name = f"{ts}_{commit}_{branch}_{tag}"
        session_dir = Path("runs") / session_name
    session_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "commit": commit,
        "branch": branch,
        "timestamp": ts,
        "policy": args.policy,
        "seeds": seeds,
        "max_steps": args.max_steps,
        "session": session_name,
    }
    with open(session_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Session : {session_name}")
    print(f"Commit  : {commit}  Branch: {branch}")
    print(f"Policy  : {args.policy}  Seeds: {seeds}  Max steps: {args.max_steps}")
    print(f"Output  : {session_dir}/")
    print(f"{'='*60}\n")

    for seed in seeds:
        run_seed(seed, session_dir, args.max_steps, args.policy, args.mcts_rollouts)

    print(f"\n{'='*60}")
    print(f"Listo. {len(seeds)} runs guardados en: {session_dir}/")
    print(f"Para consolidar:")
    print(f"  python tools/consolidate_runs.py {session_dir}/")
    print(f"{'='*60}\n")
    return str(session_dir)


if __name__ == "__main__":
    main()

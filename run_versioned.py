#!/usr/bin/env python3
"""
Run simulator with automatic versioning based on git commit hash.
Each commit gets its own runs folder to avoid mixing data from different code states.
"""
import subprocess
import json
from pathlib import Path
from datetime import datetime
import argparse
import sys

def get_git_commit_short():
    """Get the short commit hash (7 chars)"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except:
        return "unknown"

def get_git_branch():
    """Get the current branch name"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except:
        return "unknown"

def run_episode(seed: int, max_steps: int = 400, version_dir: str = None):
    """Run a single episode and save to versioned directory"""
    if version_dir is None:
        commit = get_git_commit_short()
        branch = get_git_branch()
        timestamp = datetime.now().strftime("%Y%m%d")
        version_dir = f"runs_v{commit}_{branch}_{timestamp}"
    
    version_path = Path(version_dir)
    version_path.mkdir(parents=True, exist_ok=True)
    
    # Run the simulator
    out_file = str(version_path / f"seed{seed}.jsonl")
    result = subprocess.run(
        ["python", "-m", "sim.runner", "--seed", str(seed), "--max-steps", str(max_steps), "--out", out_file],
        capture_output=True,
        text=True
    )
    
    # Parse output to get result
    output_lines = result.stdout.strip().split('\n')
    for line in output_lines:
        if "Finished:" in line:
            print(f"[Seed {seed}] {line}")
    
    return out_file

def main():
    parser = argparse.ArgumentParser(
        description="Run simulations with automatic code versioning"
    )
    parser.add_argument("--seed", type=int, default=1, help="Seed or seed range (1-5)")
    parser.add_argument("--all-seeds", action="store_true", help="Run seeds 1-5")
    parser.add_argument("--max-steps", type=int, default=400, help="Max steps per run")
    parser.add_argument("--version-dir", type=str, default=None, help="Custom version directory name")
    args = parser.parse_args()
    
    # Determine seeds to run
    if args.all_seeds:
        seeds = range(1, 6)
    else:
        seeds = [args.seed]
    
    # Get version info
    commit = get_git_commit_short()
    branch = get_git_branch()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if args.version_dir is None:
        version_dir = f"runs_v{commit}_{branch}_{timestamp}"
    else:
        version_dir = args.version_dir
    
    version_path = Path(version_dir)
    
    # Create metadata file
    metadata = {
        "commit": commit,
        "branch": branch,
        "timestamp": timestamp,
        "seeds": list(seeds),
        "max_steps": args.max_steps,
        "version_dir": version_dir
    }
    
    version_path.mkdir(parents=True, exist_ok=True)
    with open(version_path / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Running simulations for code version: {commit}")
    print(f"Branch: {branch}")
    print(f"Directory: {version_dir}")
    print(f"{'='*60}\n")
    
    # Run all seeds
    run_files = []
    for seed in seeds:
        out_file = run_episode(seed, args.max_steps, version_dir)
        run_files.append(out_file)
    
    print(f"\n{'='*60}")
    print(f"✓ All runs completed!")
    print(f"Results saved to: {version_dir}/")
    print(f"Files: {len(run_files)} runs")
    print(f"{'='*60}\n")
    
    return version_dir

if __name__ == "__main__":
    version_dir = main()

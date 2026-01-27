
import glob
import json
import os
import sys
from collections import Counter
import statistics

def analyze_runs():
    # Find latest versioned directory (current or historic)
    versions = []
    for pattern in ("runs/runs_v*", "docs/historics/runs/runs_v*"):
        versions.extend(glob.glob(pattern))
    
    # Sort by modification time (newest first)
    versions.sort(key=os.path.getmtime, reverse=True)
    
    jsonl_files = []
    if versions:
        version_dir = versions[0]
        print(f"Analyzing directory: {version_dir}")
        jsonl_files = glob.glob(os.path.join(version_dir, "*.jsonl"))
    else:
        # Fallback: analyze jsonl files directly under runs/
        jsonl_files = glob.glob(os.path.join("runs", "*.jsonl"))
        if not jsonl_files:
            print("No run directories or jsonl files found.")
            return
        print("Analyzing runs/*.jsonl files")

    outcomes = Counter()
    rounds = []
    print(f"Found {len(jsonl_files)} run files.")
    
    for fpath in jsonl_files:
        outcome = "UNKNOWN"
        round_num = 0
        try:
            with open(fpath, "r") as f:
                # Read line by line, look for game_over flag or last state
                last_line = None
                for line in f:
                    last_line = line
                
                if last_line:
                    data = json.loads(last_line)
                    # Check done or game_over
                    if data.get("done") or data.get("game_over"):
                        outcome = data.get("outcome", "UNKNOWN")
                        round_num = data.get("round", 0)
                    else:
                        outcome = "INCOMPLETE"
                        round_num = data.get("round", 0)
        except Exception as e:
            print(f"Error reading {fpath}: {e}")
            continue
            
        outcomes[outcome] += 1
        if outcome != "INCOMPLETE":
            rounds.append(round_num)

    print("\nResults Summary:")
    print("=" * 40)
    total = sum(outcomes.values())
    for k, v in outcomes.items():
        pct = (v / total * 100) if total > 0 else 0
        print(f"  {k}: {v} ({pct:.1f}%)")
    
    if rounds:
        print("\nGame Length (Rounds):")
        print(f"  Mean: {statistics.mean(rounds):.1f}")
        try:
            print(f"  Median: {statistics.median(rounds)}")
        except:
            pass
        print(f"  Min: {min(rounds)}")
        print(f"  Max: {max(rounds)}")

if __name__ == "__main__":
    analyze_runs()

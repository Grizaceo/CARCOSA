
import os
import json
import argparse
import glob
from collections import defaultdict
import statistics

def load_runs(data_dir):
    run_files = glob.glob(os.path.join(data_dir, "**/*.jsonl"), recursive=True)
    all_runs = []
    
    print(f"Found {len(run_files)} run files in {data_dir}...")
    
    for fpath in run_files:
        filename = os.path.basename(fpath)
        # Parse metadata from filename: run_POLICY_seedX_timestamp.jsonl
        # or run_seedX_timestamp.jsonl
        policy = "UNKNOWN"
        parts = filename.split('_')
        
        # Heuristica para extraer policy si existe
        # run_BERSERKER_seed123_...
        if len(parts) >= 3 and parts[1] in ["GOAL", "COWARD", "BERSERKER", "SPEEDRUNNER", "RANDOM"]:
            policy = parts[1]
        
        run_data = {
            "policy": policy,
            "file": filename,
            "steps": [],
            "outcome": "UNKNOWN",
            "final_round": 0,
            "final_sanity": [],
            "keys_found": 0
        }
        
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if not lines: continue
                
                # Read last line for outcome
                last_line = json.loads(lines[-1])
                run_data["outcome"] = last_line.get("outcome", "UNKNOWN")
                run_data["final_round"] = last_line.get("round", 0)
                run_data["steps_count"] = last_line.get("step", 0)
                
                # Extract summary from last step
                summary = last_line.get("summary_post", {})
                run_data["keys_found"] = summary.get("keys_in_hand", 0) # This is keys held, not total found. Close enough.
                
                # Check sanities from summary if available? 
                # Summary has mean_sanity and min_sanity.
                # Let's check features_post if available for detailed players
                features = last_line.get("features_post", [])
                # Features is a vector, hard to decode without schema.
                # Use summary keys.
                run_data["min_sanity"] = summary.get("min_sanity", 0)
                
        except Exception as e:
            print(f"Error reading {fpath}: {e}")
            continue
            
        all_runs.append(run_data)
        
    return all_runs

def analyze_runs(runs):
    if not runs:
        print("No runs to analyze.")
        return

    # Group by Policy
    runs_by_policy = defaultdict(list)
    for r in runs:
        runs_by_policy[r["policy"]].append(r)
        
    print("\n" + "="*60)
    print("GAMEPLAY ANALYSIS REPORT")
    print("="*60)
    
    headers = f"{'POLICY':<15} | {'GAMES':<5} | {'WIN %':<7} | {'AVG RND':<7} | {'MIN SAN':<7} | {'KEYS':<5}"
    print(headers)
    print("-" * len(headers))
    
    for policy, policy_runs in runs_by_policy.items():
        n = len(policy_runs)
        wins = sum(1 for r in policy_runs if r["outcome"] == "WIN")
        win_rate = (wins / n) * 100
        
        rounds = [r["final_round"] for r in policy_runs]
        avg_round = statistics.mean(rounds) if rounds else 0
        
        sanities = [r["min_sanity"] for r in policy_runs if r["min_sanity"] is not None]
        avg_min_sanity = statistics.mean(sanities) if sanities else 0
        
        keys = [r["keys_found"] for r in policy_runs]
        avg_keys = statistics.mean(keys) if keys else 0
        
        print(f"{policy:<15} | {n:<5} | {win_rate:6.1f}% | {avg_round:7.1f} | {avg_min_sanity:7.1f} | {avg_keys:5.1f}")

    print("\n" + "="*60)
    print("DEATH ANALYSIS (Causes of Loss)")
    
    # We infer cause from heuristics since we don't have explicit 'cause' field yet
    causes = defaultdict(int)
    for r in runs:
        if r["outcome"] == "LOSE":
            # Heuristic
            if r["min_sanity"] is not None and r["min_sanity"] <= -5:
                causes["Insanity (-5)"] += 1
            else:
                causes["Time/Attr/Other"] += 1
                
    for cause, count in causes.items():
        print(f"  - {cause}: {count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze Carcosa Gameplay Runs")
    parser.add_argument("dir", nargs="?", default="runs", help="Directory containing .jsonl run files")
    args = parser.parse_args()
    
    runs = load_runs(args.dir)
    analyze_runs(runs)

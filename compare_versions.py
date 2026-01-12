#!/usr/bin/env python3
"""
Compare d6 distributions across different code versions
"""
import json
from collections import Counter
from pathlib import Path
from scipy import stats
import glob
import sys

def analyze_version(version_dir: str) -> dict:
    """Analyze d6 distribution in a specific version directory"""
    version_path = Path(version_dir)
    
    if not version_path.exists():
        return None
    
    jsonl_files = sorted(version_path.glob("*.jsonl"))
    
    all_d6_rolls = []
    
    for jsonl_file in jsonl_files:
        with open(jsonl_file, "r") as f:
            for line in f:
                step = json.loads(line)
                if step.get("action_type") == "KING_ENDROUND":
                    if "action_data" in step and "d6" in step.get("action_data", {}):
                        d6 = step["action_data"]["d6"]
                        all_d6_rolls.append(d6)
    
    if not all_d6_rolls:
        return None
    
    counter = Counter(all_d6_rolls)
    observed = [counter.get(i, 0) for i in range(1, 7)]
    expected = [len(all_d6_rolls) / 6] * 6
    chi2_stat, p_value = stats.chisquare(observed, expected)
    
    # Load metadata
    metadata_file = version_path / "metadata.json"
    metadata = {}
    if metadata_file.exists():
        with open(metadata_file) as f:
            metadata = json.load(f)
    
    return {
        "version": version_dir,
        "commit": metadata.get("commit", "?"),
        "branch": metadata.get("branch", "?"),
        "timestamp": metadata.get("timestamp", "?"),
        "total_rolls": len(all_d6_rolls),
        "distribution": dict(sorted(counter.items())),
        "chi2": chi2_stat,
        "p_value": p_value,
        "is_uniform": p_value > 0.05
    }

def main():
    # Find all version directories
    versions = sorted(glob.glob("runs_v*"), reverse=True)
    
    if not versions:
        print("ERROR: No version directories found (runs_v*)")
        return
    
    print(f"\n{'='*90}")
    print("COMPARING D6 DISTRIBUTIONS ACROSS CODE VERSIONS")
    print(f"{'='*90}\n")
    
    results = []
    
    for version_dir in versions[:5]:  # Show last 5 versions
        result = analyze_version(version_dir)
        if result:
            results.append(result)
    
    # Display comparison table
    print(f"{'Commit':>7} | {'Branch':<8} | {'Rolls':>6} | {'Chi2':>7} | {'P-value':>8} | Uniform?")
    print(f"{'-'*7}-+-{'-'*8}-+-{'-'*6}-+-{'-'*7}-+-{'-'*8}-+----------")
    
    for r in results:
        status = "OK YES" if r["is_uniform"] else "NO"
        print(f"{r['commit']:>7} | {r['branch']:<8} | {r['total_rolls']:>6} | {r['chi2']:>7.2f} | {r['p_value']:>8.4f} | {status}")
    
    # Detailed view of most recent
    if results:
        latest = results[0]
        print(f"\n{'-'*90}")
        print(f"LATEST VERSION: {latest['commit']} ({latest['timestamp']})")
        print(f"{'-'*90}\n")
        
        print(f"Distribution: {latest['distribution']}")
        print(f"Total rolls: {latest['total_rolls']}")
        print(f"Chi-square: {latest['chi2']:.2f}")
        print(f"P-value: {latest['p_value']:.6f}")
        print(f"Status: {'OK UNIFORM' if latest['is_uniform'] else 'BIASED'}\n")
        
        print("Per-die breakdown:")
        dist = latest['distribution']
        total = latest['total_rolls']
        for i in range(1, 7):
            count = dist.get(i, 0)
            pct = (count / total) * 100 if total else 0
            expected_pct = 100 / 6
            ratio = (count / (total / 6)) if total else 0
            status = "OK" if 0.5 < ratio < 1.5 else "!"
            print(f"  d6={i}: {count:3d} rolls ({pct:5.1f}%) | expected {expected_pct:5.1f}% | ratio {ratio:5.2f}x | {status}")

if __name__ == "__main__":
    main()

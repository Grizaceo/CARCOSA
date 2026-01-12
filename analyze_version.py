"""
Analyze d6 distribution from a specific version directory
"""
import json
from collections import Counter
from pathlib import Path
from scipy import stats
import sys

def analyze_version(version_dir: str):
    """Analyze d6 distribution in a specific version directory"""
    version_path = Path(version_dir)
    
    if not version_path.exists():
        print(f"ERROR: Directory not found: {version_dir}")
        return False
    
    # Load metadata if available
    metadata_file = version_path / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file) as f:
            metadata = json.load(f)
        print(f"\n{'='*70}")
        print(f"Version: {metadata.get('commit', 'unknown')}")
        print(f"Branch: {metadata.get('branch', 'unknown')}")
        print(f"Timestamp: {metadata.get('timestamp', 'unknown')}")
        print(f"{'='*70}\n")
    
    # Find all JSONL files
    jsonl_files = sorted(version_path.glob("*.jsonl"))
    
    if not jsonl_files:
        print(f"ERROR: No JSONL files found in {version_dir}")
        return False
    
    print(f"Analyzing {len(jsonl_files)} files:\n")
    
    all_d6_rolls = []
    
    for jsonl_file in jsonl_files:
        d6_rolls = []
        with open(jsonl_file, "r") as f:
            for line in f:
                step = json.loads(line)
                if step.get("action_type") == "KING_ENDROUND":
                    if "action_data" in step and "d6" in step.get("action_data", {}):
                        d6 = step["action_data"]["d6"]
                        d6_rolls.append(d6)
                        all_d6_rolls.append(d6)
        
        if d6_rolls:
            counter = Counter(d6_rolls)
            print(f"  {jsonl_file.name:20s} -> {len(d6_rolls):3d} rolls, dist: {dict(sorted(counter.items()))}")
    
    print(f"\n{'='*70}")
    print(f"GLOBAL STATISTICS")
    print(f"{'='*70}\n")
    
    if all_d6_rolls:
        counter = Counter(all_d6_rolls)
        print(f"Total d6 rolls: {len(all_d6_rolls)}")
        print(f"Distribution: {dict(sorted(counter.items()))}\n")
        
        # Chi-square test
        observed = [counter.get(i, 0) for i in range(1, 7)]
        expected = [len(all_d6_rolls) / 6] * 6
        
        chi2_stat, p_value = stats.chisquare(observed, expected)
        
        print(f"Chi-square test:")
        print(f"  Observed: {observed}")
        print(f"  Expected: {[f'{e:.1f}' for e in expected]}")
        print(f"  Chi-square statistic: {chi2_stat:.2f}")
        print(f"  P-value: {p_value:.6f}")
        
        if p_value > 0.05:
            print(f"\nOK: Distribution is UNIFORM (p > 0.05)\n")
        else:
            print(f"\nWARN: Distribution is BIASED (p < 0.05)\n")
        
        print(f"Per-die breakdown:")
        print(f"{'d6':>3} | {'Count':>5} | {'%':>6} | {'Ratio':>6} | Status")
        print(f"{'-'*3}-+-{'-'*5}-+-{'-'*6}-+-{'-'*6}-+--------")
        
        for i in range(1, 7):
            count = counter.get(i, 0)
            pct = (count / len(all_d6_rolls)) * 100 if all_d6_rolls else 0
            expected_pct = 100 / 6
            ratio = (count / expected[0]) if expected[0] > 0 else 0
            status = "OK" if 0.5 < ratio < 1.5 else "!"
            print(f"{i:3d} | {count:5d} | {pct:5.1f}% | {ratio:5.2f}x | {status}")
        
        return True
    else:
        print("ERROR: No d6 rolls found in files!")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        version_dir = sys.argv[1]
    else:
        # Find the latest versioned directory
        import glob
        versions = sorted(glob.glob("runs_v*"), reverse=True)
        if versions:
            version_dir = versions[0]
            print(f"Using latest version: {version_dir}")
        else:
            print("ERROR: No version directories found (runs_v*)")
            sys.exit(1)
    
    analyze_version(version_dir)

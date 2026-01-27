"""
Analyze d6 distribution in the 5 most recent run files (those with latest timestamp)
"""
import json
from collections import Counter
from pathlib import Path
from scipy import stats

runs_dir = Path("runs")
jsonl_files = sorted(runs_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]

print("=== ANALYZING LAST 5 RUN FILES ===")
print(f"Files analyzed: {[f.name for f in jsonl_files]}\n")

all_d6_rolls = []

for jsonl_file in jsonl_files:
    d6_rolls = []
    with open(jsonl_file, "r") as f:
        for line in f:
            step = json.loads(line)
            if step.get("action_type") == "KING_ENDROUND":
                # d6 is now saved in action dict
                if "action_data" in step and "d6" in step.get("action_data", {}):
                    d6 = step["action_data"]["d6"]
                    d6_rolls.append(d6)
                    all_d6_rolls.append(d6)
    
    if d6_rolls:
        counter = Counter(d6_rolls)
        print(f"{jsonl_file.name}: total={len(d6_rolls)}, distribution={dict(sorted(counter.items()))}")

print("\n=== GLOBAL STATISTICS ===")
if all_d6_rolls:
    counter = Counter(all_d6_rolls)
    print(f"Total d6 rolls: {len(all_d6_rolls)}")
    print(f"Distribution: {dict(sorted(counter.items()))}")
    
    # Chi-square test
    observed = [counter.get(i, 0) for i in range(1, 7)]
    expected = [len(all_d6_rolls) / 6] * 6
    
    chi2_stat, p_value = stats.chisquare(observed, expected)
    
    print(f"\nChi-square test:")
    print(f"  Observed: {observed}")
    print(f"  Expected: {[f'{e:.1f}' for e in expected]}")
    print(f"  Chi-square statistic: {chi2_stat:.2f}")
    print(f"  P-value: {p_value:.6f}")
    
    if p_value > 0.05:
        print(f"✓ Distribution is UNIFORM (p > 0.05)")
    else:
        print(f"✗ Distribution is BIASED (p < 0.05)")
    
    print("\nPercentages by die:")
    for i in range(1, 7):
        count = counter.get(i, 0)
        pct = (count / len(all_d6_rolls)) * 100 if all_d6_rolls else 0
        expected_pct = 100 / 6
        ratio = (count / expected[0]) if expected[0] > 0 else 0
        print(f"  d6={i}: {count:3d} rolls ({pct:5.1f}%) - Expected: {expected_pct:5.1f}% ({ratio:4.2f}x)")
else:
    print("No d6 rolls found in files!")

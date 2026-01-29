import glob
import json
import os
from collections import Counter

def analyze_policy(path, name):
    files = glob.glob(os.path.join(path, '*_summary.json'))
    outcomes = Counter()
    keys_destroyed = []
    keys_final = []
    sacrifice_modes = Counter()
    sacrifice_total = 0
    accept_total = 0
    sacrifice_with_keys = 0
    
    for f in files:
        try:
            data = json.load(open(f))
            outcomes[data.get('outcome', 'UNKNOWN')] += 1
            keys_destroyed.append(data.get('keys_destroyed_total', 0))
            keys_final.append(data.get('keys_in_hand', 0))
            
            sac = data.get('sacrifice', {})
            sacrifice_total += sac.get('sacrifice', 0)
            accept_total += sac.get('accept', 0)
            sacrifice_with_keys += sac.get('sacrifice_with_keys', 0)
            for mode, count in sac.get('sacrifice_mode', {}).items():
                sacrifice_modes[mode] += count
        except Exception as e:
            print(f"Error reading {f}: {e}")
    
    print(f"\n{'='*60}")
    print(f"{name} ({len(files)} runs)")
    print('='*60)
    
    total = sum(outcomes.values())
    wins = outcomes.get('WIN', 0)
    key_losses = sum(v for k, v in outcomes.items() if 'KEYS_DESTROYED' in k)
    sanity_losses = sum(v for k, v in outcomes.items() if 'MINUS5' in k)
    
    print(f"\nWINRATE: {wins}/{total} ({wins/total*100:.1f}%)")
    print(f"  - LOSE_KEYS_DESTROYED: {key_losses} ({key_losses/total*100:.1f}%)")
    print(f"  - LOSE_ALL_MINUS5: {sanity_losses} ({sanity_losses/total*100:.1f}%)")
    
    print("\nOutcome breakdown:")
    for k, v in sorted(outcomes.items(), key=lambda x: -x[1])[:10]:
        print(f"  {k}: {v} ({v/total*100:.1f}%)")
    
    print(f"\nKeys destroyed per game: avg={sum(keys_destroyed)/len(keys_destroyed):.2f}")
    print(f"Keys in hand (final): avg={sum(keys_final)/len(keys_final):.2f}")
    
    print(f"\nSacrifice stats:")
    print(f"  Total sacrifices: {sacrifice_total}")
    print(f"  Total accepts: {accept_total}")
    print(f"  Sacrifices WITH keys: {sacrifice_with_keys}")
    print(f"  Modes: {dict(sacrifice_modes)}")

# Run analysis
goal_path = 'runs/runs_v8a81e15_main_20260128_203713_goal_randomking'
habitante_path = 'runs/runs_v8a81e15_main_20260128_201003_habitante_randomking'

if os.path.exists(goal_path):
    analyze_policy(goal_path, "GOAL Policy")
if os.path.exists(habitante_path):
    analyze_policy(habitante_path, "HABITANTE Policy")

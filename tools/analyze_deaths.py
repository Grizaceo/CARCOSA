import glob
import json
import os
from collections import Counter

def analyze_deaths(path, name):
    files = glob.glob(os.path.join(path, '*_summary.json'))
    death_by_player = Counter()
    death_by_role = Counter()
    role_modes = Counter()
    
    for f in files:
        try:
            data = json.load(open(f))
            outcome = data.get('outcome', '')
            role_mode = data.get('role_draw_mode', 'UNKNOWN')
            role_modes[role_mode] += 1
            roles = data.get('roles_assigned', {})
            
            # Extract victim from outcome like "LOSE_ALL_MINUS5 (HOUSE_LOSS -> P3)"
            if '->' in outcome:
                parts = outcome.split('->')
                if len(parts) >= 2:
                    victim = parts[-1].strip().rstrip(')')
                    death_by_player[victim] += 1
                    # Get role of victim
                    if victim in roles:
                        death_by_role[roles[victim]] += 1
        except Exception as e:
            pass
    
    print(f"\n{name}")
    print("="*50)
    print(f"Role draw modes: {dict(role_modes)}")
    print(f"\nDeaths by PLAYER ID (turn order):")
    for p in ['P1', 'P2', 'P3', 'P4']:
        count = death_by_player.get(p, 0)
        pct = count/sum(death_by_player.values())*100 if death_by_player else 0
        print(f"  {p}: {count} ({pct:.1f}%)")
    
    print(f"\nDeaths by ROLE:")
    for role, count in sorted(death_by_role.items(), key=lambda x: -x[1]):
        pct = count/sum(death_by_role.values())*100 if death_by_role else 0
        print(f"  {role}: {count} ({pct:.1f}%)")

goal_path = 'runs/runs_v8a81e15_main_20260128_203713_goal_randomking'
habitante_path = 'runs/runs_v8a81e15_main_20260128_201003_habitante_randomking'

if os.path.exists(goal_path):
    analyze_deaths(goal_path, "GOAL Policy")
if os.path.exists(habitante_path):
    analyze_deaths(habitante_path, "HABITANTE Policy")

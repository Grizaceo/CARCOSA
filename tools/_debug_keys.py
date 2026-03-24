"""Debug single game to understand key collection progress."""
import sys
sys.path.insert(0, '/home/gris/.openclaw/workspace/repos/CARCOSA')
from sim.runner import run_episode, make_smoke_state
from sim.policies import GoalDirectedPlayerPolicy

policy = GoalDirectedPlayerPolicy()
# Try a few losing seeds to understand the pattern
for seed in [1, 4, 5, 7, 20, 25, 40]:
    state = make_smoke_state(seed=seed)
    result = run_episode(
        state,
        {'P1': policy, 'P2': policy, 'P3': policy, 'P4': policy},
        max_steps=900,
        verbose=False
    )
    if isinstance(result, dict):
        outcome = result.get('outcome') or result.get('result') or result.get('win')
        keys = result.get('keys_collected') or result.get('keys_total') or '?'
        print(f"seed={seed}: outcome={outcome}, keys={keys}")
        print("  available keys:", [k for k in result.keys() if 'key' in k.lower()])
        if seed == 1:
            print("  full result:", {k: v for k, v in result.items() if not isinstance(v, list) or len(str(v)) < 200})
    else:
        print(f"seed={seed}: result type={type(result)}, attrs={[x for x in dir(result) if not x.startswith('_')][:15]}")

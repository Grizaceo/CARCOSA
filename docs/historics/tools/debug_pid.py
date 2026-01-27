#!/usr/bin/env python3
"""Debug: verificar _current_player_id."""
import sys
sys.path.insert(0, "/home/gris/carcosa")

from engine.config import Config
from engine.rng import RNG
from sim.runner import make_smoke_state
from engine.legality import _current_player_id, get_legal_actions
from engine.types import PlayerId

cfg = Config()
seed = 1
state = make_smoke_state(seed=seed, cfg=cfg)

# Simular hasta step 4
for i in range(4):
    pid = _current_player_id(state)
    print(f"Step {i}: _current_player_id={pid}, turn_pos={state.turn_pos}, turn_order={state.turn_order}")
    from sim.policies import GoalDirectedPlayerPolicy
    ppol = GoalDirectedPlayerPolicy(cfg)
    rng = RNG(seed)
    action = ppol.choose(state, rng)
    from engine.transition import step
    state = step(state, action, rng, cfg)

# Now step 4
print(f"\nStep 4 (error point):")
print(f"  turn_pos={state.turn_pos}")
print(f"  turn_order={state.turn_order}")
print(f"  game_over={state.game_over}")
print(f"  phase={state.phase}")

try:
    pid = _current_player_id(state)
    print(f"  _current_player_id={pid}")
except Exception as e:
    print(f"  ERROR in _current_player_id: {e}")

print(f"  get_legal_actions(state, 'P2'):")
try:
    acts = get_legal_actions(state, 'P2')
    print(f"    {acts}")
except Exception as e:
    print(f"    ERROR: {e}")

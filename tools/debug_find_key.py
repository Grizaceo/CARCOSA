#!/usr/bin/env python3
"""Debug: simular hasta encontrar llave."""
import sys
sys.path.insert(0, "/home/gris/carcosa")

from engine.config import Config
from engine.rng import RNG
from sim.runner import make_smoke_state
from sim.policies import GoalDirectedPlayerPolicy
from engine.transition import step
from sim.metrics import _keys_in_hand

cfg = Config()
seed = 1
state = make_smoke_state(seed=seed, cfg=cfg)
ppol = GoalDirectedPlayerPolicy(cfg)
rng = RNG(seed)

print("=== Simulación hasta encontrar llave (max 100 steps) ===")
for step_idx in range(100):
    if state.game_over:
        print(f"Game over at step {step_idx}: {state.outcome}")
        break
    
    pid = state.turn_order[state.turn_pos]
    actor = str(pid)
    
    action = ppol.choose(state, rng)
    state = step(state, action, rng, cfg)
    
    keys_now = _keys_in_hand(state)
    if keys_now > 0:
        print(f"\n✓ Found key at step {step_idx}!")
        print(f"  Actor: {actor}")
        print(f"  Action: {action.type.value}")
        print(f"  Keys in hand: {keys_now}")
        break
    
    if step_idx % 20 == 0:
        print(f"Step {step_idx}: keys_in_hand={keys_now}, phase={state.phase}, round={state.round}")

if _keys_in_hand(state) == 0:
    print(f"\nNo key found after 100 steps. Final keys: {_keys_in_hand(state)}")

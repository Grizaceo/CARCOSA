#!/usr/bin/env python3
"""Debug: ver qué acciones son legales antes de error."""
import sys
sys.path.insert(0, "/home/gris/carcosa")

from engine.config import Config
from engine.rng import RNG
from sim.runner import make_smoke_state
from sim.policies import GoalDirectedPlayerPolicy
from engine.legality import get_legal_actions
from engine.transition import step

cfg = Config()
seed = 1
state = make_smoke_state(seed=seed, cfg=cfg)
ppol = GoalDirectedPlayerPolicy(cfg)
rng = RNG(seed)

print("=== Simular hasta error ===")
for step_idx in range(10):
    if state.game_over:
        break
    
    pid = state.turn_order[state.turn_pos]
    actor = str(pid)
    p = state.players[pid]
    
    legal_actions = get_legal_actions(state, actor)
    print(f"\nStep {step_idx}: actor={actor}, room={p.room}, remaining_actions={state.remaining_actions.get(pid, '?')}")
    print(f"  Legal actions: {[a.type.value + (' ' + str(a.data) if a.data else '') for a in legal_actions]}")
    
    action = ppol.choose(state, rng)
    print(f"  Policy chose: {action.type.value} {action.data}")
    
    # Check if action is in legal
    if action not in legal_actions:
        print(f"  ERROR: Action not in legal! {action}")
        for i, la in enumerate(legal_actions):
            if la.type == action.type and la.data == action.data:
                print(f"    Found matching legal action at index {i}")
                break
        break
    
    state = step(state, action, rng, cfg)
    print(f"  After step: remaining_actions={state.remaining_actions}")

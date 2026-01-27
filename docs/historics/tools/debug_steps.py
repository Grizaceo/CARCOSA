#!/usr/bin/env python3
"""Debug: ver qué carta se revela en MOVE."""
import sys
sys.path.insert(0, "/home/gris/carcosa")

from engine.config import Config
from engine.rng import RNG
from sim.runner import make_smoke_state
from sim.policies import GoalDirectedPlayerPolicy
from engine.transition import step
from engine.legality import get_legal_actions
from sim.metrics import _keys_in_hand

cfg = Config()
seed = 1
state = make_smoke_state(seed=seed, cfg=cfg)
ppol = GoalDirectedPlayerPolicy(cfg)
rng = RNG(seed)

# First 5 steps
for step_idx in range(5):
    print(f"\n=== Step {step_idx} ===")
    pid = state.turn_order[state.turn_pos]
    actor = str(pid)
    p = state.players[pid]
    print(f"Actor: {actor}, Room: {p.room}, Sanity: {p.sanity}, Keys: {p.keys}")
    
    acts = get_legal_actions(state, actor)
    action = ppol.choose(state, rng)
    print(f"Action: {action.type.value} {action.data}")
    
    state = step(state, action, rng, cfg)
    print(f"After step:")
    print(f"  Actor room: {state.players[pid].room}")
    print(f"  Keys in hand: {_keys_in_hand(state)}")

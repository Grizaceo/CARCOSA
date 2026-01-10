#!/usr/bin/env python3
"""Debug: inspeccionar primer paso completo."""
import sys
sys.path.insert(0, "/home/gris/carcosa")

from engine.config import Config
from engine.rng import RNG
from sim.runner import make_smoke_state
from sim.policies import GoalDirectedPlayerPolicy
from engine.transition import step
from engine.legality import get_legal_actions

cfg = Config()
seed = 1
state = make_smoke_state(seed=seed, cfg=cfg)
ppol = GoalDirectedPlayerPolicy(cfg)
rng = RNG(seed)

print("=== First Step Debug ===")
print(f"Player P1 is at: {state.players['P1'].room}")
print(f"Is corridor? {str(state.players['P1'].room).endswith('_P')}")

# Get legal actions
pid = state.turn_order[state.turn_pos]
actor = str(pid)
p = state.players[pid]
print(f"\nCurrent actor: {actor}")
print(f"Current room: {p.room}")

acts = get_legal_actions(state, actor)
print(f"\nLegal actions ({len(acts)}):")
for i, a in enumerate(acts):
    print(f"  {i}: {a.type.value} {a.data}")

# Get policy choice
action = ppol.choose(state, rng)
print(f"\nPolicy chose: {action.type.value} {action.data}")

# Step it
state2 = step(state, action, rng, cfg)
print(f"\nAfter step:")
print(f"  P1 room: {state2.players['P1'].room}")
print(f"  P1 keys: {state2.players['P1'].keys}")
print(f"  P1 remaining_actions: {state2.remaining_actions.get('P1', '?')}")

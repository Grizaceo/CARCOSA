#!/usr/bin/env python3
"""Debug: simular full rounds."""
import sys
sys.path.insert(0, "/home/gris/carcosa")

from engine.config import Config
from engine.rng import RNG
from sim.runner import run_episode
from sim.metrics import _keys_in_hand

# Ejecutar 1 episode con seed 1
state = run_episode(max_steps=400, seed=1)

print(f"\n=== Final State ===")
print(f"Game over: {state.game_over}")
print(f"Outcome: {state.outcome}")
print(f"Round: {state.round}")
print(f"Keys in hand: {_keys_in_hand(state)}")

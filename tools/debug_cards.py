#!/usr/bin/env python3
"""Debug: ver qué carta se revela en cada paso."""
import sys
sys.path.insert(0, "/home/gris/carcosa")

from engine.config import Config
from engine.rng import RNG
from sim.runner import make_smoke_state
from engine.transition import _reveal_one
from engine.types import RoomId

cfg = Config()
seed = 1
state = make_smoke_state(seed=seed, cfg=cfg)

# Inspect room F1_R1
room = state.rooms[RoomId("F1_R1")]
print("F1_R1 initial state:")
print(f"  cards: {room.deck.cards}")
print(f"  top: {room.deck.top}")
print(f"  remaining: {room.deck.remaining()}")

# Reveal one
card1 = _reveal_one(state, RoomId("F1_R1"))
print(f"\nAfter first _reveal_one:")
print(f"  returned card: {card1}")
print(f"  top: {room.deck.top}")
print(f"  remaining: {room.deck.remaining()}")

# Reveal another
card2 = _reveal_one(state, RoomId("F1_R1"))
print(f"\nAfter second _reveal_one:")
print(f"  returned card: {card2}")
print(f"  top: {room.deck.top}")
print(f"  remaining: {room.deck.remaining()}")

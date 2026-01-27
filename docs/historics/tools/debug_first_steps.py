#!/usr/bin/env python3
"""Debug: inspeccionar primeros pasos de simulación."""
import sys
sys.path.insert(0, "/home/gris/carcosa")

from engine.config import Config
from engine.rng import RNG
from sim.runner import make_smoke_state
from sim.metrics import _keys_in_hand, _keys_in_game

cfg = Config()
seed = 1
state = make_smoke_state(seed=seed, cfg=cfg)

print("=== Initial State ===")
print(f"Round: {state.round}")
print(f"Phase: {state.phase}")
print(f"Keys in hand: {_keys_in_hand(state)}")
print(f"Keys in game: {_keys_in_game(state, cfg)}")
print(f"\nPlayers:")
for pid, p in state.players.items():
    print(f"  {pid}: room={p.room}, sanity={p.sanity}, keys={p.keys}")

print(f"\nRooms (top 5):")
for rid, room in list(state.rooms.items())[:5]:
    print(f"  {rid}: deck.remaining()={room.deck.remaining()}, total_cards={len(room.deck.cards)}, top={room.deck.top}")
    if room.deck.cards:
        print(f"       cards[:3] = {room.deck.cards[:min(3, len(room.deck.cards))]}")

print(f"\nTurn order: {state.turn_order}")
print(f"Remaining actions: {state.remaining_actions}")

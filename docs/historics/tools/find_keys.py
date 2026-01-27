#!/usr/bin/env python3
"""Debug: encontrar dónde están las llaves."""
import sys
sys.path.insert(0, "/home/gris/carcosa")

from engine.config import Config
from sim.runner import make_smoke_state

cfg = Config()
seed = 1
state = make_smoke_state(seed=seed, cfg=cfg)

print("=== Búsqueda de llaves ===")
key_locations = []
for rid, room in state.rooms.items():
    for i, card in enumerate(room.deck.cards):
        if str(card) == "KEY":
            key_locations.append((rid, i, room.deck.cards))
            print(f"KEY en {rid} en posición {i}")
            print(f"  Contexto: ...{room.deck.cards[max(0,i-1):min(len(room.deck.cards),i+2)]}...")

print(f"\nTotal llaves encontradas: {len(key_locations)}")
print(f"Configuración KEYS_TOTAL: {cfg.KEYS_TOTAL}")

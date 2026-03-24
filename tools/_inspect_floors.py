"""Inspect floor structure of CARCOSA game."""
import sys
sys.path.insert(0, '/home/gris/.openclaw/workspace/repos/CARCOSA')
from engine.board import floor_of
from engine.types import RoomId
from sim.runner import make_smoke_state

s = make_smoke_state(seed=1)
floors = sorted(set(floor_of(rid) for rid in s.rooms))
print('Available floors:', floors)
print('King floor:', s.king_floor)
import engine.config as cfg_mod
print('Config attrs:', [x for x in dir(cfg_mod) if x.isupper()])

rooms_per_floor = {}
for rid in s.rooms:
    f = floor_of(rid)
    rooms_per_floor.setdefault(f, []).append(str(rid))
for f, rs in sorted(rooms_per_floor.items()):
    non_p = [r for r in rs if not r.endswith('_P')]
    print(f'Floor {f}: {len(rs)} rooms total, {len(non_p)} searchable -> {non_p[:6]}')

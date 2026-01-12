#!/usr/bin/env python3
"""Fix engine/board.py with canonical adjacencies (P0.1)"""

code = '''from __future__ import annotations
from typing import List, Tuple
from engine.types import RoomId


FLOORS = 3
ROOMS_PER_FLOOR = 4


def floor_of(room_id: RoomId) -> int:
    # "F2_R3" o "F2_P"
    prefix = str(room_id).split("_")[0]
    return int(prefix[1:])


def is_corridor(room_id: RoomId) -> bool:
    return str(room_id).endswith("_P")


def corridor_id(floor: int) -> RoomId:
    return RoomId(f"F{floor}_P")


def room_id(floor: int, n: int) -> RoomId:
    return RoomId(f"F{floor}_R{n}")


def room_from_d4(floor: int, roll: int) -> RoomId:
    # d4 => R1..R4
    r = ((roll - 1) % ROOMS_PER_FLOOR) + 1
    return room_id(floor, r)


def neighbors(room: RoomId) -> List[RoomId]:
    f = floor_of(room)
    if is_corridor(room):
        return [room_id(f, i) for i in range(1, ROOMS_PER_FLOOR + 1)]
    # habitación conecta a pasillo del piso (1 movimiento)
    neighbors_list = [corridor_id(f)]
    # Agregar conexiones directas canónicas (1 movimiento):
    # R1 <-> R2, R3 <-> R4
    room_num = int(str(room).split("R")[1])
    if room_num == 1:
        neighbors_list.append(room_id(f, 2))
    elif room_num == 2:
        neighbors_list.append(room_id(f, 1))
    elif room_num == 3:
        neighbors_list.append(room_id(f, 4))
    elif room_num == 4:
        neighbors_list.append(room_id(f, 3))
    return neighbors_list


def ruleta_floor(start_floor: int, d4: int) -> int:
    # Sistema de ruleta: cuenta hacia arriba d4 pisos, wrap en 1..3.
    return ((start_floor - 1 + d4) % FLOORS) + 1
'''

with open('engine/board.py', 'w') as f:
    f.write(code)
print('✓ engine/board.py regenerated with canonical adjacencies')

from __future__ import annotations
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
    # habitación conecta a pasillo del piso
    return [corridor_id(f)]


def ruleta_floor(start_floor: int, d4: int) -> int:
    # Sistema de ruleta: cuenta hacia arriba d4 pisos, wrap en 1..3. :contentReference[oaicite:2]{index=2}
    return ((start_floor - 1 + d4) % FLOORS) + 1

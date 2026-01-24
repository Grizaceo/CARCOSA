from __future__ import annotations
from typing import Dict, List, Tuple
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


def canonical_room_ids() -> List[RoomId]:
    return [room_id(f, r) for f in range(1, FLOORS + 1) for r in range(1, ROOMS_PER_FLOOR + 1)]


SUSHI_CYCLE: Dict[RoomId, RoomId] = {
    room_id(1, 1): room_id(1, 4),
    room_id(1, 4): room_id(1, 3),
    room_id(1, 3): room_id(1, 2),
    room_id(1, 2): room_id(2, 3),
    room_id(2, 3): room_id(2, 2),
    room_id(2, 2): room_id(3, 3),
    room_id(3, 3): room_id(3, 2),
    room_id(3, 2): room_id(3, 1),
    room_id(3, 1): room_id(3, 4),
    room_id(3, 4): room_id(2, 1),
    room_id(2, 1): room_id(2, 4),
    room_id(2, 4): room_id(1, 1),
}


def rotate_boxes(box_at_room: Dict[RoomId, str]) -> Dict[RoomId, str]:
    _validate_box_mapping(box_at_room)
    rotated = dict(box_at_room)
    for src, dst in SUSHI_CYCLE.items():
        if src in box_at_room:
            rotated[dst] = box_at_room[src]
    return rotated


def rotate_boxes_intra_floor(box_at_room: Dict[RoomId, str]) -> Dict[RoomId, str]:
    """
    Rotación intra-piso: R1->R4->R3->R2->R1 en cada piso.
    No cruza pisos.
    """
    _validate_box_mapping(box_at_room)
    rotated = dict(box_at_room)
    
    # Ciclo por piso: R1 (src) -> R4 (dst) ??? 
    # Espérate, el ciclo P0 dice: R1->R4->R3->R2->R1 ??
    # El prompt dice: (R1→R4→R3→R2→R1 por piso).
    # O sea:
    # R1 va a R4? No, R1 es source, R4 es destination?
    # R1 -> R4
    # R4 -> R3
    # R3 -> R2
    # R2 -> R1
    
    for floor in range(1, FLOORS + 1):
        # Mapeo intra-piso
        cycle = {
            room_id(floor, 1): room_id(floor, 4),
            room_id(floor, 4): room_id(floor, 3),
            room_id(floor, 3): room_id(floor, 2),
            room_id(floor, 2): room_id(floor, 1),
        }
        for src, dst in cycle.items():
            if src in box_at_room:
                rotated[dst] = box_at_room[src]
                
    return rotated


def _validate_box_mapping(box_at_room: Dict[RoomId, str]) -> None:
    canonical = set(canonical_room_ids())
    keys = set(box_at_room.keys())

    extra = sorted(str(k) for k in keys - canonical)
    missing = sorted(str(k) for k in canonical - keys)
    corridors = sorted(str(k) for k in keys if is_corridor(k))

    values = list(box_at_room.values())
    value_counts = {}
    for v in values:
        value_counts[v] = value_counts.get(v, 0) + 1
    duplicates = sorted(str(v) for v, c in value_counts.items() if c > 1)

    if extra or missing or corridors or duplicates:
        parts = []
        if missing:
            parts.append(f"missing={missing}")
        if extra:
            parts.append(f"extra={extra}")
        if corridors:
            parts.append(f"corridors={corridors}")
        if duplicates:
            parts.append(f"duplicate_box_ids={duplicates}")
        detail = "; ".join(parts)
        raise ValueError(f"Invalid box mapping: {detail}")


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


def bfs_dist_to_targets(start: RoomId, targets: set[RoomId]) -> int:
    """Retorna la distancia mínima desde start a cualquiera de los targets."""
    if start in targets:
        return 0
    
    queue = [(start, 0)]
    visited = {start}
    
    while queue:
        current, dist = queue.pop(0)
        
        # Check adjacent neighbors for targets in case we popped a node that IS a target?
        # No, current is popped from queue. Check if current is target?
        # Wait, if `start` is target, handled above.
        # Use queue check.
        
        if current in targets:
            return dist
        
        for nb in neighbors(current):
            if nb not in visited:
                if nb in targets:
                     return dist + 1
                visited.add(nb)
                queue.append((nb, dist + 1))
                
    return 999  # Unreachable


def get_next_move_to_targets(start: RoomId, targets: set[RoomId]) -> RoomId:
    """
    Retorna el vecino de start que minimiza la distancia a los targets.
    Si start ya está en targets o no hay camino, retorna start.
    Priority: Primer vecino que cumple (orden de neighbors).
    """
    if start in targets:
        return start
        
    best_step = start
    min_dist = 999
    
    # Evaluar cada vecino
    for nb in neighbors(start):
        d = bfs_dist_to_targets(nb, targets)
        if d < min_dist:
            min_dist = d
            best_step = nb
            
    return best_step


def get_next_move_away_from_targets(start: RoomId, targets: set[RoomId]) -> RoomId:
    """
    Retorna el vecino de start que maximiza la distancia al target más cercano.
    Flee logic.
    """
    best_step = start
    max_dist = -1
    
    # Evaluar cada vecino
    for nb in neighbors(start):
        # Distancia desde el vecino al target más cercano
        d = bfs_dist_to_targets(nb, targets)
        if d > max_dist:
            max_dist = d
            best_step = nb
            
    return best_step

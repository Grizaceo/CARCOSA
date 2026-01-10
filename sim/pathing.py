from __future__ import annotations
from collections import deque
from typing import Dict, List, Optional, Set

from engine.board import neighbors, corridor_id, floor_of
from engine.state import GameState
from engine.types import RoomId


def adjacency(state: GameState) -> Dict[RoomId, List[RoomId]]:
    """
    Grafo de movimiento coherente con engine/legality.py:
    - vecinos pasillo<->habitaciones (mismo piso)
    - transición vertical solo desde la habitación que tiene escalera del piso.
    """
    adj: Dict[RoomId, List[RoomId]] = {}

    # Nodos existentes: tomamos rooms del estado
    nodes: Set[RoomId] = set(state.rooms.keys())
    # Por si los pasillos no están en rooms (en tu smoke sí están), los agregamos
    for f in (1, 2, 3):
        nodes.add(corridor_id(f))

    for node in nodes:
        adj[node] = []

    # vecinos horizontales según board.neighbors
    for node in list(nodes):
        for nb in neighbors(node):
            if nb in nodes:
                adj[node].append(nb)

    # vecinos verticales (desde escalera)
    for f, stair_room in state.stairs.items():
        if stair_room not in nodes:
            continue
        if f > 1:
            adj[stair_room].append(corridor_id(f - 1))
        if f < 3:
            adj[stair_room].append(corridor_id(f + 1))

    return adj


def bfs_next_step(state: GameState, start: RoomId, goal: RoomId) -> Optional[RoomId]:
    if start == goal:
        return None

    adj = adjacency(state)

    q = deque([start])
    prev: Dict[RoomId, Optional[RoomId]] = {start: None}

    while q:
        cur = q.popleft()
        if cur == goal:
            break
        for nb in adj.get(cur, []):
            if nb not in prev:
                prev[nb] = cur
                q.append(nb)

    if goal not in prev:
        return None

    # reconstruir: desde goal hacia start, devolver el primer paso
    cur = goal
    while prev[cur] is not None and prev[cur] != start:
        cur = prev[cur]
    return cur if prev[cur] == start else goal

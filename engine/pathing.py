from __future__ import annotations

from collections import deque
from typing import Iterable

from engine.board import floor_of, is_corridor, neighbors
from engine.state import GameState
from engine.types import RoomId


def _graph_neighbors(state: GameState, room: RoomId) -> Iterable[RoomId]:
    """Vecinos considerando pasillos y conexiones por escaleras permanentes."""
    for nb in neighbors(room):
        yield nb

    f = floor_of(room)
    if room == state.stairs.get(f):
        if f > 1:
            dest = state.stairs.get(f - 1)
            if dest:
                yield dest
        if f < 3:
            dest = state.stairs.get(f + 1)
            if dest:
                yield dest


def find_nearest_empty_room(state: GameState, origin: RoomId) -> RoomId:
    """
    Busca la habitación más cercana sin jugadores.
    Prioriza habitaciones (no pasillos); si no encuentra, retorna origin.
    """
    occupied = {p.room for p in state.players.values()}

    queue = deque([origin])
    visited = {origin}

    while queue:
        current = queue.popleft()
        if current not in occupied and not is_corridor(current):
            return current
        for nb in _graph_neighbors(state, current):
            if nb not in visited:
                visited.add(nb)
                queue.append(nb)

    return origin


__all__ = ["find_nearest_empty_room"]

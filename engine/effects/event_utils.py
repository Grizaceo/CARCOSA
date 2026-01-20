"""
Funciones de utilidad para eventos.

Estas funciones son reutilizadas por múltiples eventos del juego.
"""

from engine.state import GameState, PlayerState, StatusInstance
from engine.types import PlayerId, RoomId
from typing import List


def swap_positions(s: GameState, pid1: PlayerId, pid2: PlayerId) -> None:
    """Intercambia ubicación de dos jugadores."""
    p1, p2 = s.players[pid1], s.players[pid2]
    p1.room, p2.room = p2.room, p1.room


def move_player_to_room(s: GameState, pid: PlayerId, room: RoomId) -> None:
    """Mueve un jugador a una habitación específica."""
    s.players[pid].room = room


def remove_all_statuses(p: PlayerState) -> None:
    """Remueve todos los estados de un jugador."""
    p.statuses = []


def remove_status(p: PlayerState, status_id: str) -> bool:
    """Remueve un estado específico. Retorna True si existía."""
    original_len = len(p.statuses)
    p.statuses = [st for st in p.statuses if st.status_id != status_id]
    return len(p.statuses) < original_len


def add_status(p: PlayerState, status_id: str, duration: int = 2) -> None:
    """Agrega un estado con duración."""
    p.statuses.append(StatusInstance(status_id=status_id, remaining_rounds=duration))


def get_player_by_turn_offset(s: GameState, pid: PlayerId, offset: int) -> PlayerId:
    """
    Obtiene jugador a la derecha (+1) o izquierda (-1) según orden de turno.
    """
    idx = s.turn_order.index(pid)
    new_idx = (idx + offset) % len(s.turn_order)
    return s.turn_order[new_idx]


def get_players_in_floor(s: GameState, floor: int) -> List[PlayerId]:
    """Retorna lista de jugadores en un piso."""
    from engine.board import floor_of
    return [pid for pid, p in s.players.items() if floor_of(p.room) == floor]


def invert_sanity(p: PlayerState) -> None:
    """Invierte la cordura: cordura_nueva = cordura_actual × (-1)"""
    p.sanity = -p.sanity

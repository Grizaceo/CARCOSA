"""
TANK Protection System — CARCOSA

Implements PROTECT_ALLY ability:
- TANK can receive damage instead of allies in same node
- TANK gains +1 shield at round start (absorbs first damage)
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from engine.state import GameState, PlayerState
    from engine.types import PlayerId


def can_protect(tank: "PlayerState", target: "PlayerState") -> bool:
    """
    TANK puede proteger a target si:
    1. tank tiene role_id == "TANK"
    2. tank y target están en el mismo nodo (room)
    3. tank no es el mismo que target
    4. tank tiene cordura > -5 (no está derrotado)
    """
    return (
        getattr(tank, "role_id", "") == "TANK"
        and tank.room == target.room
        and tank.player_id != target.player_id
        and tank.sanity > -5
    )


def find_tank_protector(state: "GameState", target_pid: "PlayerId") -> Optional["PlayerState"]:
    """
    Busca un TANK que pueda proteger al jugador target.
    Retorna None si no hay TANK disponible en el mismo nodo.
    """
    target = state.players.get(target_pid)
    if not target:
        return None
    
    for p in state.players.values():
        if can_protect(p, target):
            return p
    return None


def apply_tank_shields(state: "GameState") -> None:
    """
    Aplica escudo +1 a todos los TANK al inicio de ronda.
    Llamar desde el sistema de fin de ronda antes del siguiente turno.
    """
    for p in state.players.values():
        if getattr(p, "role_id", "") == "TANK":
            p.shield = getattr(p, "shield", 0) + 1


def apply_damage_with_protection(
    state: "GameState",
    target_pid: "PlayerId",
    damage: int,
    source: str = "UNKNOWN",
    allow_tank_protection: bool = True,
) -> int:
    """
    Aplica daño a un jugador con soporte para:
    1. Escudo del jugador (absorbe daño primero)
    2. Protección del TANK (puede recibir daño en su lugar)
    
    Args:
        state: GameState actual
        target_pid: ID del jugador objetivo del daño
        damage: Cantidad de daño a aplicar (positivo)
        source: Fuente del daño para logging
        allow_tank_protection: Si True, permite que un TANK proteja
        
    Returns:
        Daño real aplicado al target original (puede ser 0 si TANK absorbió)
    """
    if damage <= 0:
        return 0
    
    target = state.players.get(target_pid)
    if not target:
        return 0
    
    # 1. Buscar TANK protector si está permitido
    if allow_tank_protection and getattr(target, "role_id", "") != "TANK":
        protector = find_tank_protector(state, target_pid)
        if protector:
            # TANK recibe el daño en lugar del target
            return _apply_damage_to_player(protector, damage, source)
    
    # 2. Aplicar daño al target original
    return _apply_damage_to_player(target, damage, source)


def _apply_damage_to_player(player: "PlayerState", damage: int, source: str) -> int:
    """
    Aplica daño a un jugador específico, consumiendo escudo primero.
    
    Returns:
        Daño real aplicado a cordura (después de escudo)
    """
    remaining_damage = damage
    
    # Escudo absorbe primero
    shield = getattr(player, "shield", 0)
    if shield > 0:
        absorbed = min(shield, remaining_damage)
        player.shield = shield - absorbed
        remaining_damage -= absorbed
    
    # Resto va a cordura
    if remaining_damage > 0:
        player.sanity -= remaining_damage
    
    return remaining_damage


__all__ = [
    "can_protect",
    "find_tank_protector",
    "apply_tank_shields",
    "apply_damage_with_protection",
]

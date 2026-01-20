"""
Sistema de objetos con efectos.

Define el catálogo de objetos y sus efectos cuando se usan.
"""

from dataclasses import dataclass
from typing import Optional
from engine.state import GameState, PlayerState
from engine.types import PlayerId


@dataclass
class ObjectDefinition:
    object_id: str
    name: str
    uses: Optional[int]  # None = infinito, 1 = consumible
    is_blunt: bool = False  # Objeto contundente
    is_treasure: bool = False


# Catálogo de objetos existentes
OBJECT_CATALOG = {
    "COMPASS": ObjectDefinition("COMPASS", "Brújula", uses=1, is_blunt=False),
    "VIAL": ObjectDefinition("VIAL", "Vial", uses=1, is_blunt=False),
    "BLUNT": ObjectDefinition("BLUNT", "Objeto Contundente", uses=1, is_blunt=True),
    "ROPE": ObjectDefinition("ROPE", "Cuerda", uses=1, is_blunt=False),
}


def use_object(s: GameState, pid: PlayerId, object_id: str, cfg, rng) -> bool:
    """
    Usa un objeto del inventario.
    Retorna True si se usó exitosamente.
    """
    p = s.players[pid]
    if object_id not in p.objects:
        return False

    obj_def = OBJECT_CATALOG.get(object_id)
    if obj_def is None:
        return False

    # Aplicar efecto según tipo
    if object_id == "COMPASS":
        _use_compass(s, pid, cfg)
    elif object_id == "VIAL":
        _use_vial(s, pid, cfg)
    elif object_id == "BLUNT":
        _use_blunt(s, pid, cfg)
    # ... más objetos ...

    # Consumir si tiene usos limitados
    if obj_def.uses is not None:
        p.objects.remove(object_id)

    return True


def _use_compass(s: GameState, pid: PlayerId, cfg) -> None:
    """Brújula: Mueve al pasillo del piso actual. Acción gratuita."""
    from engine.board import floor_of, corridor_id
    p = s.players[pid]
    floor = floor_of(p.room)
    p.room = corridor_id(floor)


def _use_vial(s: GameState, pid: PlayerId, cfg) -> None:
    """Vial: Recupera 2 de cordura. Acción gratuita."""
    p = s.players[pid]
    p.sanity = min(p.sanity + 2, p.sanity_max or p.sanity + 2)


def _use_blunt(s: GameState, pid: PlayerId, cfg) -> None:
    """
    Objeto Contundente: Aturde monstruo en la habitación por 2 rondas.
    SUPUESTO: Se marca en flags del GameState.
    """
    p = s.players[pid]
    for monster in s.monsters:
        if monster.room == p.room:
            s.flags[f"STUN_{monster.monster_id}_UNTIL_ROUND"] = s.round + 2
            break

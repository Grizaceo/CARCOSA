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
    # Tesoros
    "TREASURE_RING": ObjectDefinition("TREASURE_RING", "Llavero", uses=None, is_blunt=False, is_treasure=True),
    "TREASURE_STAIRS": ObjectDefinition("TREASURE_STAIRS", "Escaleras", uses=3, is_blunt=False, is_treasure=True),
    "TREASURE_CROWN": ObjectDefinition("TREASURE_CROWN", "Corona", uses=None, is_blunt=False, is_treasure=True),
    "TREASURE_SCROLL": ObjectDefinition("TREASURE_SCROLL", "Pergamino", uses=None, is_blunt=False, is_treasure=True),
    "TREASURE_PENDANT": ObjectDefinition("TREASURE_PENDANT", "Colgante", uses=None, is_blunt=False, is_treasure=True),
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
    elif object_id == "TREASURE_STAIRS":
        _use_treasure_stairs(s, pid, cfg)
    # Nota: TREASURE_RING tiene efecto pasivo, no se "usa"
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
    CORRECCIÓN B: Objeto Contundente aturde monstruo en la habitación por 2 turnos.

    - Busca monstruo en misma habitación que el jugador
    - Aplica STUN de 2 turnos (excepto Rey de Amarillo, que es inmune)
    - Se consume al usarse (1 uso)
    """
    p = s.players[pid]
    for monster in s.monsters:
        if monster.room == p.room:
            # Rey de Amarillo es inmune al STUN
            if "YELLOW_KING" not in monster.monster_id and "KING" not in monster.monster_id:
                monster.stunned_remaining_rounds = max(monster.stunned_remaining_rounds, 2)
            break


def _use_treasure_stairs(s: GameState, pid: PlayerId, cfg) -> None:
    """
    Escaleras (Tesoro): 3 usos. Coloca escalera temporal en habitación actual.
    Dura hasta fin de ronda.
    """
    p = s.players[pid]
    # Registrar escalera temporal
    s.flags[f"TEMP_STAIRS_{p.room}"] = s.round  # Válida solo esta ronda

    # Decrementar usos (manejado automáticamente por el sistema en use_object)


def has_treasure_ring(p: PlayerState) -> bool:
    """Verifica si el jugador tiene el tesoro Llavero (efecto pasivo)."""
    return "TREASURE_RING" in p.objects


def get_max_keys_capacity(p: PlayerState) -> int:
    """
    Retorna la capacidad máxima de llaves del jugador.
    Base: 1 llave
    +1 si tiene Llavero (TREASURE_RING)
    """
    base_capacity = 1
    if has_treasure_ring(p):
        base_capacity += 1
    return base_capacity


def get_effective_sanity_max(p: PlayerState) -> int:
    """
    Retorna la cordura máxima efectiva del jugador.
    Base: sanity_max del jugador (o 5 si no está definido)
    +1 si tiene Llavero (TREASURE_RING)
    """
    base_max = p.sanity_max if p.sanity_max is not None else 5
    if has_treasure_ring(p):
        base_max += 1
    return base_max

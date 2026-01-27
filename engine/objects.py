"""
Sistema de objetos con efectos.

Define el catálogo de objetos y sus efectos cuando se usan.

SISTEMA CANÓNICO DE OBJETOS (2026-01-21):
=========================================

CATEGORÍAS:
-----------
1. OBJETO NORMAL: Consumible o permanente, NO soulbound
   - Ejemplos: Brújula, Vial, Contundente, Cuerda

2. TESORO: Objetos especiales del mazo de Motemey
   - Ejemplos: Llavero, Escaleras, Pergamino, Colgante

3. TESORO SOULBOUND: Ligados permanentemente al jugador
   - Corona: Activa Falso Rey, no ocupa slot
   - Anillo: Tesoro especial, no puede descartarse

REGLAS SOULBOUND:
-----------------
- NO se puede intercambiar, dropear ni transferir
- Efectos de descarte (d6=6 del Rey) NO eliminan objetos Soulbound
- No ocupan slots de objetos normales

NOTA: Las LLAVES son entidad separada (slot propio por rol de personaje)
"""

from dataclasses import dataclass
from typing import Optional

from engine.handlers.objects import get_object_use_handler, register_object_use
from engine.state import GameState, PlayerState
from engine.types import PlayerId


@dataclass
class ObjectDefinition:
    object_id: str
    name: str
    uses: Optional[int]  # None = permanente, N = consumible N usos
    is_blunt: bool = False  # Objeto contundente (stun monstruos)
    is_treasure: bool = False  # Es tesoro (viene de Motemey)
    is_soulbound: bool = False  # Es soulbound (no puede descartarse)
    can_react: bool = False  # Puede usarse como reacción (fuera del turno)


# ==============================================================================
# CATÁLOGO DE OBJETOS CANÓNICO
# ==============================================================================

OBJECT_CATALOG = {
    # --- OBJETOS NORMALES ---
    # Brújula: +1 movimiento gratis, consumible, usable como reacción
    "COMPASS": ObjectDefinition("COMPASS", "Brújula", uses=1, is_blunt=False, can_react=True),
    # Vial: +2 cordura, consumible, usable como reacción
    "VIAL": ObjectDefinition("VIAL", "Vial", uses=1, is_blunt=False, can_react=True),
    # Contundente: STUN monstruo 2 turnos, consumible
    "BLUNT": ObjectDefinition("BLUNT", "Objeto Contundente", uses=1, is_blunt=True, can_react=False),
    # Cuerda: uso por definir
    "ROPE": ObjectDefinition("ROPE", "Cuerda", uses=1, is_blunt=False),
    # Escalera Portátil: subir/bajar 1 piso, consumible
    "PORTABLE_STAIRS": ObjectDefinition("PORTABLE_STAIRS", "Escalera Portátil", uses=1, is_blunt=False),
    
    # --- CUENTOS DE AMARILLO (4 objetos, mecánicamente iguales) ---
    "TALE_REPAIRER": ObjectDefinition("TALE_REPAIRER", "El Reparador de Reputaciones", uses=None, is_blunt=False),
    "TALE_MASK": ObjectDefinition("TALE_MASK", "La Máscara", uses=None, is_blunt=False),
    "TALE_DRAGON": ObjectDefinition("TALE_DRAGON", "En la Corte del Dragón", uses=None, is_blunt=False),
    "TALE_SIGN": ObjectDefinition("TALE_SIGN", "El Signo de Amarillo", uses=None, is_blunt=False),

    # --- LIBRO (Soulbound) ---
    "BOOK_CHAMBERS": ObjectDefinition("BOOK_CHAMBERS", "El Rey de Amarillo", uses=None, is_soulbound=True),
    
    # --- TESOROS (de Motemey) ---
    "TREASURE_RING": ObjectDefinition("TREASURE_RING", "Llavero", uses=None, is_blunt=False, is_treasure=True),
    "TREASURE_STAIRS": ObjectDefinition("TREASURE_STAIRS", "Escaleras Tesoro", uses=3, is_blunt=False, is_treasure=True),
    "TREASURE_SCROLL": ObjectDefinition("TREASURE_SCROLL", "Pergamino", uses=None, is_blunt=False, is_treasure=True),
    "TREASURE_PENDANT": ObjectDefinition("TREASURE_PENDANT", "Colgante", uses=None, is_blunt=False, is_treasure=True),
    
    # --- TESOROS SOULBOUND ---
    # Corona: soulbound desde inicio, activa Falso Rey
    "CROWN": ObjectDefinition("CROWN", "Corona", uses=None, is_blunt=False, is_treasure=True, is_soulbound=True),
    # Anillo: tesoro normal hasta activarse, luego soulbound
    # Al activar: todos a max cordura, portador -2/turno después
    "RING": ObjectDefinition("RING", "Anillo", uses=None, is_blunt=False, is_treasure=True, is_soulbound=False),
    # Libro de Chambers: soulbound desde inicio, vanisher del Rey
    # "CHAMBERS_BOOK": ObjectDefinition("CHAMBERS_BOOK", "Libro de Chambers", uses=None, is_blunt=False, is_treasure=True, is_soulbound=True),
    # REEMPLAZADO POR "BOOK_CHAMBERS" arriba para consistencia con nombres canónicos
}


def is_soulbound(object_id: str) -> bool:
    """Retorna True si el objeto es soulbound (no puede descartarse)."""
    if object_id == "CHAMBERS_BOOK":
        object_id = "BOOK_CHAMBERS"
    obj_def = OBJECT_CATALOG.get(object_id)
    return obj_def.is_soulbound if obj_def else False


def can_discard(object_id: str) -> bool:
    """Retorna True si el objeto PUEDE ser descartado (no es soulbound)."""
    return not is_soulbound(object_id)



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

    # Aplicar efecto segun tipo
    handler = get_object_use_handler(object_id)
    if handler is not None:
        handler(s, pid, cfg, rng)
    # Nota: TREASURE_RING tiene efecto pasivo, no se "usa"
    # ... mas objetos ...

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
    p.sanity = min(p.sanity + 2, get_effective_sanity_max(p))


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
            # BABY_SPIDER: Stun = Muerte
            if "BABY_SPIDER" in monster.monster_id:
                  s.monsters.remove(monster)
                  # Log kill? flag?
                  # s.flags[f"KILLED_{monster.monster_id}"] = True
                  break

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


@register_object_use("COMPASS")
def _handle_object_compass(s: GameState, pid: PlayerId, cfg, rng) -> None:
    _use_compass(s, pid, cfg)


@register_object_use("VIAL")
def _handle_object_vial(s: GameState, pid: PlayerId, cfg, rng) -> None:
    _use_vial(s, pid, cfg)


@register_object_use("BLUNT")
def _handle_object_blunt(s: GameState, pid: PlayerId, cfg, rng) -> None:
    _use_blunt(s, pid, cfg)


@register_object_use("TREASURE_STAIRS")
def _handle_object_treasure_stairs(s: GameState, pid: PlayerId, cfg, rng) -> None:
    _use_treasure_stairs(s, pid, cfg)


def has_treasure_ring(p: PlayerState) -> bool:
    """Verifica si el jugador tiene el tesoro Llavero (efecto pasivo)."""
    return "TREASURE_RING" in p.objects


def get_max_keys_capacity(p: PlayerState) -> int:
    """
    Retorna la capacidad máxima de llaves del jugador.
    Base: slots por rol
    +1 si tiene Llavero (TREASURE_RING)
    """
    from engine.roles import get_key_slots
    base_capacity = get_key_slots(getattr(p, "role_id", ""))
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

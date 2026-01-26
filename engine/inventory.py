"""
Sistema de Inventario - CARCOSA

Maneja límites de objetos por rol, descarte, y operaciones de inventario.

Reglas canónicas:
- Cada rol tiene límites específicos de objetos y llaves
- Si obtiene objeto cuando está full → elige qué descartar
- Objetos soulbound no ocupan slots
- Objetos descartados van al pozo común
"""
from typing import List, Optional, Tuple
from engine.state import GameState, PlayerState
from engine.types import PlayerId
from engine.objects import OBJECT_CATALOG, is_soulbound, get_max_keys_capacity


# ==============================================================================
# LÍMITES DE INVENTARIO POR ROL
# ==============================================================================

# Definido según canon: {role_id: (key_slots, object_slots)}
ROLE_INVENTORY_LIMITS = {
    "HEALER": (1, 2),
    "TANK": (1, 3),
    "HIGH_ROLLER": (2, 2),
    "SCOUT": (1, 1),
    "BRAWLER": (1, 2),
    "PSYCHIC": (1, 2),
    # Default para roles no definidos
    "DEFAULT": (1, 2),
}


def get_inventory_limits(player: PlayerState) -> Tuple[int, int]:
    """
    Obtiene los límites de inventario para un jugador según su rol.
    
    Returns:
        Tuple[int, int]: (key_slots, object_slots)
    """
    role_id = getattr(player, "role_id", "DEFAULT")
    key_slots, object_slots = ROLE_INVENTORY_LIMITS.get(role_id, ROLE_INVENTORY_LIMITS["DEFAULT"])
    # Llavero (TREASURE_RING) aumenta la capacidad de llaves en +1
    key_slots = get_max_keys_capacity(player)
    # Penalidad por sacrificio reduce slots de objetos
    penalty = getattr(player, "object_slots_penalty", 0)
    object_slots = max(0, object_slots - penalty)
    return key_slots, object_slots


def get_object_count(player: PlayerState) -> int:
    """
    Cuenta objetos en inventario, excluyendo soulbound (no ocupan slot).
    """
    objects = getattr(player, "objects", [])
    return sum(1 for obj_id in objects if not is_soulbound(obj_id))


def get_key_count(player: PlayerState) -> int:
    """
    Cuenta llaves del jugador.
    """
    return getattr(player, "keys", 0)


def can_add_object(player: PlayerState, object_id: str) -> bool:
    """
    Verifica si el jugador puede agregar un objeto sin exceder límite.
    Objetos soulbound siempre pueden agregarse (no ocupan slot).
    """
    if is_soulbound(object_id):
        return True
    
    _, object_slots = get_inventory_limits(player)
    current_count = get_object_count(player)
    return current_count < object_slots


def can_add_key(player: PlayerState) -> bool:
    """
    Verifica si el jugador puede agregar una llave sin exceder límite.
    """
    key_slots = get_max_keys_capacity(player)
    current_keys = get_key_count(player)
    return current_keys < key_slots


def add_object(state: GameState, player_id: PlayerId, object_id: str, 
               discard_choice: Optional[str] = None) -> bool:
    """
    Agrega un objeto al inventario del jugador.
    
    Si el inventario está lleno:
    - Si discard_choice es el nuevo objeto → descarta el nuevo
    - Si discard_choice es un objeto existente → descarta ese y agrega el nuevo
    - Si discard_choice es None y está lleno → falla
    
    Args:
        state: Estado del juego
        player_id: ID del jugador
        object_id: ID del objeto a agregar
        discard_choice: ID del objeto a descartar (nuevo o existente)
    
    Returns:
        bool: True si se agregó exitosamente
    """
    player = state.players[player_id]
    objects = getattr(player, "objects", [])
    
    # Soulbound siempre se puede agregar
    if is_soulbound(object_id):
        if object_id not in objects:
            objects.append(object_id)
            player.objects = objects
            
            # Libro de Chambers se registra especialmente
            if object_id in ("BOOK_CHAMBERS", "CHAMBERS_BOOK"):
                state.chambers_book_holder = player_id
        return True
    
    # Verificar si cabe
    if can_add_object(player, object_id):
        objects.append(object_id)
        player.objects = objects
        
        # BOOK_CHAMBERS: registrar holder (aunque no sea soulbound)
        if object_id in ("BOOK_CHAMBERS", "CHAMBERS_BOOK"):
            state.chambers_book_holder = player_id
        
        return True
    
    # Inventario lleno - necesita descarte
    if discard_choice is None:
        return False  # No puede agregar sin descartar
    
    if discard_choice == object_id:
        # Descarta el nuevo objeto directamente
        state.discard_pile.append(object_id)
        return True
    
    if discard_choice in objects:
        # Descarta un objeto existente
        if is_soulbound(discard_choice):
            return False  # No puede descartar soulbound
        
        objects.remove(discard_choice)
        state.discard_pile.append(discard_choice)
        objects.append(object_id)
        player.objects = objects
        return True
    
    return False


def remove_object(state: GameState, player_id: PlayerId, object_id: str, 
                  to_discard: bool = True) -> bool:
    """
    Remueve un objeto del inventario.
    
    Args:
        state: Estado del juego
        player_id: ID del jugador
        object_id: ID del objeto a remover
        to_discard: Si True, va al pozo de descarte
    
    Returns:
        bool: True si se removió
    """
    player = state.players[player_id]
    objects = getattr(player, "objects", [])
    
    if object_id not in objects:
        return False
    
    if is_soulbound(object_id):
        return False  # No puede remover soulbound
    
    objects.remove(object_id)
    player.objects = objects
    
    if to_discard:
        state.discard_pile.append(object_id)
    
    return True


def consume_object(state: GameState, player_id: PlayerId, object_id: str) -> bool:
    """
    Consume un objeto (lo usa y lo descarta si es consumible).
    
    Returns:
        bool: True si se consumió
    """
    obj_def = OBJECT_CATALOG.get(object_id)
    if obj_def is None:
        return False
    
    player = state.players[player_id]
    objects = getattr(player, "objects", [])
    
    if object_id not in objects:
        return False
    
    # Si tiene usos limitados, consumir
    if obj_def.uses is not None:
        return remove_object(state, player_id, object_id, to_discard=True)
    
    return True  # Objeto permanente, no se consume


def is_tale_of_yellow(object_id: str) -> bool:
    """Verifica si un objeto es un Cuento de Amarillo."""
    return object_id in ("TALE_REPAIRER", "TALE_MASK", "TALE_DRAGON", "TALE_SIGN")


def attach_tale_to_chambers(state: GameState, player_id: PlayerId, tale_id: str) -> bool:
    """
    Une un Cuento de Amarillo al Libro de Chambers.
    
    Efectos:
    - Remueve el cuento del inventario (ya no ocupa slot)
    - Incrementa chambers_tales_attached
    - Aplica vanish al Rey (1, 2, 3, o 4 turnos según número de cuento)
    
    Returns:
        bool: True si se unió exitosamente
    """
    if state.chambers_book_holder != player_id:
        return False  # Solo el portador del Libro puede unir cuentos
    
    if not is_tale_of_yellow(tale_id):
        return False
    
    player = state.players[player_id]
    objects = getattr(player, "objects", [])
    
    if tale_id not in objects:
        return False
    
    # Remover cuento del inventario (no va a descarte, se "une" al libro)
    objects.remove(tale_id)
    player.objects = objects
    
    # Incrementar contador y aplicar vanish
    state.chambers_tales_attached += 1
    vanish_turns = state.chambers_tales_attached  # 1, 2, 3, o 4 turnos
    state.king_vanished_turns = vanish_turns
    
    return True

from __future__ import annotations

from typing import Optional, Tuple

from engine.catalogs.roles import ROLE_INVENTORY_LIMITS
from engine.objects import OBJECT_CATALOG, get_max_keys_capacity, is_soulbound
from engine.state import GameState, PlayerState
from engine.types import PlayerId

def get_inventory_limits(player: PlayerState) -> Tuple[int, int]:
    """
    Return inventory limits for a player according to their role.

    Returns:
        (key_slots, object_slots)
    """
    role_id = getattr(player, "role_id", "DEFAULT")
    key_slots, object_slots = ROLE_INVENTORY_LIMITS.get(role_id, ROLE_INVENTORY_LIMITS["DEFAULT"])
    # Key capacity may be boosted by objects (e.g., TREASURE_RING).
    key_slots = get_max_keys_capacity(player)
    # Sacrifice penalty reduces object slots.
    penalty = getattr(player, "object_slots_penalty", 0)
    object_slots = max(0, object_slots - penalty)
    return key_slots, object_slots


def get_object_count(player: PlayerState) -> int:
    """Count non-soulbound objects in inventory."""
    objects = getattr(player, "objects", [])
    return sum(1 for obj_id in objects if not is_soulbound(obj_id))


def get_key_count(player: PlayerState) -> int:
    """Count keys in inventory."""
    return getattr(player, "keys", 0)


def can_add_object(player: PlayerState, object_id: str) -> bool:
    """
    Check if an object can be added without exceeding limits.
    Soulbound objects always fit.
    """
    if is_soulbound(object_id):
        return True
    _, object_slots = get_inventory_limits(player)
    return get_object_count(player) < object_slots


def can_add_key(player: PlayerState) -> bool:
    """Check if a key can be added without exceeding limits."""
    key_slots = get_max_keys_capacity(player)
    return get_key_count(player) < key_slots


def add_object(state: GameState, player_id: PlayerId, object_id: str,
               discard_choice: Optional[str] = None) -> bool:
    """
    Add an object to player inventory.

    If inventory is full:
    - discard_choice == new object -> discard new object
    - discard_choice == existing object -> discard that and add new
    - discard_choice is None -> fail
    """
    player = state.players[player_id]
    objects = getattr(player, "objects", [])

    if is_soulbound(object_id):
        if object_id not in objects:
            objects.append(object_id)
            player.objects = objects
            if object_id in ("BOOK_CHAMBERS", "CHAMBERS_BOOK"):
                state.chambers_book_holder = player_id
        return True

    if can_add_object(player, object_id):
        objects.append(object_id)
        player.objects = objects
        if object_id in ("BOOK_CHAMBERS", "CHAMBERS_BOOK"):
            state.chambers_book_holder = player_id
        return True

    if discard_choice is None:
        return False

    if discard_choice == object_id:
        state.discard_pile.append(object_id)
        return True

    if discard_choice in objects:
        if is_soulbound(discard_choice):
            return False
        objects.remove(discard_choice)
        state.discard_pile.append(discard_choice)
        objects.append(object_id)
        player.objects = objects
        return True

    return False


def remove_object(state: GameState, player_id: PlayerId, object_id: str,
                  to_discard: bool = True) -> bool:
    """Remove an object from inventory (optionally to discard pile)."""
    player = state.players[player_id]
    objects = getattr(player, "objects", [])
    if object_id not in objects:
        return False
    if is_soulbound(object_id):
        return False
    objects.remove(object_id)
    player.objects = objects
    if to_discard:
        state.discard_pile.append(object_id)
    return True


def consume_object(state: GameState, player_id: PlayerId, object_id: str) -> bool:
    """Consume an object (discard if it has limited uses)."""
    obj_def = OBJECT_CATALOG.get(object_id)
    if obj_def is None:
        return False
    player = state.players[player_id]
    objects = getattr(player, "objects", [])
    if object_id not in objects:
        return False
    if obj_def.uses is not None:
        return remove_object(state, player_id, object_id, to_discard=True)
    return True


def is_tale_of_yellow(object_id: str) -> bool:
    """Return True if object is a Yellow Tale."""
    return object_id in ("TALE_REPAIRER", "TALE_MASK", "TALE_DRAGON", "TALE_SIGN")


def attach_tale_to_chambers(state: GameState, player_id: PlayerId, tale_id: str) -> bool:
    """
    Attach a Yellow Tale to the Chambers Book.

    Effects:
    - Remove tale from inventory (not discarded)
    - Increment chambers_tales_attached
    - Apply vanish to the King for N turns
    """
    if state.chambers_book_holder != player_id:
        return False
    if not is_tale_of_yellow(tale_id):
        return False
    player = state.players[player_id]
    objects = getattr(player, "objects", [])
    if tale_id not in objects:
        return False
    objects.remove(tale_id)
    player.objects = objects
    state.chambers_tales_attached += 1
    state.king_vanished_turns = state.chambers_tales_attached
    return True

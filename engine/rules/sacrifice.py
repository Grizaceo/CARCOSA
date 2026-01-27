from __future__ import annotations

from engine.inventory import get_inventory_limits
from engine.objects import is_soulbound
from engine.state import PlayerState


def available_sacrifice_options(player: PlayerState) -> dict:
    obj_options = [obj for obj in player.objects if not is_soulbound(obj)]
    can_reduce_sanity = player.sanity_max is not None and player.sanity_max > -1
    _, current_slots = get_inventory_limits(player)
    can_reduce_object_slots = current_slots > 0
    return {
        "object_options": obj_options,
        "can_reduce_sanity": can_reduce_sanity,
        "can_reduce_object_slots": can_reduce_object_slots,
        "current_object_slots": current_slots,
    }

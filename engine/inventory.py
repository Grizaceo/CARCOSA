"""Inventory facade: keep public API while systems move to engine/systems."""
from engine.systems.inventory import (  # noqa: F401
    ROLE_INVENTORY_LIMITS,
    add_object,
    attach_tale_to_chambers,
    can_add_key,
    can_add_object,
    consume_object,
    get_inventory_limits,
    get_key_count,
    get_object_count,
    is_tale_of_yellow,
    remove_object,
)

__all__ = [
    "ROLE_INVENTORY_LIMITS",
    "get_inventory_limits",
    "get_object_count",
    "get_key_count",
    "can_add_object",
    "can_add_key",
    "add_object",
    "remove_object",
    "consume_object",
    "is_tale_of_yellow",
    "attach_tale_to_chambers",
]

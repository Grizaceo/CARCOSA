from __future__ import annotations

from importlib import import_module
from typing import Dict

__all__ = [
    "EVENT_HANDLERS",
    "get_event_handler",
    "register_event",
    "MONSTER_POST_SPAWN_HANDLERS",
    "MONSTER_REVEAL_HANDLERS",
    "MONSTER_SPAWN_HANDLERS",
    "apply_monster_post_spawn",
    "apply_monster_reveal",
    "register_monster_post_spawn",
    "register_monster_reveal",
    "register_monster_spawn",
    "try_monster_spawn",
    "OBJECT_USE_HANDLERS",
    "get_object_use_handler",
    "register_object_use",
    "OMEN_HANDLERS",
    "get_omen_handler",
    "register_omen",
    "SPECIAL_ROOM_HANDLERS",
    "get_special_room_handler",
    "register_special_room",
    "STATUS_END_OF_ROUND_HANDLERS",
    "apply_end_of_round_status_effects",
    "register_status_end_of_round",
]

_EXPORTS: Dict[str, str] = {
    "EVENT_HANDLERS": "engine.handlers.events",
    "get_event_handler": "engine.handlers.events",
    "register_event": "engine.handlers.events",
    "MONSTER_POST_SPAWN_HANDLERS": "engine.handlers.monsters",
    "MONSTER_REVEAL_HANDLERS": "engine.handlers.monsters",
    "MONSTER_SPAWN_HANDLERS": "engine.handlers.monsters",
    "apply_monster_post_spawn": "engine.handlers.monsters",
    "apply_monster_reveal": "engine.handlers.monsters",
    "register_monster_post_spawn": "engine.handlers.monsters",
    "register_monster_reveal": "engine.handlers.monsters",
    "register_monster_spawn": "engine.handlers.monsters",
    "try_monster_spawn": "engine.handlers.monsters",
    "OBJECT_USE_HANDLERS": "engine.handlers.objects",
    "get_object_use_handler": "engine.handlers.objects",
    "register_object_use": "engine.handlers.objects",
    "OMEN_HANDLERS": "engine.handlers.omens",
    "get_omen_handler": "engine.handlers.omens",
    "register_omen": "engine.handlers.omens",
    "SPECIAL_ROOM_HANDLERS": "engine.handlers.special_rooms",
    "get_special_room_handler": "engine.handlers.special_rooms",
    "register_special_room": "engine.handlers.special_rooms",
    "STATUS_END_OF_ROUND_HANDLERS": "engine.handlers.statuses",
    "apply_end_of_round_status_effects": "engine.handlers.statuses",
    "register_status_end_of_round": "engine.handlers.statuses",
}


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name)
    return getattr(module, name)


def __dir__():
    return sorted(set(__all__))

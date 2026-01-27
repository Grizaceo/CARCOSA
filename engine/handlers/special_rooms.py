from __future__ import annotations

from typing import Callable, Dict

SpecialRoomHandler = Callable[..., None]

# Registry for special room handlers (resolved by room_type)
SPECIAL_ROOM_HANDLERS: Dict[str, SpecialRoomHandler] = {}


def register_special_room(room_type: str) -> Callable[[SpecialRoomHandler], SpecialRoomHandler]:
    def decorator(fn: SpecialRoomHandler) -> SpecialRoomHandler:
        SPECIAL_ROOM_HANDLERS[room_type] = fn
        return fn

    return decorator


def get_special_room_handler(room_type: str) -> SpecialRoomHandler | None:
    return SPECIAL_ROOM_HANDLERS.get(room_type)

from __future__ import annotations

from typing import Callable, Dict, Optional

from engine.config import Config
from engine.rng import RNG
from engine.state import GameState
from engine.types import PlayerId

ObjectUseHandler = Callable[[GameState, PlayerId, Config, Optional[RNG]], None]

# Registry for object use handlers (resolved by object_id)
OBJECT_USE_HANDLERS: Dict[str, ObjectUseHandler] = {}


def register_object_use(object_id: str) -> Callable[[ObjectUseHandler], ObjectUseHandler]:
    def decorator(fn: ObjectUseHandler) -> ObjectUseHandler:
        OBJECT_USE_HANDLERS[object_id] = fn
        return fn

    return decorator


def get_object_use_handler(object_id: str) -> ObjectUseHandler | None:
    return OBJECT_USE_HANDLERS.get(object_id)


__all__ = [
    "OBJECT_USE_HANDLERS",
    "register_object_use",
    "get_object_use_handler",
]

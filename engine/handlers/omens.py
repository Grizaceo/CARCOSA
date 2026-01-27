from __future__ import annotations

from typing import Callable, Dict

OmenHandler = Callable[..., None]

# Registry for omen handlers (resolved by omen_id)
OMEN_HANDLERS: Dict[str, OmenHandler] = {}


def register_omen(omen_id: str) -> Callable[[OmenHandler], OmenHandler]:
    def decorator(fn: OmenHandler) -> OmenHandler:
        OMEN_HANDLERS[omen_id] = fn
        return fn

    return decorator


def get_omen_handler(omen_id: str) -> OmenHandler | None:
    return OMEN_HANDLERS.get(omen_id)

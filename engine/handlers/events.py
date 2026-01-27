from __future__ import annotations

from typing import Callable, Dict

EventHandler = Callable[..., None]

# Registry for event card handlers (resolved by event_id)
EVENT_HANDLERS: Dict[str, EventHandler] = {}


def register_event(event_id: str) -> Callable[[EventHandler], EventHandler]:
    def decorator(fn: EventHandler) -> EventHandler:
        EVENT_HANDLERS[event_id] = fn
        return fn

    return decorator


def get_event_handler(event_id: str) -> EventHandler | None:
    return EVENT_HANDLERS.get(event_id)

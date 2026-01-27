from .events import EVENT_HANDLERS, get_event_handler, register_event
from .omens import OMEN_HANDLERS, get_omen_handler, register_omen
from .special_rooms import SPECIAL_ROOM_HANDLERS, get_special_room_handler, register_special_room

__all__ = [
    "EVENT_HANDLERS",
    "get_event_handler",
    "register_event",
    "OMEN_HANDLERS",
    "get_omen_handler",
    "register_omen",
    "SPECIAL_ROOM_HANDLERS",
    "get_special_room_handler",
    "register_special_room",
]

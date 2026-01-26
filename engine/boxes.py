from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from engine.board import is_corridor

if TYPE_CHECKING:
    from engine.state import DeckState, GameState
    from engine.types import RoomId


def active_box_id_for_room(state: "GameState", room_id: "RoomId") -> Optional[str]:
    if is_corridor(room_id):
        return None
    return state.box_at_room.get(room_id)


def active_deck_for_room(state: "GameState", room_id: "RoomId") -> Optional["DeckState"]:
    if is_corridor(room_id):
        return None
    box_id = state.box_at_room.get(room_id)
    if box_id and box_id in state.boxes:
        return state.boxes[box_id].deck
    room = state.rooms.get(room_id)
    return room.deck if room else None


def sync_room_decks_from_boxes(state: "GameState") -> None:
    for rid, room in state.rooms.items():
        if is_corridor(rid):
            continue
        box_id = state.box_at_room.get(rid)
        if not box_id:
            continue
        box = state.boxes.get(box_id)
        if box is None:
            continue
        room.deck = box.deck


def sync_boxes_from_rooms(state: "GameState") -> None:
    """
    Ensure box decks reference the same DeckState instances as rooms.
    This keeps active_deck_for_room consistent after room decks are rebuilt.
    """
    from engine.state import BoxState

    for rid, room in state.rooms.items():
        if is_corridor(rid):
            continue
        box_id = state.box_at_room.get(rid)
        if not box_id:
            box_id = str(rid)
            state.box_at_room[rid] = box_id
        box = state.boxes.get(box_id)
        if box is None:
            state.boxes[box_id] = BoxState(box_id=box_id, deck=room.deck)
        else:
            box.deck = room.deck

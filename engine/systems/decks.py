from __future__ import annotations

from engine.boxes import active_deck_for_room
from engine.state import GameState
from engine.types import RoomId


def reveal_one(state: GameState, room_id: RoomId):
    room = state.rooms.get(room_id)
    if room is None:
        return None
    deck = active_deck_for_room(state, room_id)
    if deck is None or deck.remaining() <= 0:
        return None
    card = deck.cards[deck.top]
    deck.top += 1
    room.revealed += 1
    return card

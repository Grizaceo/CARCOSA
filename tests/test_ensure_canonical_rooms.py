from engine.actions import Action, ActionType
from engine.board import canonical_room_ids, corridor_id, room_id
from engine.rng import RNG
from engine.state_factory import make_game_state
from engine.transition import step
from engine.types import CardId, PlayerId


def test_game_state_initializes_canonical_rooms():
    players = {"P1": {"room": str(corridor_id(1)), "sanity": 3}}
    s = make_game_state(round=1, players=players, rooms={})

    for rid in canonical_room_ids():
        assert rid in s.rooms
    for floor in (1, 2, 3):
        assert corridor_id(floor) in s.rooms

    target = room_id(1, 1)
    box_id = s.box_at_room[target]
    s.boxes[box_id].deck.cards = [CardId("KEY")]

    s2 = step(s, Action(actor="P1", type=ActionType.MOVE, data={"to": str(target)}), RNG(1))
    assert s2.players[PlayerId("P1")].keys == 1

from engine.actions import Action, ActionType
from engine.board import canonical_room_ids, corridor_id, room_id, rotate_boxes
from engine.boxes import active_deck_for_room, sync_room_decks_from_boxes
from engine.state import BoxState, DeckState
from engine.state_factory import make_game_state
from engine.types import CardId, PlayerId
from engine.rng import RNG
from engine.transition import step


def _make_empty_rooms():
    return {}


def test_rotation_changes_revealed_card():
    boxes = {}
    box_at_room = {}

    for rid in canonical_room_ids():
        box_id = f"box_{rid}"
        box_at_room[rid] = box_id
        boxes[box_id] = BoxState(box_id=box_id, deck=DeckState(cards=[]))

    boxes[box_at_room[room_id(1, 1)]].deck.cards = [CardId("EVENT:X")]
    boxes[box_at_room[room_id(2, 4)]].deck.cards = [CardId("KEY")]

    s = make_game_state(
        round=1,
        players={"P1": {"room": str(corridor_id(1)), "sanity": 3}},
        rooms=_make_empty_rooms(),
        phase="PLAYER",
    )
    s.boxes = boxes
    s.box_at_room = box_at_room

    s.box_at_room = rotate_boxes(s.box_at_room)
    sync_room_decks_from_boxes(s)

    action = Action(actor="P1", type=ActionType.MOVE, data={"to": str(room_id(1, 1))})
    s2 = step(s, action, RNG(1))

    assert s2.players[PlayerId("P1")].keys == 1
    assert s2.rooms[room_id(1, 1)].deck is s2.boxes[s2.box_at_room[room_id(1, 1)]].deck


def test_search_uses_active_deck():
    boxes = {}
    box_at_room = {}

    for rid in canonical_room_ids():
        box_id = f"box_{rid}"
        box_at_room[rid] = box_id
        boxes[box_id] = BoxState(box_id=box_id, deck=DeckState(cards=[]))

    target = room_id(1, 1)
    boxes[box_at_room[target]].deck.cards = [CardId("KEY")]

    s = make_game_state(
        round=1,
        players={"P1": {"room": str(target), "sanity": 3}},
        rooms=_make_empty_rooms(),
        phase="PLAYER",
    )
    s.boxes = boxes
    s.box_at_room = box_at_room

    s.rooms[target].deck = DeckState(cards=[])
    deck = active_deck_for_room(s, target)
    assert deck is not None and deck.remaining() > 0

    from engine.legality import get_legal_actions
    acts = get_legal_actions(s, "P1")
    assert any(a.type == ActionType.SEARCH for a in acts)

    boxes[box_at_room[target]].deck.cards = []
    s.rooms[target].deck = DeckState(cards=[CardId("KEY")])
    deck = active_deck_for_room(s, target)
    assert deck is not None and deck.remaining() == 0

    acts = get_legal_actions(s, "P1")
    assert all(a.type != ActionType.SEARCH for a in acts)

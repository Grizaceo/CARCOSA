from engine.actions import Action, ActionType
from engine.board import corridor_id, room_id
from engine.config import Config
from engine.rng import RNG
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.transition import _resolve_card_minimal, step
from engine.types import CardId, PlayerId


class FixedRNG:
    def __init__(self, values):
        self.values = list(values)
        self.last_king_d4 = None
        self.last_king_d6 = None

    def randint(self, a, b):
        value = self.values.pop(0)
        if a == 1 and b == 4:
            self.last_king_d4 = value
        if a == 1 and b == 6:
            self.last_king_d6 = value
        return value

    def shuffle(self, seq):
        return None


def _make_rooms():
    return {
        corridor_id(1): RoomState(room_id=corridor_id(1), deck=DeckState(cards=[])),
        corridor_id(2): RoomState(room_id=corridor_id(2), deck=DeckState(cards=[])),
        corridor_id(3): RoomState(room_id=corridor_id(3), deck=DeckState(cards=[])),
        room_id(1, 1): RoomState(room_id=room_id(1, 1), deck=DeckState(cards=[CardId("EVENT:X")])),
    }


def test_crown_is_soulbound_not_object():
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=3, room=room_id(1, 1))
    s = GameState(round=1, players={PlayerId("P1"): p1})

    _resolve_card_minimal(s, PlayerId("P1"), CardId("CROWN"), Config())

    assert "CROWN" in s.players[PlayerId("P1")].soulbound_items
    assert "CROWN" not in s.players[PlayerId("P1")].objects
    assert s.flags.get("CROWN_HOLDER") == "P1"


def test_d6_discard_ignores_soulbound():
    cfg = Config()
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=3, room=corridor_id(1))
    p1.soulbound_items.append("CROWN")
    p1.objects = []
    rooms = _make_rooms()
    s = GameState(round=1, players={PlayerId("P1"): p1}, rooms=rooms, phase="KING", king_floor=1)

    rng = FixedRNG([1, 6, 1, 1, 1, 1])
    s2 = step(s, Action(actor="KING", type=ActionType.KING_ENDROUND, data={}), rng, cfg)

    assert "CROWN" in s2.players[PlayerId("P1")].soulbound_items

    p1 = PlayerState(player_id=PlayerId("P1"), sanity=3, room=corridor_id(1))
    p1.soulbound_items.append("CROWN")
    p1.objects = ["OBJ"]
    s = GameState(round=1, players={PlayerId("P1"): p1}, rooms=rooms, phase="KING", king_floor=1)

    rng = FixedRNG([1, 6, 1, 1, 1, 1])
    s2 = step(s, Action(actor="KING", type=ActionType.KING_ENDROUND, data={}), rng, cfg)

    assert s2.players[PlayerId("P1")].objects == []
    assert "CROWN" in s2.players[PlayerId("P1")].soulbound_items

from engine.actions import Action, ActionType
from engine.board import corridor_id, room_id
from engine.config import Config
from engine.rng import RNG
from engine.state_factory import make_game_state
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
        str(corridor_id(1)): {},
        str(corridor_id(2)): {},
        str(corridor_id(3)): {},
        str(room_id(1, 1)): {"cards": ["EVENT:X"]},
    }


def test_crown_is_soulbound_not_object():
    s = make_game_state(
        round=1,
        players={"P1": {"room": str(room_id(1, 1)), "sanity": 3}},
        rooms=[str(room_id(1, 1))],
    )

    _resolve_card_minimal(s, PlayerId("P1"), CardId("CROWN"), Config())

    assert "CROWN" in s.players[PlayerId("P1")].soulbound_items
    assert "CROWN" not in s.players[PlayerId("P1")].objects
    assert s.flags.get("CROWN_HOLDER") == "P1"


def test_d6_discard_ignores_soulbound():
    """d6=6 descarta objetos pero NO soulbound items."""
    cfg = Config()
    # Jugador en piso 2 para evitar inmunidad FK (king_floor=1, false_king_floor distinto)
    rooms = _make_rooms()
    s = make_game_state(
        round=1,
        players={"P1": {"room": str(corridor_id(2)), "sanity": 3}},
        rooms=rooms,
        phase="KING",
        king_floor=1,
    )
    s.players[PlayerId("P1")].soulbound_items.append("CROWN")
    s.players[PlayerId("P1")].objects = []
    s.false_king_floor = 3  # FK en piso diferente para evitar inmunidad

    rng = FixedRNG([1, 6, 1, 1, 1, 1, 1, 1, 1, 1])
    s2 = step(s, Action(actor="KING", type=ActionType.KING_ENDROUND, data={}), rng, cfg)

    assert "CROWN" in s2.players[PlayerId("P1")].soulbound_items

    # Segunda parte: con objeto normal
    s = make_game_state(
        round=1,
        players={"P1": {"room": str(corridor_id(2)), "sanity": 3, "objects": ["OBJ"]}},
        rooms=rooms,
        phase="KING",
        king_floor=1,
    )
    s.players[PlayerId("P1")].soulbound_items.append("GENERIC_SOULBOUND")
    s.false_king_floor = 3  # FK en piso diferente

    rng = FixedRNG([1, 6, 1, 1, 1, 1, 1, 1, 1, 1])
    s2 = step(s, Action(actor="KING", type=ActionType.KING_ENDROUND, data={}), rng, cfg)

    assert s2.players[PlayerId("P1")].objects == []
    assert "GENERIC_SOULBOUND" in s2.players[PlayerId("P1")].soulbound_items

from engine.actions import Action, ActionType
from engine.config import Config
from engine.rng import RNG
from engine.state_factory import make_game_state
from engine.board import corridor_id
from engine.types import PlayerId
from engine.transition import step


def _state(round_n: int, king_floor: int, p_floor: int):
    players = {
        "P1": {"room": str(corridor_id(p_floor)), "sanity": 3},
        "P2": {"room": str(corridor_id(p_floor)), "sanity": 3},
    }
    rooms = [
        str(corridor_id(1)),
        str(corridor_id(2)),
        str(corridor_id(3)),
    ]
    return make_game_state(round=round_n, players=players, rooms=rooms, king_floor=king_floor, phase="KING")


def test_king_no_damage_on_departure_only_arrival():
    rng = RNG(2)  # Seed 2 generates d6=1 first, no additional sanity loss beyond house loss
    cfg = Config(KING_PRESENCE_START_ROUND=1)  # presencia habilitada desde ronda 1 para el test

    s = _state(round_n=2, king_floor=1, p_floor=1)  # jugadores en piso 1
    # Rey se va a piso 2; si pegara al salir, dañaría a jugadores en piso 1 (NO debe ocurrir)
    a = Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 2})
    s2 = step(s, a, rng, cfg)

    # Solo -1 global (casa). Sin presencia porque llegó a piso 2 y jugadores están en piso 1.
    assert s2.players[PlayerId("P1")].sanity == 2
    assert s2.players[PlayerId("P2")].sanity == 2


def test_toggle_skip_presence_round1():
    rng = RNG(2)
    cfg = Config(KING_PRESENCE_START_ROUND=2)

    s = _state(round_n=1, king_floor=1, p_floor=1)
    a = Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 1})
    s2 = step(s, a, rng, cfg)

    # En ronda 1: solo -1 global; presencia se omite por toggle.
    assert s2.players[PlayerId("P1")].sanity == 2
    assert s2.players[PlayerId("P2")].sanity == 2

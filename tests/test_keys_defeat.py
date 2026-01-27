from engine.config import Config
from engine.state_factory import make_game_state
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step


def test_lose_when_keys_in_game_leq_threshold():
    cfg = Config(KEYS_TOTAL=6, KEYS_LOSE_THRESHOLD=3)
    rooms = [
        str(corridor_id(1)),
        str(corridor_id(2)),
        str(corridor_id(3)),
    ]
    players = {
        "P1": {"room": str(corridor_id(1)), "sanity": 3},
        "P2": {"room": str(corridor_id(2)), "sanity": 3},
    }

    # 6 total, 3 destruidas -> quedan 3 en juego => derrota al final de ronda
    s = make_game_state(players=players, rooms=rooms, round=5, phase="KING", king_floor=1)
    s.keys_destroyed = 3
    rng = RNG(1)

    a = Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 1})
    s2 = step(s, a, rng, cfg)

    assert s2.game_over is True
    assert s2.outcome == "LOSE_KEYS_DESTROYED"

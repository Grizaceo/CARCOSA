from engine.config import Config
from engine.state_factory import make_game_state
from engine.types import PlayerId
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step

def test_win_triggers_on_endround_when_conditions_met():
    cfg = Config(
        UMBRAL_NODE="F1_P",
        KEYS_TO_WIN=4,
        HOUSE_LOSS_PER_ROUND=0,          # aislar test
        KING_PRESENCE_START_ROUND=999,   # aislar test
    )

    rooms = [
        str(corridor_id(1)),
        str(corridor_id(2)),
        str(corridor_id(3)),
    ]

    players = {
        "P1": {"room": str(corridor_id(1)), "sanity": 3, "keys": 2},
        "P2": {"room": str(corridor_id(1)), "sanity": 3, "keys": 2},
    }

    s = make_game_state(players=players, rooms=rooms, round=5, phase="KING", king_floor=2)
    s.players[PlayerId("P1")].at_umbral = True
    s.players[PlayerId("P2")].at_umbral = True
    rng = RNG(1)

    a = Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 2})
    s2 = step(s, a, rng, cfg)

    assert s2.game_over is True
    assert s2.outcome == "WIN"

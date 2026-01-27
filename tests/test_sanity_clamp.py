from engine.config import Config
from engine.state_factory import make_game_state
from engine.types import PlayerId
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step

def test_sanity_never_goes_below_minus5():
    cfg = Config(HOUSE_LOSS_PER_ROUND=10, KING_PRESENCE_START_ROUND=999)
    rooms = [
        str(corridor_id(1)),
        str(corridor_id(2)),
        str(corridor_id(3)),
    ]
    players = {
        "P1": {"room": str(corridor_id(1)), "sanity": 0},
        "P2": {"room": str(corridor_id(2)), "sanity": 0},
    }
    s = make_game_state(round=1, players=players, rooms=rooms, phase="KING", king_floor=1)
    rng = RNG(1)

    s2 = step(s, Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 1}), rng, cfg)

    assert s2.players[PlayerId("P1")].sanity >= cfg.S_LOSS
    assert s2.players[PlayerId("P2")].sanity >= cfg.S_LOSS

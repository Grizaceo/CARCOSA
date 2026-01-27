from engine.config import Config
from engine.state_factory import make_game_state
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step

def test_timeout_triggers_when_round_exceeds_max_rounds():
    cfg = Config(MAX_ROUNDS=2, TIMEOUT_OUTCOME="TIMEOUT", KING_PRESENCE_START_ROUND=999)
    rooms = [
        str(corridor_id(1)),
        str(corridor_id(2)),
        str(corridor_id(3)),
    ]
    players = {"P1": {"room": str(corridor_id(1)), "sanity": 3}}
    # round=3 excede MAX_ROUNDS=2 => debe terminar en TIMEOUT al salir de step()
    s = make_game_state(players=players, rooms=rooms, round=3, phase="PLAYER", king_floor=1)
    rng = RNG(1)

    s2 = step(s, Action(actor="P1", type=ActionType.END_TURN, data={}), rng, cfg)
    assert s2.game_over is True
    assert s2.outcome == "TIMEOUT"

from engine.config import Config
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step

def test_timeout_triggers_when_round_exceeds_max_rounds():
    cfg = Config(MAX_ROUNDS=2, TIMEOUT_OUTCOME="TIMEOUT", KING_PRESENCE_START_ROUND=999)
    rooms = {
        corridor_id(1): RoomState(room_id=corridor_id(1), deck=DeckState(cards=[])),
        corridor_id(2): RoomState(room_id=corridor_id(2), deck=DeckState(cards=[])),
        corridor_id(3): RoomState(room_id=corridor_id(3), deck=DeckState(cards=[])),
    }
    players = {PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=corridor_id(1))}
    # round=3 excede MAX_ROUNDS=2 => debe terminar en TIMEOUT al salir de step()
    s = GameState(round=3, players=players, rooms=rooms, phase="PLAYER", king_floor=1)
    rng = RNG(1)

    s2 = step(s, Action(actor="P1", type=ActionType.END_TURN, data={}), rng, cfg)
    assert s2.game_over is True
    assert s2.outcome == "TIMEOUT"

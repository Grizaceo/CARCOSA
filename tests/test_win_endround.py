from engine.config import Config
from engine.state import GameState, PlayerState, RoomState, DeckState
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

    rooms = {
        corridor_id(1): RoomState(room_id=corridor_id(1), deck=DeckState(cards=[])),
        corridor_id(2): RoomState(room_id=corridor_id(2), deck=DeckState(cards=[])),
        corridor_id(3): RoomState(room_id=corridor_id(3), deck=DeckState(cards=[])),
    }

    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=corridor_id(1), keys=2, at_umbral=True),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=3, room=corridor_id(1), keys=2, at_umbral=True),
    }

    s = GameState(round=5, players=players, rooms=rooms, phase="KING", king_floor=2)
    rng = RNG(1)

    a = Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 2})
    s2 = step(s, a, rng, cfg)

    assert s2.game_over is True
    assert s2.outcome == "WIN"

from engine.config import Config
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step

def test_sanity_never_goes_below_minus5():
    cfg = Config(HOUSE_LOSS_PER_ROUND=10, KING_PRESENCE_START_ROUND=999)
    rooms = {
        corridor_id(1): RoomState(room_id=corridor_id(1), deck=DeckState(cards=[])),
        corridor_id(2): RoomState(room_id=corridor_id(2), deck=DeckState(cards=[])),
        corridor_id(3): RoomState(room_id=corridor_id(3), deck=DeckState(cards=[])),
    }
    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=0, room=corridor_id(1)),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=0, room=corridor_id(2)),
    }
    s = GameState(round=1, players=players, rooms=rooms, phase="KING", king_floor=1)
    rng = RNG(1)

    s2 = step(s, Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 1}), rng, cfg)

    assert s2.players[PlayerId("P1")].sanity >= cfg.S_LOSS
    assert s2.players[PlayerId("P2")].sanity >= cfg.S_LOSS

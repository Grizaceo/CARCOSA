from engine.config import Config
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step


def test_lose_when_keys_in_game_leq_threshold():
    cfg = Config(KEYS_TOTAL=6, KEYS_LOSE_THRESHOLD=3)
    rooms = {
        corridor_id(1): RoomState(room_id=corridor_id(1), deck=DeckState(cards=[])),
        corridor_id(2): RoomState(room_id=corridor_id(2), deck=DeckState(cards=[])),
        corridor_id(3): RoomState(room_id=corridor_id(3), deck=DeckState(cards=[])),
    }
    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=corridor_id(1)),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=3, room=corridor_id(2)),
    }

    # 6 total, 3 destruidas -> quedan 3 en juego => derrota al final de ronda
    s = GameState(round=5, players=players, rooms=rooms, phase="KING", keys_destroyed=3, king_floor=1)
    rng = RNG(1)

    a = Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 1})
    s2 = step(s, a, rng, cfg)

    assert s2.game_over is True
    assert s2.outcome == "LOSE_KEYS_DESTROYED"

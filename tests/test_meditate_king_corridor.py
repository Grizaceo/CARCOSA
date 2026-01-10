from engine.config import Config
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId
from engine.board import corridor_id
from engine.legality import get_legal_actions
from engine.actions import ActionType

def test_cannot_meditate_in_king_floor_corridor():
    cfg = Config(KING_PRESENCE_START_ROUND=999)
    rooms = {
        corridor_id(1): RoomState(room_id=corridor_id(1), deck=DeckState(cards=[])),
        corridor_id(2): RoomState(room_id=corridor_id(2), deck=DeckState(cards=[])),
        corridor_id(3): RoomState(room_id=corridor_id(3), deck=DeckState(cards=[])),
    }
    players = {PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=0, room=corridor_id(1))}
    s = GameState(round=1, players=players, rooms=rooms, phase="PLAYER", king_floor=1)

    acts = get_legal_actions(s, "P1")
    assert all(a.type != ActionType.MEDITATE for a in acts)

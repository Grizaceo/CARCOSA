from engine.config import Config
from engine.state_factory import make_game_state
from engine.board import corridor_id
from engine.legality import get_legal_actions
from engine.actions import ActionType

def test_cannot_meditate_in_king_floor_corridor():
    cfg = Config(KING_PRESENCE_START_ROUND=999)
    rooms = [
        str(corridor_id(1)),
        str(corridor_id(2)),
        str(corridor_id(3)),
    ]
    players = {"P1": {"room": str(corridor_id(1)), "sanity": 0}}
    s = make_game_state(round=1, players=players, rooms=rooms, phase="PLAYER", king_floor=1)

    acts = get_legal_actions(s, "P1")
    assert all(a.type != ActionType.MEDITATE for a in acts)

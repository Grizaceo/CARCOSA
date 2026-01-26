
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId
from engine.actions import Action, ActionType
from engine.transition import step
from engine.rng import RNG

def create_base_state():
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=5, room=RoomId("F1_R1"), role_id="SCOUT")
    rooms = {
        RoomId("F1_R1"): RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=["ITEM"]*10)),
    }
    s = GameState(
        round=1,
        players={PlayerId("P1"): p1},
        rooms=rooms,
        turn_order=[PlayerId("P1")],
        remaining_actions={PlayerId("P1"): 2},  # Base 2
        phase="PLAYER"
    )
    return s

try:
    s = create_base_state()
    print(f"Initial Actions: {s.remaining_actions}")
    
    s = step(s, Action(actor="P1", type=ActionType.SEARCH, data={}), RNG(0))
    print(f"After Search 1: {s.remaining_actions}")
    
    if s.remaining_actions[PlayerId("P1")] != 1:
        print("FAILURE: Actions != 1")
    else:
        print("SUCCESS: Search 1 cost 1 action")
        
except Exception as e:
    print(f"EXCEPTION: {e}")

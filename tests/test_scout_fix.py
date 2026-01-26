import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState, BoxState
from engine.types import PlayerId, RoomId
from engine.actions import Action, ActionType
from engine.transition import step, _start_new_round
from engine.rng import RNG

def create_base_state():
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=5, room=RoomId("F1_R1"), role_id="SCOUT")
    rooms = {
        RoomId("F1_R1"): RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=[])),
        RoomId("F1_P"): RoomState(room_id=RoomId("F1_P"), deck=DeckState(cards=[])),
        RoomId("F1_R2"): RoomState(room_id=RoomId("F1_R2"), deck=DeckState(cards=[])),
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

def test_scout_actions_limit_non_move():
    """Verify separate limit: 2 searches allowed, but free move logic doesn't add generic action."""
    s = create_base_state()
    # Mock deck to allow search
    s.rooms[RoomId("F1_R1")].deck.cards = ["ITEM"] * 10 
    
    with open("scout_debug.log", "w") as f:
        f.write(f"Initial Actions: {s.remaining_actions}\n")

        # 1. Search (Cost 1)
        s = step(s, Action(actor="P1", type=ActionType.SEARCH, data={}), RNG(0))
        f.write(f"After Search 1: Actions={s.remaining_actions[PlayerId('P1')]}\n")
        assert s.remaining_actions[PlayerId("P1")] == 1

        # 2. Search (Cost 1) -> Total 2 paid
        s = step(s, Action(actor="P1", type=ActionType.SEARCH, data={}), RNG(0))
        f.write(f"After Search 2: Actions={s.remaining_actions[PlayerId('P1')]}\n")
        assert s.remaining_actions[PlayerId("P1")] == 0

    # 3. Try 3rd Search -> Should be illegal or cost fail (actions 0)
    # The legality checker checks remaining_actions > 0.
    from engine.legality import get_legal_actions
    legal = get_legal_actions(s, "P1")
    search_legal = any(a.type == ActionType.SEARCH for a in legal)
    assert not search_legal
    # Only END_TURN should be available
    assert len(legal) == 1 and legal[0].type == ActionType.END_TURN

def test_scout_free_move():
    """Verify MOVE is free first time."""
    s = create_base_state()
    # Mock neighbors
    s.rooms[RoomId("F1_R2")].deck.cards = ["ITEM"]*5
    
    ps = s.players[PlayerId("P1")]
    assert not ps.free_move_used_this_turn
    assert s.remaining_actions[PlayerId("P1")] == 2

    # 1. Move (Should be free)
    s = step(s, Action(actor="P1", type=ActionType.MOVE, data={"to": "F1_R2"}), RNG(0))
    
    p = s.players[PlayerId("P1")]
    assert p.free_move_used_this_turn
    assert s.remaining_actions[PlayerId("P1")] == 2  # No consumió acción

    # 2. Search (Cost 1)
    s = step(s, Action(actor="P1", type=ActionType.SEARCH, data={}), RNG(0))
    assert s.remaining_actions[PlayerId("P1")] == 1

    # 3. Move again (Cost 1)
    s = step(s, Action(actor="P1", type=ActionType.MOVE, data={"to": "F1_R1"}), RNG(0))
    assert s.remaining_actions[PlayerId("P1")] == 0

def test_scout_start_round_reset():
    """Verify base actions are 2 at start of round."""
    s = create_base_state()
    _start_new_round(s, None)
    
    assert s.remaining_actions[PlayerId("P1")] == 2 # Base 2, not 3.
    # The +1 is applied dynamically as a discount.

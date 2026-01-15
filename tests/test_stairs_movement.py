from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId
from engine.legality import get_legal_actions
from engine.actions import ActionType
from engine.board import room_id

def test_stairs_move_up_valid():
    """Test valid movement up the stairs (F1 -> F2)."""
    # Setup: Player at F1_R1, Stairs at F1_R1 and F2_R1
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=10, room=room_id(1, 1))
    stairs = {1: room_id(1, 1), 2: room_id(2, 1), 3: room_id(3, 1)}
    
    # Minimal rooms state
    rooms = {
        room_id(1, 1): RoomState(room_id=room_id(1, 1), deck=DeckState([])),
        room_id(2, 1): RoomState(room_id=room_id(2, 1), deck=DeckState([])),
    }
    
    s = GameState(
        round=1,
        players={PlayerId("P1"): p1},
        rooms=rooms,
        stairs=stairs,
        phase="PLAYER",
        turn_order=[PlayerId("P1")],
        remaining_actions={PlayerId("P1"): 2}
    )
    
    actions = get_legal_actions(s, "P1")
    move_moves = [a for a in actions if a.type == ActionType.MOVE]
    destinations = [a.data["to"] for a in move_moves]
    
    # Should be able to move to neighbors AND F2_R1 (stairs up)
    assert str(room_id(2, 1)) in destinations

def test_stairs_move_down_valid():
    """Test valid movement down the stairs (F2 -> F1)."""
    # Setup: Player at F2_R1
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=10, room=room_id(2, 1))
    stairs = {1: room_id(1, 1), 2: room_id(2, 1), 3: room_id(3, 1)}
    
    rooms = {
        room_id(1, 1): RoomState(room_id=room_id(1, 1), deck=DeckState([])),
        room_id(2, 1): RoomState(room_id=room_id(2, 1), deck=DeckState([])),
    }
    
    s = GameState(
        round=1,
        players={PlayerId("P1"): p1},
        rooms=rooms,
        stairs=stairs,
        phase="PLAYER",
        turn_order=[PlayerId("P1")],
        remaining_actions={PlayerId("P1"): 2}
    )
    
    actions = get_legal_actions(s, "P1")
    move_moves = [a for a in actions if a.type == ActionType.MOVE]
    destinations = [a.data["to"] for a in move_moves]
    
    # Should be able to move to neighbors AND F1_R1 (stairs down)
    assert str(room_id(1, 1)) in destinations

def test_stairs_move_invalid_not_at_stairs():
    """Test cannot move floors if not at stairs room."""
    # Setup: Player at F1_R2 (stairs are at F1_R1)
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=10, room=room_id(1, 2))
    stairs = {1: room_id(1, 1), 2: room_id(2, 1), 3: room_id(3, 1)}
    
    rooms = {
        room_id(1, 2): RoomState(room_id=room_id(1, 2), deck=DeckState([])),
        room_id(2, 1): RoomState(room_id=room_id(2, 1), deck=DeckState([])),
    }
    
    s = GameState(
        round=1,
        players={PlayerId("P1"): p1},
        rooms=rooms,
        stairs=stairs,
        phase="PLAYER",
        turn_order=[PlayerId("P1")],
        remaining_actions={PlayerId("P1"): 2}
    )
    
    actions = get_legal_actions(s, "P1")
    move_moves = [a for a in actions if a.type == ActionType.MOVE]
    destinations = [a.data["to"] for a in move_moves]
    
    # Should NOT be able to move to F2_R1
    assert str(room_id(2, 1)) not in destinations

def test_stairs_destination_is_stairs_room():
    """Test that taking stairs lands you exactly on the stairs room of the other floor."""
    # This is implicitly tested by get_legal_actions proposing the specific room,
    # but we can verify the logic ensures the destination is the stairs key.
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=10, room=room_id(1, 1))
    stairs = {1: room_id(1, 1), 2: room_id(2, 4), 3: room_id(3, 1)} # Stairs F2 at R4
    
    rooms = {
        room_id(1, 1): RoomState(room_id=room_id(1, 1), deck=DeckState([])),
        room_id(2, 4): RoomState(room_id=room_id(2, 4), deck=DeckState([])),
    }
    
    s = GameState(
        round=1,
        players={PlayerId("P1"): p1},
        rooms=rooms,
        stairs=stairs,
        phase="PLAYER",
        turn_order=[PlayerId("P1")],
        remaining_actions={PlayerId("P1"): 2}
    )
    
    actions = get_legal_actions(s, "P1")
    move_moves = [a for a in actions if a.type == ActionType.MOVE]
    destinations = [a.data["to"] for a in move_moves]
    
    # Destination in F2 should be F2_R4 (stairs), not generic default
    assert str(room_id(2, 4)) in destinations

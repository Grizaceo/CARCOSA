from engine.state import GameState, PlayerState, RoomState, DeckState, BoxState
from engine.types import PlayerId, RoomId
from engine.transition import step
from engine.actions import Action, ActionType
from engine.board import canonical_room_ids, room_id, rotate_boxes_intra_floor, rotate_boxes
from engine.rng import RNG

def test_king_d6_1_activates_intra_floor_rotation():
    """Test that d6=1 causes intra-floor rotation instead of sushi global."""
    # Setup state in KING phase
    rooms = {}
    boxes = {}
    box_at_room = {}
    
    # Init simple mapping: Box_R<id> at Room <id>
    for rid in canonical_room_ids():
        rooms[rid] = RoomState(room_id=rid, deck=DeckState([]))
        bid = str(rid)
        boxes[bid] = BoxState(box_id=bid, deck=DeckState([]))
        box_at_room[rid] = bid
        
    s = GameState(
        round=1,
        players={},
        rooms=rooms,
        boxes=boxes,
        box_at_room=box_at_room,
        phase="KING",
        king_floor=1
    )
    
    # Mock RNG to force d6=1
    # We need to know how many RNG calls happen before d6 logic.
    # In 'step' -> KING_ENDROUND:
    #   1. d4 for new floor (ruleta)
    #   2. maybe loop if falls on false king (none here)
    #   3. d6 for effect
    
    # Let's use a seeded RNG that we know produces d6=1 at the right time?
    # Or cleaner: Monkey patch RNG or just rely on a known seed.
    # But wait, transition.py uses `rng.randint(1, 6)`.
    
    # We can use a deterministic seed and "search" for one that gives d6=1.
    # Or we can just spy on the result?
    # Logic in transition.py:
    # d4 = rng.randint(1, 4)
    # ...
    # d6 = rng.randint(1, 6)
    
    # We'll try a few seeds until we hit d6=1.
    target_d6 = 1
    found_seed = None
    
    for seed in range(1000):
        rng = RNG(seed)
        _ = rng.randint(1, 4) # d4 for floor
        val = rng.randint(1, 6) # d6
        if val == target_d6:
            found_seed = seed
            break
            
    assert found_seed is not None, "Could not find seed for d6=1"
    
    # Now run with that seed
    rng = RNG(found_seed)
    
    # Action
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    
    next_s = step(s, action, rng)
    
    # Verify d6 was indeed 1
    assert rng.last_king_d6 == 1
    
    # Check if rotation was intra-floor
    # Expected: 
    # F1_R1 -> F1_R4 (box from R1 moves to R4)
    # If it was sushi global:
    # F1_R1 -> F1_R4 (Wait, sushi global map: R1->R4, R4->R3, R3->R2, R2->F2_R3 etc?)
    # Let's verify a difference.
    
    # SUSHI_CYCLE global:
    # F1_R1 -> F1_R4
    # F1_R4 -> F1_R3
    # ...
    # F2_R4 -> F1_R1
    
    # INTRA_FLOOR:
    # F1_R1 -> F1_R4
    # F1_R2 -> F1_R1
    # ...
    # F2_R1 -> F2_R4
    
    # Let's check F2_R1 behavior which differs.
    # Intra: F2_R1 moves to F2_R4.
    # Sushi: F2_R1 moves to F2_R4. Wait.
    
    # Let's check SUSHI_CYCLE in board.py:
    # room_id(2, 1): room_id(2, 4),
    # Intra cycle: 
    # room_id(2, 1) -> room_id(2, 4)
    
    # Wait, check F2_R4.
    # Sushi: room_id(2, 4): room_id(1, 1) CROSSES FLOORS
    # Intra: room_id(2, 4): room_id(2, 3) STAYS ON FLOOR
    
    # So we check F2_R4.
    r2_4 = room_id(2, 4)
    box_at_r2_4_initial = box_at_room[r2_4] # "F2_R4"
    
    # In next_s, who has "F2_R4" box?
    # rotated[dst] = box[src]
    # So box at src moves to dst.
    
    # Intra: src=F2_R4 -> dst=F2_R3. So F2_R3 should have box "F2_R4".
    # Sushi: src=F2_R4 -> dst=F1_R1. So F1_R1 should have box "F2_R4".
    
    box_expected_intra_dst = room_id(2, 3)
    box_expected_sushi_dst = room_id(1, 1)
    
    # Which room has the box that WAS at F2_R4?
    # We iterate next_s.box_at_room to find value == "F2_R4"
    
    found_room = None
    for r, b in next_s.box_at_room.items():
        if b == str(r2_4):
            found_room = r
            break
            
    assert found_room == box_expected_intra_dst, \
        f"With d6=1, box from F2_R4 should move to {box_expected_intra_dst}, but moved to {found_room}"


def test_king_d6_other_activates_global_rotation():
    """Test that d6!=1 causes standard global rotation."""
    rooms = {}
    boxes = {}
    box_at_room = {}
    for rid in canonical_room_ids():
        rooms[rid] = RoomState(room_id=rid, deck=DeckState([]))
        bid = str(rid)
        boxes[bid] = BoxState(box_id=bid, deck=DeckState([]))
        box_at_room[rid] = bid
        
    s = GameState(
        round=1,
        players={},
        rooms=rooms,
        boxes=boxes,
        box_at_room=box_at_room,
        phase="KING",
        king_floor=1
    )
    
    # Find seed for d6=2 (or anything != 1)
    target_d6 = 2
    found_seed = None
    for seed in range(1000):
        rng = RNG(seed)
        _ = rng.randint(1, 4)
        val = rng.randint(1, 6)
        if val == target_d6:
            found_seed = seed
            break
            
    assert found_seed is not None
    rng = RNG(found_seed)
    
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    next_s = step(s, action, rng)
    
    assert rng.last_king_d6 == target_d6
    assert rng.last_king_d6 != 1
    
    # Check F2_R4 again (should follow Sushi cycle)
    # Sushi: src=F2_R4 -> dst=F1_R1.
    
    r2_4 = room_id(2, 4)
    box_expected_sushi_dst = room_id(1, 1)
    
    found_room = None
    for r, b in next_s.box_at_room.items():
        if b == str(r2_4):
            found_room = r
            break
            
    assert found_room == box_expected_sushi_dst, \
        f"With d6={target_d6}, box from F2_R4 should move to {box_expected_sushi_dst} (global), but moved to {found_room}"

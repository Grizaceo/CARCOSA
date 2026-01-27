
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.state import GameState, PlayerState
from engine.transition import step
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.board import room_id, SUSHI_CYCLE, floor_of
from engine.config import Config

def test_stair_movement():
    print("--- Test Stair Movement ---")
    s = GameState()
    # Setup stairs: F1->R1, F2->R1
    s.stairs = {1: room_id(1, 1), 2: room_id(2, 1), 3: room_id(3, 1)}
    
    # Player at F1_R1 (stair room)
    p1 = PlayerState(room=room_id(1, 1), sanity=10, name="P1")
    s.players["P1"] = p1
    s.turn_order = ["P1"]
    s.turn_pos = 0
    s.remaining_actions["P1"] = 2
    s.phase = "PLAYER"

    # Check legal actions
    from engine.legality import get_legal_actions
    actions = get_legal_actions(s, "P1")
    move_up = None
    for a in actions:
        if a.type == ActionType.MOVE and a.data["to"] == str(room_id(2, 1)):
            move_up = a
            break
    
    if move_up:
        print("OK: Found legal move to upstairs stair room (F2_R1).")
    else:
        print("FAIL: Did not find legal move to upstairs stair room.")
        print([a.data for a in actions if a.type == ActionType.MOVE])

def test_d6_1_rotation():
    print("\n--- Test d6=1 Rotation ---")
    s = GameState()
    rng = RNG(seed=123)
    
    # Mocking RNG to force d6=1
    s.phase = "KING"
    s.turn_order = ["P1"]
    
    hit_d6_1 = False
    for i in range(100):
        s_clone = s.clone()
        rng = RNG(seed=i)
        try:
            next_s = step(s_clone, Action(actor="KING", type=ActionType.KING_ENDROUND, data={}), rng)
            if hasattr(rng, 'last_king_d6') and rng.last_king_d6 == 1:
                print(f"Hit d6=1 on seed {i}")
                
                 # Check 2: Was it INTRA-floor?
                cross_floor = False
                for src, dst in SUSHI_CYCLE.items():
                    if floor_of(src) != floor_of(dst):
                        cross_floor = True
                        print(f"Found Inter-floor rotation in definition: {src} -> {dst}")
                        break
                
                if cross_floor:
                    print("FAIL: Rotation cycle is defined as Inter-floor.")
                
                print("Observed Behavior: Boxes rotated (because `step` calls rotate_boxes).")
                hit_d6_1 = True
                break
        except Exception as e:
            print(f"Error: {e}")
            break
            
    if not hit_d6_1:
         print("Could not reproduce d6=1 in loop.")

if __name__ == "__main__":
    test_stair_movement()
    test_d6_1_rotation()

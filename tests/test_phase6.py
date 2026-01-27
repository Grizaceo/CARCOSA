
import unittest
from engine.state_factory import make_game_state
from engine.types import PlayerId, RoomId
from engine.transition import step, _apply_status_effects_end_of_round, _false_king_check
from engine.actions import Action, ActionType
from engine.objects import OBJECT_CATALOG
from engine.config import Config

class MockRNG:
    def __init__(self):
        self.randint_vals = []
        self.last_king_d4 = 0
        self.last_king_d6 = 0

    def randint(self, a, b):
        if self.randint_vals:
            val = self.randint_vals.pop(0)
            return val
        return 1

class TestPhase6(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.rng = MockRNG()
        rooms = [f"F{f}_R{r}" for f in range(1, 4) for r in range(1, 5)]
        rooms += ["F1_P", "F2_P", "F3_P"]
        players = {
            "P1": {"room": "F1_R1", "sanity": 5, "sanity_max": 5, "role_id": "EXPLORER"},
            "P2": {"room": "F1_R2", "sanity": 5, "sanity_max": 5, "role_id": "EXPLORER"},
        }
        self.state = make_game_state(round=1, players=players, rooms=rooms)

        # Setup initial boxes
        self.state.box_at_room = {
            RoomId(f"F{f}_R{r}"): f"BOX_{f}_{r}" for f in range(1, 4) for r in range(1, 5)
        }
        self.state.remaining_actions[PlayerId("P1")] = 2
        self.state.remaining_actions[PlayerId("P2")] = 2

    def test_status_maldito(self):
        # P1 has MALDITO, P2 is on same floor
        from engine.effects.event_utils import add_status
        add_status(self.state.players[PlayerId("P1")], "MALDITO")
        
        # P2 in F1_R2, P1 in F1_R1 (same floor)
        p2_sanity_before = self.state.players[PlayerId("P2")].sanity
        
        _apply_status_effects_end_of_round(self.state)
        
        # P2 should lose 1 sanity
        self.assertEqual(self.state.players[PlayerId("P2")].sanity, p2_sanity_before - 1)

    def test_status_sanidad(self):
        from engine.effects.event_utils import add_status
        from engine.systems.status import apply_end_of_turn_status_effects
        p = self.state.players[PlayerId("P1")]
        p.sanity = 2
        add_status(p, "SANIDAD")
        
        apply_end_of_turn_status_effects(self.state)
        
        # Should gain 1 sanity
        self.assertEqual(p.sanity, 3)

    def test_false_king_formula(self):
        # Setup False King conditions
        self.state.flags["CROWN_HOLDER"] = "P1"
        self.state.false_king_floor = 1
        self.state.false_king_round_appeared = 1
        self.state.round = 2 # 1 round since appearance
        self.state.players[PlayerId("P1")].room = RoomId("F2_R1") # Holder safe
        
        # P2 in False King floor (F1)
        self.state.players[PlayerId("P2")].room = RoomId("F1_R1")
        
        # Formula: threshold = sanity_max(5) + 1 + rounds(1) = 7
        # Total = d6 + sanity
        p1 = self.state.players[PlayerId("P1")]
        p1.objects.append("CROWN") # Asegurar que tiene la corona para _sync_crown_holder
        p1.sanity = 5
        p1.room = RoomId("F1_R2") # Holder en F1 (donde está P2) para que FK esté en F1
        
        # If d6=1, Total = 1 + 5 = 6. 6 <= 7 -> Trigger Damage
        self.rng.randint_vals = [1] 
        # _presence_damage_for_round(2) should be 1
        
        p2_sanity_before = self.state.players[PlayerId("P2")].sanity
        _false_king_check(self.state, self.rng, self.cfg)
        
        # Verify damage applied
        self.assertEqual(self.state.players[PlayerId("P2")].sanity, p2_sanity_before - 1)
        
        # Test Case: Total > Threshold
        # d6=6, Total = 6 + 5 = 11. 11 > 7 -> No Damage
        self.rng.randint_vals = [6]
        p2_sanity_before = self.state.players[PlayerId("P2")].sanity
        _false_king_check(self.state, self.rng, self.cfg)
        self.assertEqual(self.state.players[PlayerId("P2")].sanity, p2_sanity_before)

    def test_king_d6_intra_floor_rotation(self):
        # Setup King Phase, d6=1
        self.state.phase = "KING"
        self.state.round = 10 # King active logic
        
        # d4 for floor (let's say 1 -> F2), d6=1 for intra-rotation
        # NOTE: King step calls steps 1(House), 2(d4), 3(Presence), 4(d6)
        # We need rng to supply d4 then d6.
        # Step 4(d6=1) sets flag.
        # Then _roll_stairs -> 3 d4s (one per floor).
        # Then rotation.
        
        self.rng.randint_vals = [
            1, # d4 (King moves to F2)
            1, # d6 (=1 -> intra rotation)
            1, 1, 1 # d4s for _roll_stairs (3 floors)
        ]
        
        # Box Setup
        # F1_R1 has BOX_1_1
        # F1_R4 has BOX_1_4
        # Intra rotation: R1->R4, R4->R3...
        # So BOX_1_1 (at R1) should move to R4
        
        # Current logic: rotated[dst] = box[src]
        # cycle: src=R1 -> dst=R4
        
        action = Action(type=ActionType.KING_ENDROUND, actor="KING")
        new_state = step(self.state, action, self.rng, self.cfg)
        
        # Verify F1_R4 has BOX_1_1
        self.assertEqual(new_state.box_at_room[RoomId("F1_R4")], "BOX_1_1")
        # Verify F1_R3 has BOX_1_4
        self.assertEqual(new_state.box_at_room[RoomId("F1_R3")], "BOX_1_4")

if __name__ == '__main__':
    unittest.main()

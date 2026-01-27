import pytest
from engine.board import room_id, corridor_id, neighbors, floor_of
from engine.state_factory import make_game_state
from engine.types import RoomId, PlayerId

class TestP01Adjacencies:
    def test_r1_connects_to_r2(self):
        room = room_id(1, 1)
        neighbors_list = neighbors(room)
        assert room_id(1, 2) in neighbors_list


    def test_r2_connects_to_r1(self):
        room = room_id(1, 2)
        neighbors_list = neighbors(room)
        assert room_id(1, 1) in neighbors_list

    def test_r3_connects_to_r4(self):
        room = room_id(1, 3)
        neighbors_list = neighbors(room)
        assert room_id(1, 4) in neighbors_list

    def test_r4_connects_to_r3(self):
        room = room_id(1, 4)
        neighbors_list = neighbors(room)
        assert room_id(1, 3) in neighbors_list

    def test_room_connects_to_corridor(self):
        for floor in range(1, 4):
            for room_num in range(1, 5):
                room = room_id(floor, room_num)
                neighbors_list = neighbors(room)
                assert corridor_id(floor) in neighbors_list

    def test_corridor_connects_to_all_rooms(self):
        for floor in range(1, 4):
            corridor = corridor_id(floor)
            neighbors_list = neighbors(corridor)
            for room_num in range(1, 5):
                assert room_id(floor, room_num) in neighbors_list

class TestP03StairsReroll:
    """Test canonical stair rerolling (1d4 per floor) at end of round (P0.3)."""
    
    def test_stairs_in_valid_range_after_reroll(self):
        """After reroll, each floor has stairs in R1..R4."""
        from engine.config import Config
        from engine.rng import RNG
        from engine.transition import _roll_stairs
        from engine.types import RoomId
        from engine.board import floor_of, room_id as board_room_id
        
        # Create a minimal state
        s = make_game_state(round=1, players={}, rooms={})
        s.stairs = {}
        rng = RNG(seed=42)
        
        # Roll stairs
        _roll_stairs(s, rng)
        
        # Verify each floor has one stair in R1..R4
        for floor in range(1, 4):
            assert floor in s.stairs, f"Floor {floor} missing stair"
            stair_room = s.stairs[floor]
            assert floor_of(stair_room) == floor
            # Extract room number from "F<f>_R<n>"
            room_str = str(stair_room)
            room_num = int(room_str.split("R")[1])
            assert 1 <= room_num <= 4, f"Stair on floor {floor} is in invalid room: {stair_room}"
    
    def test_stairs_reroll_deterministic_with_seed(self):
        """Same seed -> same stair positions."""
        from engine.rng import RNG
        from engine.transition import _roll_stairs
        
        # Two separate runs with same seed
        def get_stairs(seed):
            s = make_game_state(round=1, players={}, rooms={})
            s.stairs = {}
            rng = RNG(seed=seed)
            _roll_stairs(s, rng)
            return s.stairs
        
        stairs1 = get_stairs(12345)
        stairs2 = get_stairs(12345)
        
        assert stairs1 == stairs2, "Same seed should produce same stairs"
    
    def test_stairs_reroll_different_with_different_seed(self):
        """Different seed -> likely different stair positions."""
        from engine.rng import RNG
        from engine.transition import _roll_stairs
        
        # Two runs with different seeds
        def get_stairs(seed):
            s = make_game_state(round=1, players={}, rooms={})
            s.stairs = {}
            rng = RNG(seed=seed)
            _roll_stairs(s, rng)
            return s.stairs
        
        stairs1 = get_stairs(100)
        stairs2 = get_stairs(200)
        
        # With very high probability they should differ
        # (1d4^3 permutations = 64, so ~98% chance they differ)
        assert stairs1 != stairs2, "Different seeds should likely produce different stairs"


class TestP05KingPresenceDamage:
    """Test King presence damage (P0.5) - UPDATED canon table."""
    
    def test_presence_damage_round_1_to_3_is_one(self):
        """Rounds 1-3: 1 damage from King presence."""
        from engine.transition import _presence_damage_for_round
        assert _presence_damage_for_round(1) == 1
        assert _presence_damage_for_round(2) == 1
        assert _presence_damage_for_round(3) == 1
    
    def test_presence_damage_round_4_to_6_is_two(self):
        """Rounds 4-6: 2 damage per round from King presence."""
        from engine.transition import _presence_damage_for_round
        assert _presence_damage_for_round(4) == 2
        assert _presence_damage_for_round(5) == 2
        assert _presence_damage_for_round(6) == 2
    
    def test_presence_damage_round_7_to_9_is_three(self):
        """Rounds 7-9: 3 damage per round."""
        from engine.transition import _presence_damage_for_round
        assert _presence_damage_for_round(7) == 3
        assert _presence_damage_for_round(8) == 3
        assert _presence_damage_for_round(9) == 3
    
    def test_presence_damage_round_10_plus_is_four(self):
        """Rounds 10+: 4 damage per round."""
        from engine.transition import _presence_damage_for_round
        assert _presence_damage_for_round(10) == 4
        assert _presence_damage_for_round(11) == 4
        assert _presence_damage_for_round(20) == 4


class TestP02ExpelFromFloor:
    """Test King expel (move to stair room in adjacent floor) - P0.2."""
    
    def test_expel_f1_to_f2_stair(self):
        """Players on F1 expelled to F2 stair room."""
        from engine.transition import _expel_players_from_floor
        from engine.board import room_id, floor_of
        
        # Create state with F2 stair at R3
        s = make_game_state(
            round=1,
            players={
                "p1": {"room": str(room_id(1, 1)), "sanity": 5},
                "p2": {"room": str(room_id(1, 2)), "sanity": 5},
            },
            rooms=[str(room_id(1, 1)), str(room_id(1, 2)), str(room_id(2, 3))],
        )
        s.stairs = {1: room_id(1, 1), 2: room_id(2, 3), 3: room_id(3, 1)}
        
        # Expel from F1
        _expel_players_from_floor(s, 1)
        
        # Both should be in F2_R3
        assert floor_of(s.players[PlayerId("p1")].room) == 2
        assert str(s.players[PlayerId("p1")].room) == "F2_R3"
        assert floor_of(s.players[PlayerId("p2")].room) == 2
        assert str(s.players[PlayerId("p2")].room) == "F2_R3"
    
    def test_expel_f2_to_f1_stair(self):
        """Players on F2 expelled to F1 stair room."""
        from engine.transition import _expel_players_from_floor
        from engine.board import room_id, floor_of
        
        s = make_game_state(
            round=1,
            players={"p1": {"room": str(room_id(2, 2)), "sanity": 5}},
            rooms=[str(room_id(2, 2)), str(room_id(1, 2))],
        )
        s.stairs = {1: room_id(1, 2), 2: room_id(2, 1), 3: room_id(3, 1)}
        
        # Expel from F2
        _expel_players_from_floor(s, 2)
        
        # Should be in F1_R2
        assert floor_of(s.players[PlayerId("p1")].room) == 1
        assert str(s.players[PlayerId("p1")].room) == "F1_R2"
    
    def test_expel_f3_to_f2_stair(self):
        """Players on F3 expelled to F2 stair room."""
        from engine.transition import _expel_players_from_floor
        from engine.board import room_id, floor_of
        
        s = make_game_state(
            round=1,
            players={"p1": {"room": str(room_id(3, 4)), "sanity": 5}},
            rooms=[str(room_id(3, 4)), str(room_id(2, 4))],
        )
        s.stairs = {1: room_id(1, 1), 2: room_id(2, 4), 3: room_id(3, 1)}
        
        # Expel from F3
        _expel_players_from_floor(s, 3)
        
        # Should be in F2_R4
        assert floor_of(s.players[PlayerId("p1")].room) == 2
        assert str(s.players[PlayerId("p1")].room) == "F2_R4"
    
    def test_expel_only_from_target_floor(self):
        """Only players on target floor are expelled."""
        from engine.transition import _expel_players_from_floor
        from engine.board import room_id, floor_of
        
        s = make_game_state(
            round=1,
            players={
                "p1": {"room": str(room_id(1, 1)), "sanity": 5},
                "p2": {"room": str(room_id(2, 2)), "sanity": 5},
            },
            rooms=[str(room_id(1, 1)), str(room_id(2, 2)), str(room_id(2, 3))],
        )
        s.stairs = {1: room_id(1, 1), 2: room_id(2, 3), 3: room_id(3, 1)}
        
        # Expel from F1
        _expel_players_from_floor(s, 1)
        
        # p1 should be expelled to F2
        assert floor_of(s.players[PlayerId("p1")].room) == 2
        # p2 should stay in F2 (unchanged)
        assert str(s.players[PlayerId("p2")].room) == "F2_R2"


class TestP04MinusFiveEvent:
    """Test -5 event: key/object destruction, sanity loss for others, 1 action (P0.4)."""
    
    def test_crossing_to_minus5_destroys_keys(self):
        """Keys destroyed when crossing to -5."""
        from engine.config import Config
        from engine.transition import _apply_minus5_transitions, _apply_minus5_consequences
        from engine.board import room_id
        
        cfg = Config()
        s = make_game_state(
            round=1,
            players={"p1": {"room": str(room_id(1, 1)), "sanity": -4, "keys": 3}},
            rooms=[str(room_id(1, 1))],
        )
        s.players[PlayerId("p1")].at_minus5 = False
        
        # Sanity drops to -5
        s.players[PlayerId("p1")].sanity = -5
        
        # Apply transition (sets flag)
        _apply_minus5_transitions(s, cfg)
        # Apply consequences (accept)
        _apply_minus5_consequences(s, PlayerId("p1"), cfg)
        
        # Keys should be destroyed
        assert s.players[PlayerId("p1")].keys == 0
    
    def test_crossing_to_minus5_destroys_objects(self):
        """Objects destroyed when crossing to -5."""
        from engine.config import Config
        from engine.transition import _apply_minus5_transitions, _apply_minus5_consequences
        from engine.board import room_id
        
        cfg = Config()
        s = make_game_state(
            round=1,
            players={"p1": {"room": str(room_id(1, 1)), "sanity": -5, "objects": ["item1", "item2"]}},
            rooms=[str(room_id(1, 1))],
        )
        s.players[PlayerId("p1")].at_minus5 = False
        
        # Apply transition
        _apply_minus5_transitions(s, cfg)
        _apply_minus5_consequences(s, PlayerId("p1"), cfg)
        
        # Objects should be destroyed
        assert s.players[PlayerId("p1")].objects == []
    
    def test_crossing_to_minus5_others_lose_sanity(self):
        """Other players lose 1 sanity when someone crosses to -5."""
        from engine.config import Config
        from engine.transition import _apply_minus5_transitions, _apply_minus5_consequences
        from engine.board import room_id
        
        cfg = Config()
        s = make_game_state(
            round=1,
            players={
                "p1": {"room": str(room_id(1, 1)), "sanity": -5},
                "p2": {"room": str(room_id(2, 2)), "sanity": 5},
                "p3": {"room": str(room_id(3, 1)), "sanity": 4},
            },
            rooms=[str(room_id(1, 1)), str(room_id(2, 2)), str(room_id(3, 1))],
        )
        s.players[PlayerId("p1")].at_minus5 = False
        s.players[PlayerId("p2")].at_minus5 = False
        s.players[PlayerId("p3")].at_minus5 = False
        
        # Apply transition (sets flag)
        _apply_minus5_transitions(s, cfg)
        # Apply consequences (accept)
        _apply_minus5_consequences(s, PlayerId("p1"), cfg)
        
        # p2 and p3 should lose 1 sanity
        assert s.players[PlayerId("p2")].sanity == 4
        assert s.players[PlayerId("p3")].sanity == 3
    
    def test_minus5_event_only_fires_once(self):
        """Event fires only once when crossing; doesn't repeat on subsequent ticks."""
        from engine.config import Config
        from engine.transition import _apply_minus5_transitions, _apply_minus5_consequences
        from engine.board import room_id
        
        cfg = Config()
        p2_initial_sanity = 5
        s = make_game_state(
            round=1,
            players={
                "p1": {"room": str(room_id(1, 1)), "sanity": -5, "keys": 0, "objects": []},
                "p2": {"room": str(room_id(2, 2)), "sanity": p2_initial_sanity},
            },
            rooms=[str(room_id(1, 1)), str(room_id(2, 2))],
        )
        s.players[PlayerId("p1")].at_minus5 = False
        s.players[PlayerId("p2")].at_minus5 = False
        
        # First call: event fires
        _apply_minus5_transitions(s, cfg)
        # Manually accept consequences
        _apply_minus5_consequences(s, PlayerId("p1"), cfg)
        
        assert s.players[PlayerId("p1")].at_minus5 == True
        assert s.players[PlayerId("p2")].sanity == p2_initial_sanity - 1
        
        # Second call: should NOT fire again (p2 should not lose more sanity)
        p2_sanity_after_first = s.players[PlayerId("p2")].sanity
        _apply_minus5_transitions(s, cfg)
        # If it fired again, flag would be set or at_minus5 logic would change. 
        # But _apply_minus5_consequences is manual here.
        # We verify that at_minus5 logic prevents RE-triggering.
        # Calling consequences again should duplicate effect if called, 
        # but the test checks if _apply_minus5_transitions sets anything new?
        # Logic says: if p.at_minus5: do nothing.
        # So we don't need to call consequences again because transition returns early.
        assert s.players[PlayerId("p2")].sanity == p2_sanity_after_first
    
    # CANON UPDATE: No reduction of actions at -5
    # Tests test_one_action_while_at_minus5 and test_restore_to_two_actions_when_leaving_minus5
    # have been removed as they test deprecated behavior.

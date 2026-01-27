#!/usr/bin/env python3
"""Add P0.3 (stairs reroll) tests to test_p0_canon.py"""

tests_p03 = '''
class TestP03StairsReroll:
    """Test canonical stair rerolling (1d4 per floor) at end of round (P0.3)."""
    
    def test_stairs_in_valid_range_after_reroll(self):
        """After reroll, each floor has stairs in R1..R4."""
        from engine.state import GameState
        from engine.config import Config
        from engine.rng import RNG
        from engine.transition import _roll_stairs
        from engine.types import PlayerId, RoomId
        from engine.board import floor_of, room_id as board_room_id
        
        # Create a minimal state
        s = GameState(
            round=1,
            players={PlayerId("p1"): None},
            stairs={}
        )
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
        from engine.state import GameState
        from engine.rng import RNG
        from engine.transition import _roll_stairs
        from engine.types import PlayerId
        
        # Two separate runs with same seed
        def get_stairs(seed):
            s = GameState(
                round=1,
                players={PlayerId("p1"): None},
                stairs={}
            )
            rng = RNG(seed=seed)
            _roll_stairs(s, rng)
            return s.stairs
        
        stairs1 = get_stairs(12345)
        stairs2 = get_stairs(12345)
        
        assert stairs1 == stairs2, "Same seed should produce same stairs"
    
    def test_stairs_reroll_different_with_different_seed(self):
        """Different seed -> likely different stair positions."""
        from engine.state import GameState
        from engine.rng import RNG
        from engine.transition import _roll_stairs
        from engine.types import PlayerId
        
        # Two runs with different seeds
        def get_stairs(seed):
            s = GameState(
                round=1,
                players={PlayerId("p1"): None},
                stairs={}
            )
            rng = RNG(seed=seed)
            _roll_stairs(s, rng)
            return s.stairs
        
        stairs1 = get_stairs(100)
        stairs2 = get_stairs(200)
        
        # With very high probability they should differ
        # (1d4^3 permutations = 64, so ~98% chance they differ)
        assert stairs1 != stairs2, "Different seeds should likely produce different stairs"


class TestP05KingPresenceDamage:
    """Test King presence damage (P0.5)."""
    
    def test_presence_damage_round_1_is_zero(self):
        """Round 1: no damage from King presence."""
        from engine.transition import _presence_damage_for_round
        assert _presence_damage_for_round(1) == 0
    
    def test_presence_damage_round_2_plus_is_one(self):
        """Round 2+: 1 damage per round from King presence."""
        from engine.transition import _presence_damage_for_round
        assert _presence_damage_for_round(2) == 1
        assert _presence_damage_for_round(3) == 1
        assert _presence_damage_for_round(10) == 1
'''

# Read current file
with open('tests/test_p0_canon.py', 'r') as f:
    current = f.read()

# Append new tests
with open('tests/test_p0_canon.py', 'w') as f:
    f.write(current)
    f.write(tests_p03)

print('✓ P0.3 and P0.5 tests added to test_p0_canon.py')

#!/usr/bin/env python3
"""Add P0.2 (expel from floor) tests"""

tests_p02 = '''

class TestP02ExpelFromFloor:
    """Test King expel (move to stair room in adjacent floor) - P0.2."""
    
    def test_expel_f1_to_f2_stair(self):
        """Players on F1 expelled to F2 stair room."""
        from engine.state import GameState, PlayerState
        from engine.types import PlayerId, RoomId
        from engine.transition import _expel_players_from_floor
        from engine.board import room_id, floor_of
        
        # Create state with F2 stair at R3
        s = GameState(
            round=1,
            players={
                PlayerId("p1"): PlayerState(
                    player_id=PlayerId("p1"),
                    sanity=5,
                    room=room_id(1, 1)  # F1_R1
                ),
                PlayerId("p2"): PlayerState(
                    player_id=PlayerId("p2"),
                    sanity=5,
                    room=room_id(1, 2)  # F1_R2
                )
            },
            stairs={1: room_id(1, 1), 2: room_id(2, 3), 3: room_id(3, 1)}
        )
        
        # Expel from F1
        _expel_players_from_floor(s, 1)
        
        # Both should be in F2_R3
        assert floor_of(s.players[PlayerId("p1")].room) == 2
        assert str(s.players[PlayerId("p1")].room) == "F2_R3"
        assert floor_of(s.players[PlayerId("p2")].room) == 2
        assert str(s.players[PlayerId("p2")].room) == "F2_R3"
    
    def test_expel_f2_to_f1_stair(self):
        """Players on F2 expelled to F1 stair room."""
        from engine.state import GameState, PlayerState
        from engine.types import PlayerId, RoomId
        from engine.transition import _expel_players_from_floor
        from engine.board import room_id, floor_of
        
        s = GameState(
            round=1,
            players={
                PlayerId("p1"): PlayerState(
                    player_id=PlayerId("p1"),
                    sanity=5,
                    room=room_id(2, 2)  # F2_R2
                )
            },
            stairs={1: room_id(1, 2), 2: room_id(2, 1), 3: room_id(3, 1)}
        )
        
        # Expel from F2
        _expel_players_from_floor(s, 2)
        
        # Should be in F1_R2
        assert floor_of(s.players[PlayerId("p1")].room) == 1
        assert str(s.players[PlayerId("p1")].room) == "F1_R2"
    
    def test_expel_f3_to_f2_stair(self):
        """Players on F3 expelled to F2 stair room."""
        from engine.state import GameState, PlayerState
        from engine.types import PlayerId, RoomId
        from engine.transition import _expel_players_from_floor
        from engine.board import room_id, floor_of
        
        s = GameState(
            round=1,
            players={
                PlayerId("p1"): PlayerState(
                    player_id=PlayerId("p1"),
                    sanity=5,
                    room=room_id(3, 4)  # F3_R4
                )
            },
            stairs={1: room_id(1, 1), 2: room_id(2, 4), 3: room_id(3, 1)}
        )
        
        # Expel from F3
        _expel_players_from_floor(s, 3)
        
        # Should be in F2_R4
        assert floor_of(s.players[PlayerId("p1")].room) == 2
        assert str(s.players[PlayerId("p1")].room) == "F2_R4"
    
    def test_expel_only_from_target_floor(self):
        """Only players on target floor are expelled."""
        from engine.state import GameState, PlayerState
        from engine.types import PlayerId, RoomId
        from engine.transition import _expel_players_from_floor
        from engine.board import room_id, floor_of
        
        s = GameState(
            round=1,
            players={
                PlayerId("p1"): PlayerState(
                    player_id=PlayerId("p1"),
                    sanity=5,
                    room=room_id(1, 1)  # F1
                ),
                PlayerId("p2"): PlayerState(
                    player_id=PlayerId("p2"),
                    sanity=5,
                    room=room_id(2, 2)  # F2
                )
            },
            stairs={1: room_id(1, 1), 2: room_id(2, 3), 3: room_id(3, 1)}
        )
        
        # Expel from F1
        _expel_players_from_floor(s, 1)
        
        # p1 should be expelled to F2
        assert floor_of(s.players[PlayerId("p1")].room) == 2
        # p2 should stay in F2 (unchanged)
        assert str(s.players[PlayerId("p2")].room) == "F2_R2"
'''

# Read current file
with open('tests/test_p0_canon.py', 'r') as f:
    current = f.read()

# Append new tests
with open('tests/test_p0_canon.py', 'w') as f:
    f.write(current)
    f.write(tests_p02)

print('✓ P0.2 tests added')

#!/usr/bin/env python3
"""Add P0.4 (event -5) tests"""

tests_p04 = '''

class TestP04MinusFiveEvent:
    """Test -5 event: key/object destruction, sanity loss for others, 1 action (P0.4)."""
    
    def test_crossing_to_minus5_destroys_keys(self):
        """Keys destroyed when crossing to -5."""
        from engine.state import GameState, PlayerState
        from engine.types import PlayerId
        from engine.config import Config
        from engine.transition import _apply_minus5_transitions
        from engine.board import room_id
        
        cfg = Config()
        s = GameState(
            round=1,
            players={
                PlayerId("p1"): PlayerState(
                    player_id=PlayerId("p1"),
                    sanity=-4,  # Will cross to -5
                    room=room_id(1, 1),
                    keys=3,
                    at_minus5=False
                )
            }
        )
        
        # Sanity drops to -5
        s.players[PlayerId("p1")].sanity = -5
        
        # Apply transition
        _apply_minus5_transitions(s, cfg)
        
        # Keys should be destroyed
        assert s.players[PlayerId("p1")].keys == 0
    
    def test_crossing_to_minus5_destroys_objects(self):
        """Objects destroyed when crossing to -5."""
        from engine.state import GameState, PlayerState
        from engine.types import PlayerId
        from engine.config import Config
        from engine.transition import _apply_minus5_transitions
        from engine.board import room_id
        
        cfg = Config()
        s = GameState(
            round=1,
            players={
                PlayerId("p1"): PlayerState(
                    player_id=PlayerId("p1"),
                    sanity=-5,
                    room=room_id(1, 1),
                    objects=["item1", "item2"],
                    at_minus5=False
                )
            }
        )
        
        # Apply transition
        _apply_minus5_transitions(s, cfg)
        
        # Objects should be destroyed
        assert s.players[PlayerId("p1")].objects == []
    
    def test_crossing_to_minus5_others_lose_sanity(self):
        """Other players lose 1 sanity when someone crosses to -5."""
        from engine.state import GameState, PlayerState
        from engine.types import PlayerId
        from engine.config import Config
        from engine.transition import _apply_minus5_transitions
        from engine.board import room_id
        
        cfg = Config()
        s = GameState(
            round=1,
            players={
                PlayerId("p1"): PlayerState(
                    player_id=PlayerId("p1"),
                    sanity=-5,
                    room=room_id(1, 1),
                    at_minus5=False
                ),
                PlayerId("p2"): PlayerState(
                    player_id=PlayerId("p2"),
                    sanity=5,
                    room=room_id(2, 2),
                    at_minus5=False
                ),
                PlayerId("p3"): PlayerState(
                    player_id=PlayerId("p3"),
                    sanity=4,
                    room=room_id(3, 1),
                    at_minus5=False
                )
            }
        )
        
        # Apply transition
        _apply_minus5_transitions(s, cfg)
        
        # p2 and p3 should lose 1 sanity
        assert s.players[PlayerId("p2")].sanity == 4
        assert s.players[PlayerId("p3")].sanity == 3
    
    def test_minus5_event_only_fires_once(self):
        """Event fires only once when crossing; doesn't repeat on subsequent ticks."""
        from engine.state import GameState, PlayerState
        from engine.types import PlayerId
        from engine.config import Config
        from engine.transition import _apply_minus5_transitions
        from engine.board import room_id
        
        cfg = Config()
        p2_initial_sanity = 5
        s = GameState(
            round=1,
            players={
                PlayerId("p1"): PlayerState(
                    player_id=PlayerId("p1"),
                    sanity=-5,
                    room=room_id(1, 1),
                    keys=0,
                    objects=[],
                    at_minus5=False
                ),
                PlayerId("p2"): PlayerState(
                    player_id=PlayerId("p2"),
                    sanity=p2_initial_sanity,
                    room=room_id(2, 2),
                    at_minus5=False
                )
            }
        )
        
        # First call: event fires
        _apply_minus5_transitions(s, cfg)
        assert s.players[PlayerId("p1")].at_minus5 == True
        assert s.players[PlayerId("p2")].sanity == p2_initial_sanity - 1
        
        # Second call: should NOT fire again (p2 should not lose more sanity)
        p2_sanity_after_first = s.players[PlayerId("p2")].sanity
        _apply_minus5_transitions(s, cfg)
        assert s.players[PlayerId("p2")].sanity == p2_sanity_after_first
    
    def test_one_action_while_at_minus5(self):
        """Player at -5 has only 1 action per turn."""
        from engine.state import GameState, PlayerState
        from engine.types import PlayerId
        from engine.config import Config
        from engine.transition import _apply_minus5_transitions
        from engine.board import room_id
        
        cfg = Config()
        s = GameState(
            round=1,
            players={
                PlayerId("p1"): PlayerState(
                    player_id=PlayerId("p1"),
                    sanity=-5,
                    room=room_id(1, 1),
                    at_minus5=False
                )
            },
            remaining_actions={PlayerId("p1"): 2}
        )
        
        # Apply transition
        _apply_minus5_transitions(s, cfg)
        
        # Should be capped to 1 action
        assert s.remaining_actions[PlayerId("p1")] == 1
    
    def test_restore_to_two_actions_when_leaving_minus5(self):
        """Player leaving -5 (to -4) restores to 2 actions."""
        from engine.state import GameState, PlayerState
        from engine.types import PlayerId
        from engine.config import Config
        from engine.transition import _apply_minus5_transitions
        from engine.board import room_id
        
        cfg = Config()
        s = GameState(
            round=1,
            players={
                PlayerId("p1"): PlayerState(
                    player_id=PlayerId("p1"),
                    sanity=-4,  # Above -5
                    room=room_id(1, 1),
                    at_minus5=True  # Was at -5, now leaving
                )
            },
            remaining_actions={PlayerId("p1"): 1}
        )
        
        # Apply transition
        _apply_minus5_transitions(s, cfg)
        
        # Should restore to 2 actions and clear flag
        assert s.remaining_actions[PlayerId("p1")] == 2
        assert s.players[PlayerId("p1")].at_minus5 == False
'''

# Read current file
with open('tests/test_p0_canon.py', 'r') as f:
    current = f.read()

# Append new tests
with open('tests/test_p0_canon.py', 'w') as f:
    f.write(current)
    f.write(tests_p04)

print('✓ P0.4 tests added')

"""
Tests for P0 Core updates (P0.4a, P0.4b, P0.5 revised).
- P0.4a: Keys destroyed counter coherence
- P0.4b: Attract with crown holder floor exception
- P0.5 (revised): Presence damage by round table
"""

import pytest
from engine.state import GameState, PlayerState
from engine.types import PlayerId
from engine.config import Config
from engine.board import room_id, corridor_id, floor_of
from engine.transition import _apply_minus5_transitions, _attract_players_to_floor, _presence_damage_for_round


class TestP04aKeysDestroyedCoherence:
    """Test that keys_destroyed counter increments when keys are destroyed at -5."""
    
    def test_keys_destroyed_increments_on_minus5_crossing(self):
        """When crossing to -5, keys_destroyed should increase by the destroyed count."""
        cfg = Config()
        p1 = PlayerState(
            player_id=PlayerId("p1"),
            sanity=-4,
            room=room_id(1, 1),
            keys=3,
            at_minus5=False
        )
        s = GameState(
            round=1,
            players={PlayerId("p1"): p1}
        )
        
        # Apply transition: player crosses from -4 to -5
        p1.sanity = -5
        _apply_minus5_transitions(s, cfg)
        
        # Verify keys destroyed counter increased
        assert s.keys_destroyed == 3, f"Expected keys_destroyed=3, got {s.keys_destroyed}"
        # Verify player's keys are now 0
        assert s.players[PlayerId("p1")].keys == 0
        # Verify at_minus5 flag is set
        assert s.players[PlayerId("p1")].at_minus5 is True
    
    def test_keys_destroyed_no_repeat_on_second_tick_at_minus5(self):
        """Second tick at -5 should NOT repeat key destruction."""
        cfg = Config()
        p1 = PlayerState(
            player_id=PlayerId("p1"),
            sanity=-5,
            room=room_id(1, 1),
            keys=0,
            at_minus5=True  # Already marked as at -5
        )
        s = GameState(
            round=1,
            players={PlayerId("p1"): p1},
            keys_destroyed=3  # Already destroyed 3 keys on previous crossing
        )
        
        # Apply transition again (already at -5)
        _apply_minus5_transitions(s, cfg)
        
        # Verify keys_destroyed did NOT increase
        assert s.keys_destroyed == 3, f"Expected keys_destroyed=3 (no repeat), got {s.keys_destroyed}"
    
    def test_multiple_players_keys_destroyed_sum(self):
        """When multiple players cross to -5, all keys should be counted."""
        cfg = Config()
        p1 = PlayerState(
            player_id=PlayerId("p1"),
            sanity=-4,
            room=room_id(1, 1),
            keys=2,
            at_minus5=False
        )
        p2 = PlayerState(
            player_id=PlayerId("p2"),
            sanity=-3,  # Start at -3, only p1 crosses to -5 first
            room=room_id(1, 2),
            keys=1,
            at_minus5=False
- P0.5 (revised): Presence damage by round table
"""

import pytest
from engine.state import GameState, PlayerState
from engine.types import PlayerId
from engine.config import Config
from engine.board import room_id, corridor_id, floor_of
from engine.transition import _apply_minus5_transitions, _attract_players_to_floor, _presence_damage_for_round, _apply_minus5_consequences


class TestP04aKeysDestroyedCoherence:
    """Test that keys_destroyed counter increments when keys are destroyed at -5."""
    
    def test_keys_destroyed_increments_on_minus5_crossing(self):
        """When crossing to -5, keys_destroyed should increase by the destroyed count."""
        cfg = Config()
        p1 = PlayerState(
            player_id=PlayerId("p1"),
            sanity=-4,
            room=room_id(1, 1),
            keys=3,
            at_minus5=False
        )
        s = GameState(
            round=1,
            players={PlayerId("p1"): p1}
        )
        
        # Apply transition: player crosses from -4 to -5
        p1.sanity = -5
        _apply_minus5_transitions(s, cfg)
        
        # Verify keys destroyed counter increased
        assert s.keys_destroyed == 3, f"Expected keys_destroyed=3, got {s.keys_destroyed}"
        # Verify player's keys are now 0
        assert s.players[PlayerId("p1")].keys == 0
        # Verify at_minus5 flag is set
        assert s.players[PlayerId("p1")].at_minus5 is True
    
    def test_keys_destroyed_no_repeat_on_second_tick_at_minus5(self):
        """Second tick at -5 should NOT repeat key destruction."""
        cfg = Config()
        p1 = PlayerState(
            player_id=PlayerId("p1"),
            sanity=-5,
            room=room_id(1, 1),
            keys=0,
            at_minus5=True  # Already marked as at -5
        )
        s = GameState(
            round=1,
            players={PlayerId("p1"): p1},
            keys_destroyed=3  # Already destroyed 3 keys on previous crossing
        )
        
        # Apply transition again (already at -5)
        _apply_minus5_transitions(s, cfg)
        
        # Verify keys_destroyed did NOT increase
        assert s.keys_destroyed == 3, f"Expected keys_destroyed=3 (no repeat), got {s.keys_destroyed}"
    
    def test_multiple_players_keys_destroyed_sum(self):
        """When multiple players cross to -5, all keys should be counted."""
        cfg = Config()
        p1 = PlayerState(
            player_id=PlayerId("p1"),
            sanity=-4,
            room=room_id(1, 1),
            keys=2,
            at_minus5=False
        )
        p2 = PlayerState(
            player_id=PlayerId("p2"),
            sanity=-3,  # Start at -3, only p1 crosses to -5 first
            room=room_id(1, 2),
            keys=1,
            at_minus5=False
        )
        s = GameState(
            round=1,
            players={PlayerId("p1"): p1, PlayerId("p2"): p2}
        )
        
        # p1 crosses to -5
        p1.sanity = -5
        _apply_minus5_transitions(s, cfg)
        _apply_minus5_consequences(s, PlayerId("p1"), cfg)
        assert s.keys_destroyed == 2
        
        # p2 crosses to -5
        p2.sanity = -5
        _apply_minus5_transitions(s, cfg)
        _apply_minus5_consequences(s, PlayerId("p2"), cfg)
        assert s.keys_destroyed == 3, f"Expected keys_destroyed=3 (2+1), got {s.keys_destroyed}"


class TestP04bAttractWithFalseKing:
    """Test attract action respects crown-holder false king floor exception."""
    
    def test_attract_all_without_false_king(self):
        """Without crown holder, all players go to corridor."""
        cfg = Config()
        p1 = PlayerState(player_id=PlayerId("p1"), sanity=5, room=room_id(1, 1))
        p2 = PlayerState(player_id=PlayerId("p2"), sanity=5, room=room_id(2, 2))
        p3 = PlayerState(player_id=PlayerId("p3"), sanity=5, room=room_id(3, 3))
        
        s = GameState(
            round=1,
            players={PlayerId("p1"): p1, PlayerId("p2"): p2, PlayerId("p3"): p3},
            false_king_floor=None  # No false king
        )
        
        # Attract to floor 2
        _attract_players_to_floor(s, 2)
        
        target = corridor_id(2)
        assert s.players[PlayerId("p1")].room == target
        assert s.players[PlayerId("p2")].room == target
        assert s.players[PlayerId("p3")].room == target
    
    def test_attract_excludes_false_king_floor(self):
        """Players on crown holder floor should NOT move."""
        cfg = Config()
        p1 = PlayerState(player_id=PlayerId("p1"), sanity=5, room=room_id(1, 1))
        p2 = PlayerState(player_id=PlayerId("p2"), sanity=5, room=room_id(2, 2))
        p3 = PlayerState(player_id=PlayerId("p3"), sanity=5, room=room_id(3, 3))
        
        s = GameState(
            round=1,
            players={PlayerId("p1"): p1, PlayerId("p2"): p2, PlayerId("p3"): p3},
            flags={"CROWN_YELLOW": True, "CROWN_HOLDER": "p2"}
        )
        p2.soulbound_items.append("CROWN")
        
        # Attract to floor 1
        _attract_players_to_floor(s, 1)
        
        target = corridor_id(1)
        # p1 should move (not on crown holder floor)
        assert s.players[PlayerId("p1")].room == target
        # p2 should NOT move (on crown holder floor)
        assert s.players[PlayerId("p2")].room == room_id(2, 2)
        # p3 should move (not on crown holder floor)
        assert s.players[PlayerId("p3")].room == target
    
    def test_attract_false_king_different_floor(self):
        """Attract to crown holder floor: only players NOT on it move."""
        cfg = Config()
        p1 = PlayerState(player_id=PlayerId("p1"), sanity=5, room=room_id(1, 1))
        p2 = PlayerState(player_id=PlayerId("p2"), sanity=5, room=room_id(2, 2))
        
        s = GameState(
            round=1,
            players={PlayerId("p1"): p1, PlayerId("p2"): p2},
            flags={"CROWN_YELLOW": True, "CROWN_HOLDER": "p2"}
        )
        p2.soulbound_items.append("CROWN")
        
        # Attract TO floor 2 (where crown holder is)
        _attract_players_to_floor(s, 2)
        
        target = corridor_id(2)
        # p1 should move (not on crown holder floor)
        assert s.players[PlayerId("p1")].room == target
        # p2 should NOT move (on crown holder floor)
        assert s.players[PlayerId("p2")].room == room_id(2, 2)


class TestP05PresenceDamageTable:
    """Test presence damage uses the confirmed canon table."""
    
    @pytest.mark.parametrize("round_no,expected_damage", [
        (1, 1),   # R1-R3: 1
        (2, 1),
        (3, 1),
        (4, 2),   # R4-R6: 2
        (5, 2),
        (6, 2),
        (7, 3),   # R7-R9: 3
        (8, 3),
        (9, 3),
        (10, 4),  # R10+: 4
        (11, 4),
        (20, 4),
    ])
    def test_presence_damage_by_round_table(self, round_no, expected_damage):
        """Presence damage follows the canon table."""
        damage = _presence_damage_for_round(round_no)
        assert damage == expected_damage, f"Round {round_no}: expected {expected_damage}, got {damage}"

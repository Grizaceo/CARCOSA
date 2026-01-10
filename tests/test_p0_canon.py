import pytest
from engine.board import room_id, corridor_id, neighbors, floor_of
from engine.types import RoomId

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

#!/usr/bin/env python3
"""Quick validation script to test core functionality."""
import sys

print("=" * 60)
print("Testing engine.board...")
print("=" * 60)

try:
    from engine.board import room_id, corridor_id, neighbors, floor_of, is_corridor
    
    # Test room_id
    r = room_id(1, 1)
    assert str(r) == "F1_R1", f"Expected 'F1_R1', got '{r}'"
    print(f"✓ room_id(1, 1) = {r}")
    
    # Test floor_of
    f = floor_of(r)
    assert f == 1, f"Expected floor 1, got {f}"
    print(f"✓ floor_of({r}) = {f}")
    
    # Test corridor_id
    c = corridor_id(1)
    assert str(c) == "F1_P", f"Expected 'F1_P', got '{c}'"
    print(f"✓ corridor_id(1) = {c}")
    
    # Test is_corridor
    assert is_corridor(c), f"{c} should be corridor"
    assert not is_corridor(r), f"{r} should not be corridor"
    print(f"✓ is_corridor() works")
    
    # Test neighbors
    neighbors_r1 = neighbors(r)
    assert room_id(1, 2) in neighbors_r1, f"R1 should connect to R2"
    assert corridor_id(1) in neighbors_r1, f"R1 should connect to corridor"
    print(f"✓ neighbors({r}) = {neighbors_r1}")
    
    print("✓ engine.board tests passed\n")
    
except Exception as e:
    print(f"✗ engine.board tests failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 60)
print("Testing engine.state...")
print("=" * 60)

try:
    from engine.state import GameState, PlayerState
    from engine.types import PlayerId
    
    # Test PlayerState
    p = PlayerState(player_id=PlayerId("test"), sanity=5, room=room_id(1, 1))
    assert p.keys == 0, "Default keys should be 0"
    assert p.at_minus5 == False, "Default at_minus5 should be False"
    print(f"✓ PlayerState created: {p.player_id}")
    
    # Test GameState
    s = GameState(
        round=1,
        players={PlayerId("p1"): p}
    )
    assert s.round == 1, "Round should be 1"
    assert PlayerId("p1") in s.players, "Player should be in state"
    print(f"✓ GameState created with 1 player")
    
    print("✓ engine.state tests passed\n")
    
except Exception as e:
    print(f"✗ engine.state tests failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 60)
print("Testing engine.transition...")
print("=" * 60)

try:
    from engine.transition import _roll_stairs, _expel_players_from_floor, _presence_damage_for_round
    from engine.rng import RNG
    from engine.config import Config
    
    # Test _roll_stairs
    s = GameState(round=1, players={PlayerId("p1"): p})
    rng = RNG(seed=42)
    _roll_stairs(s, rng)
    for floor in range(1, 4):
        assert floor in s.stairs, f"Floor {floor} missing stair after reroll"
    print(f"✓ _roll_stairs() works")
    
    # Test _expel_players_from_floor
    p1 = PlayerState(player_id=PlayerId("p1"), sanity=5, room=room_id(1, 1))
    s = GameState(
        round=1,
        players={PlayerId("p1"): p1},
        stairs={1: room_id(1, 1), 2: room_id(2, 3), 3: room_id(3, 1)}
    )
    _expel_players_from_floor(s, 1)
    assert floor_of(s.players[PlayerId("p1")].room) == 2, "Player should be expelled to F2"
    print(f"✓ _expel_players_from_floor() works")
    
    # Test _presence_damage_for_round
    d1 = _presence_damage_for_round(1)
    d2 = _presence_damage_for_round(2)
    assert d1 == 0, "Round 1 damage should be 0"
    assert d2 == 1, "Round 2+ damage should be 1"
    print(f"✓ _presence_damage_for_round() works")
    
    print("✓ engine.transition tests passed\n")
    
except Exception as e:
    print(f"✗ engine.transition tests failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 60)
print("✓ All validation tests passed!")
print("=" * 60)

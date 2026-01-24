
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId
from engine.config import Config
from engine.transition import _check_victory

def test_victory_condition():
    print("=== Testing Victory Condition Logic ===")
    
    # Setup Config
    cfg = Config()
    
    # Scenario 1: 2 Players, 2 Keys (Max Capacity), All in F2_P
    # Should FAIL (Keys < 4)
    print("\nScenario 1: 2 Players, 2 Keys, All in F2_P")
    players_2 = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=RoomId("F2_P"), keys=1),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=3, room=RoomId("F2_P"), keys=1),
    }
    state_2 = GameState(round=1, players=players_2)
    # Mock rooms to avoid errors if needed (though check_victory only checks players)
    
    victory_2 = _check_victory(state_2, cfg)
    print(f"Result: {victory_2}")
    if not victory_2:
        print("SUCCESS: 2 players with 2 keys did NOT win (Expected).")
    else:
        print("FAILURE: 2 players with 2 keys WON (Unexpected).")

    # Scenario 2: 4 Players, 4 Keys (1 each), All in F2_P
    # Should WIN (Keys >= 4)
    print("\nScenario 2: 4 Players, 4 Keys, All in F2_P")
    players_4 = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=RoomId("F2_P"), keys=1),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=3, room=RoomId("F2_P"), keys=1),
        PlayerId("P3"): PlayerState(player_id=PlayerId("P3"), sanity=3, room=RoomId("F2_P"), keys=1),
        PlayerId("P4"): PlayerState(player_id=PlayerId("P4"), sanity=3, room=RoomId("F2_P"), keys=1),
    }
    state_4 = GameState(round=1, players=players_4)
    
    victory_4 = _check_victory(state_4, cfg)
    print(f"Result: {victory_4}")
    if victory_4:
        print("SUCCESS: 4 players with 4 keys WON (Expected).")
    else:
        print("FAILURE: 4 players with 4 keys did NOT win (Unexpected).")

    # Scenario 3: 4 Players, 4 Keys, One NOT in F2_P
    # Should FAIL
    print("\nScenario 3: 4 Players, 4 Keys, One NOT in F2_P")
    players_4_mixed = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=RoomId("F2_P"), keys=1),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=3, room=RoomId("F2_P"), keys=1),
        PlayerId("P3"): PlayerState(player_id=PlayerId("P3"), sanity=3, room=RoomId("F2_P"), keys=1),
        PlayerId("P4"): PlayerState(player_id=PlayerId("P4"), sanity=3, room=RoomId("F1_P"), keys=1), # Wrong room
    }
    state_4_mixed = GameState(round=1, players=players_4_mixed)
    
    victory_4_mixed = _check_victory(state_4_mixed, cfg)
    print(f"Result: {victory_4_mixed}")
    if not victory_4_mixed:
        print("SUCCESS: Mixed location did NOT win (Expected).")
    else:
        print("FAILURE: Mixed location WON (Unexpected).")

if __name__ == "__main__":
    test_victory_condition()

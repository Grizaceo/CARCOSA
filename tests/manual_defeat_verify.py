import pytest
from engine.state_factory import make_game_state
from engine.types import PlayerId
from engine.config import Config
from engine.transition import _check_defeat, apply_sanity_loss
from engine.systems.king import end_of_round_checks

def test_detailed_sanity_loss_outcome():
    """Verify that sanity loss outcomes include the tracking info."""
    cfg = Config()
    
    # 1. Setup simple state
    s = make_game_state(
        round=1,
        players={"P1": {"room": "F1_R1", "sanity": -5}},
        remaining_actions={"P1": 2},
    )
    
    # Simulate applying fatal damage with a source
    # Need to simulate damage causing it to go to -5 (or stay lower)
    s.players[PlayerId("P1")].sanity = -4
    # Apply 1 damage from MONSTER
    # Note: apply_sanity_loss requires access to 's.config' usually, but here 
    # the function signature is apply_sanity_loss(s, player, amount, source)
    # We must patch s.config to exist if the function uses it
    s.config = cfg
    
    apply_sanity_loss(s, s.players[PlayerId("P1")], 1, source="MONSTER_TEST", allow_sacrifice=False)
    
    assert s.players[PlayerId("P1")].sanity == -5
    assert s.last_sanity_loss_event == "MONSTER_TEST -> P1"
    
    # 2. Check Defeat
    is_defeat = _check_defeat(s, cfg)
    assert is_defeat
    assert s.game_over
    assert s.outcome == "LOSE_ALL_MINUS5 (MONSTER_TEST -> P1)"

def test_keys_destroyed_outcome():
    """Verify detailed key loss outcome."""
    cfg = Config(KEYS_LOSE_THRESHOLD=3, KEYS_TOTAL=6)
    
    s = make_game_state(
        round=1,
        players={"P1": {"room": "F1_R1", "sanity": 3}},
        remaining_actions={"P1": 2},
    )
    
    # Destroy 4 keys -> remaining 2 (below threshold 3)
    s.keys_destroyed = 4
    
    is_defeat = _check_defeat(s, cfg)
    assert is_defeat
    assert s.outcome == "LOSE_KEYS_DESTROYED"

def test_end_round_delegation():
    """Verify _end_of_round_checks delegates correctly."""
    cfg = Config()
    s = make_game_state(round=1, players={"P1": {"room": "F1_R1", "sanity": -5}})
    s.flags = {"last_sanity_loss_event": "KING -> P1"}  # Mock manually if needed
    s.last_sanity_loss_event = "KING -> P1"
    
    end_of_round_checks(s, cfg)
    
    assert s.game_over
    assert s.outcome == "LOSE_ALL_MINUS5 (KING -> P1)"

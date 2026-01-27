import pytest
from engine.state_factory import make_game_state
from engine.types import PlayerId, CardId
from engine.transition import _resolve_card_minimal
from engine.transition import _resolve_card_minimal
from engine.config import Config

def create_simple_state():
    s = make_game_state(round=1, players={"P1": {"room": "F1_R1", "sanity": 5}}, rooms=["F1_R1"])
    return s

def test_tue_tue_sanity_wipe():
    """Test Tue Tue: Sanity >= 2 -> Sanity becomes 0."""
    s = create_simple_state()
    pid = PlayerId("P1")
    p = s.players[pid]
    p.sanity = 5
    
    # Trigger Omen
    _resolve_card_minimal(s, pid, CardId("OMEN:TUE_TUE"), Config())
    
    assert p.sanity == 0
    assert not any("TUE_TUE" in m.monster_id for m in s.monsters)

def test_tue_tue_spawn_at_low_sanity():
    """Test Tue Tue: Sanity <= 1 -> Monster Spawns."""
    s = create_simple_state()
    pid = PlayerId("P1")
    p = s.players[pid]
    p.sanity = 1
    
    # Trigger Omen
    _resolve_card_minimal(s, pid, CardId("OMEN:TUE_TUE"), Config())
    
    # Sanity remains (or doesn't change by rule, only monster spawns?)
    # Canon: "0-1 cuenta como aparición". Doesn't say "Sanity 0 AND Appearance".
    # Assuming just Spawn.
    
    assert any("MONSTER:TUE_TUE" in m.monster_id for m in s.monsters)
    # Sanity unmodified? Or rule logic?
    # Impl: if sanity >= 2: sanity=0. else: spawn.
    assert p.sanity == 1

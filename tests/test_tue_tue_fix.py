import pytest
from engine.state import GameState, RoomState, MonsterState, PlayerState, DeckState
from engine.types import RoomId, PlayerId, CardId
from engine.transition import _resolve_card_minimal
from engine.config import Config

def create_simple_state():
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=5, room=RoomId("F1_R1"))
    s = GameState(round=1, players={PlayerId("P1"): p1})
    s.rooms[RoomId("F1_R1")] = RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=[]))
    return s

def test_tue_tue_omen_should_not_spawn_monster():
    """
    Test de reproducción: Verificar que OMEN:TUE_TUE NO spawnee un token de monstruo.
    Ahora verifica que aplica efecto de cordura.
    """
    s = create_simple_state()
    pid = PlayerId("P1")
    
    # 1st revelation
    _resolve_card_minimal(s, pid, CardId("OMEN:TUE_TUE"), Config())
    
    # Check monsters list
    monster_ids = [m.monster_id for m in s.monsters]
    
    # Assertion: NO monster should be spawned
    assert "MONSTER:TUE_TUE" not in monster_ids, "ERROR: OMEN:TUE_TUE spawned a monster token!"
    
    # Check sanity loss (1st revelation -> -1)
    assert s.players[pid].sanity == 4
    assert s.tue_tue_revelations == 1

def test_tue_tue_sanity_effects():
    """
    Verificar efectos de cordura progresivos de Tue Tue.
    """
    s = create_simple_state()
    pid = PlayerId("P1")
    p = s.players[pid]
    p.sanity = 6
    p.sanity_max = 6
    
    # 1st Revelation
    _resolve_card_minimal(s, pid, CardId("OMEN:TUE_TUE"), Config())
    assert p.sanity == 5  # -1 loss
    assert s.tue_tue_revelations == 1
    
    # 2nd Revelation
    _resolve_card_minimal(s, pid, CardId("OMEN:TUE_TUE"), Config())
    assert p.sanity == 3  # -2 loss (5 - 2 = 3)
    assert s.tue_tue_revelations == 2
    
    # 3rd Revelation
    _resolve_card_minimal(s, pid, CardId("OMEN:TUE_TUE"), Config())
    assert p.sanity == -5  # Set to -5 (hardcoded in transition)
    assert s.tue_tue_revelations == 3

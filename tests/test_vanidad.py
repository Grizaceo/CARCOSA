from engine.state import GameState, PlayerState, StatusInstance
from engine.transition import apply_sanity_loss
from engine.types import PlayerId
from engine.board import corridor_id

def test_apply_sanity_loss_base():
    """Verifica pérdida básica de cordura."""
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=5, room=corridor_id(1))
    s = GameState(round=1, players={PlayerId("P1"): p1})

    apply_sanity_loss(s, p1, 1, source="TEST")
    assert p1.sanity == 4

    apply_sanity_loss(s, p1, 2, source="TEST")
    assert p1.sanity == 2

def test_apply_sanity_loss_with_vanity():
    """Verifica que VANIDAD aumenta el daño en +1."""
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=5, room=corridor_id(1))
    # Agregar estado VANIDAD
    p1.statuses.append(StatusInstance(status_id="VANIDAD", remaining_rounds=2))
    
    s = GameState(round=1, players={PlayerId("P1"): p1})

    # Daño 1 -> Total 2
    apply_sanity_loss(s, p1, 1, source="TEST")
    assert p1.sanity == 3  # 5 - (1+1) = 3

    # Daño 2 -> Total 3
    apply_sanity_loss(s, p1, 2, source="TEST")
    assert p1.sanity == 0  # 3 - (2+1) = 0

def test_apply_sanity_loss_zero():
    """Verifica que daño 0 no activa VANIDAD (ni resta nada)."""
    p1 = PlayerState(player_id=PlayerId("P1"), sanity=5, room=corridor_id(1))
    p1.statuses.append(StatusInstance(status_id="VANIDAD", remaining_rounds=2))
    s = GameState(round=1, players={PlayerId("P1"): p1})

    apply_sanity_loss(s, p1, 0, source="TEST")
    assert p1.sanity == 5

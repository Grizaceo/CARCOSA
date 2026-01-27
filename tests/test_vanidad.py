from engine.state import StatusInstance
from engine.state_factory import make_game_state
from engine.transition import apply_sanity_loss
from engine.types import PlayerId
from engine.board import corridor_id

def test_apply_sanity_loss_base():
    """Verifica pérdida básica de cordura."""
    room = str(corridor_id(1))
    s = make_game_state(players={"P1": {"room": room, "sanity": 5}}, rooms=[room])
    p1 = s.players[PlayerId("P1")]

    apply_sanity_loss(s, p1, 1, source="TEST")
    assert p1.sanity == 4

    apply_sanity_loss(s, p1, 2, source="TEST")
    assert p1.sanity == 2

def test_apply_sanity_loss_with_vanity():
    """Verifica que VANIDAD aumenta el daño en +1."""
    room = str(corridor_id(1))
    s = make_game_state(players={"P1": {"room": room, "sanity": 5}}, rooms=[room])
    p1 = s.players[PlayerId("P1")]
    # Agregar estado VANIDAD
    p1.statuses.append(StatusInstance(status_id="VANIDAD", remaining_rounds=2))

    # Daño 1 -> Total 2
    apply_sanity_loss(s, p1, 1, source="TEST")
    assert p1.sanity == 3  # 5 - (1+1) = 3

    # Daño 2 -> Total 3
    apply_sanity_loss(s, p1, 2, source="TEST")
    assert p1.sanity == 0  # 3 - (2+1) = 0

def test_apply_sanity_loss_zero():
    """Verifica que daño 0 no activa VANIDAD (ni resta nada)."""
    room = str(corridor_id(1))
    s = make_game_state(players={"P1": {"room": room, "sanity": 5}}, rooms=[room])
    p1 = s.players[PlayerId("P1")]
    p1.statuses.append(StatusInstance(status_id="VANIDAD", remaining_rounds=2))

    apply_sanity_loss(s, p1, 0, source="TEST")
    assert p1.sanity == 5

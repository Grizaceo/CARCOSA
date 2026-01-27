"""
Test de integración: B1 ILUMINADO en el flujo de turno
"""
import pytest
from engine.state import StatusInstance
from engine.state_factory import make_game_state
from engine.types import PlayerId
from engine.transition import _start_new_round
from engine.config import Config


def test_illuminated_gives_three_actions_in_turn():
    """
    Verificar que ILLUMINATED otorga 3 acciones (2 base + 1 por ILUMINADO)
    en el cálculo al inicio de la ronda.
    """
    rooms = ["F1_R1", "F1_P"]
    players = {
        "P1": {"room": "F1_R1", "sanity": 5, "sanity_max": 5},
        "P2": {"room": "F1_R1", "sanity": 5, "sanity_max": 5},
    }
    s = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=3,
        turn_pos=0,
        remaining_actions={"P1": 2, "P2": 2},
        turn_order=["P1", "P2"],
    )
    s.flags = {}
    
    cfg = Config()
    
    # Agregar ILLUMINATED a P1
    p1 = s.players[PlayerId("P1")]
    p1.statuses.append(StatusInstance(status_id="ILLUMINATED", remaining_rounds=2))
    
    # Simular inicio de ronda (donde se recalculan acciones)
    _start_new_round(s, cfg)
    
    # Verificar: P1 debe tener 3 acciones
    assert s.remaining_actions[PlayerId("P1")] == 3, "P1 con ILLUMINATED debe tener 3 acciones (2 + 1)"
    assert s.remaining_actions[PlayerId("P2")] == 2, "P2 sin ILLUMINATED debe tener 2 acciones"

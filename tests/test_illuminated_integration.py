"""
Test de integración: B1 ILUMINADO en el flujo de turno
"""
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState, StatusInstance
from engine.types import PlayerId, RoomId
from engine.transition import step, _start_new_round
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.config import Config


def test_illuminated_gives_three_actions_in_turn():
    """
    Verificar que ILLUMINATED otorga 3 acciones (2 base + 1 por ILUMINADO)
    en el cálculo al inicio de la ronda.
    """
    rooms = {
        RoomId("F1_R1"): RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=[])),
        RoomId("F1_P"): RoomState(room_id=RoomId("F1_P"), deck=DeckState(cards=[])),
    }
    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=5, room=RoomId("F1_R1"), sanity_max=5),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=5, room=RoomId("F1_R1"), sanity_max=5),
    }
    s = GameState(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=3,
        turn_pos=0,
        remaining_actions={PlayerId("P1"): 2, PlayerId("P2"): 2},
        turn_order=[PlayerId("P1"), PlayerId("P2")],
        flags={},
    )
    
    cfg = Config()
    
    # Agregar ILLUMINATED a P1
    p1 = s.players[PlayerId("P1")]
    p1.statuses.append(StatusInstance(status_id="ILLUMINATED", remaining_rounds=2))
    
    # Simular inicio de ronda (donde se recalculan acciones)
    _start_new_round(s, cfg)
    
    # Verificar: P1 debe tener 3 acciones
    assert s.remaining_actions[PlayerId("P1")] == 3, "P1 con ILLUMINATED debe tener 3 acciones (2 + 1)"
    assert s.remaining_actions[PlayerId("P2")] == 2, "P2 sin ILLUMINATED debe tener 2 acciones"

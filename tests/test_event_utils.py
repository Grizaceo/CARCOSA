"""
Tests para funciones de utilidad de eventos (FASE 0.2)
"""
import pytest
from engine.state import StatusInstance
from engine.state_factory import make_game_state
from engine.types import PlayerId, RoomId
from engine.effects.event_utils import (
    swap_positions,
    move_player_to_room,
    remove_all_statuses,
    remove_status,
    add_status,
    get_player_by_turn_offset,
    get_players_in_floor,
    invert_sanity
)


def setup_basic_state():
    """Estado básico con 2 jugadores para tests."""
    rooms = ["F1_R1", "F1_R2", "F2_R1"]
    players = {
        "P1": {"room": "F1_R1", "sanity": 5, "sanity_max": 10, "keys": 0, "objects": []},
        "P2": {"room": "F1_R2", "sanity": 3, "sanity_max": 10, "keys": 0, "objects": []},
    }
    s = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=3,
        turn_pos=0,
        remaining_actions={"P1": 2},
        turn_order=["P1", "P2"],
    )
    s.flags = {}
    return s


def test_swap_positions():
    """Swap intercambia posiciones correctamente"""
    s = setup_basic_state()
    p1 = s.players[PlayerId("P1")]
    p2 = s.players[PlayerId("P2")]

    initial_p1_room = p1.room
    initial_p2_room = p2.room

    # Swap
    swap_positions(s, PlayerId("P1"), PlayerId("P2"))

    # Verificar intercambio
    assert p1.room == initial_p2_room
    assert p2.room == initial_p1_room


def test_move_player_to_room():
    """move_player_to_room mueve jugador correctamente"""
    s = setup_basic_state()
    p1 = s.players[PlayerId("P1")]

    assert p1.room == RoomId("F1_R1")

    # Mover a F2_R1
    move_player_to_room(s, PlayerId("P1"), RoomId("F2_R1"))

    assert p1.room == RoomId("F2_R1")


def test_remove_all_statuses():
    """remove_all_statuses elimina todos los estados"""
    s = setup_basic_state()
    p1 = s.players[PlayerId("P1")]

    # Agregar varios estados
    p1.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=2))
    p1.statuses.append(StatusInstance(status_id="ILLUMINATED", remaining_rounds=1))
    assert len(p1.statuses) == 2

    # Remover todos
    remove_all_statuses(p1)

    assert len(p1.statuses) == 0


def test_remove_status():
    """remove_status elimina estado específico"""
    s = setup_basic_state()
    p1 = s.players[PlayerId("P1")]

    # Agregar estados
    p1.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=2))
    p1.statuses.append(StatusInstance(status_id="ILLUMINATED", remaining_rounds=1))
    assert len(p1.statuses) == 2

    # Remover TRAPPED
    result = remove_status(p1, "TRAPPED")

    assert result == True
    assert len(p1.statuses) == 1
    assert p1.statuses[0].status_id == "ILLUMINATED"

    # Intentar remover algo que no existe
    result2 = remove_status(p1, "NONEXISTENT")
    assert result2 == False
    assert len(p1.statuses) == 1


def test_add_status():
    """add_status agrega estado correctamente"""
    s = setup_basic_state()
    p1 = s.players[PlayerId("P1")]

    assert len(p1.statuses) == 0

    # Agregar estado
    add_status(p1, "SANGRADO", duration=2)

    assert len(p1.statuses) == 1
    assert p1.statuses[0].status_id == "SANGRADO"
    assert p1.statuses[0].remaining_rounds == 2


def test_get_player_by_turn_offset():
    """get_player_by_turn_offset obtiene jugador correcto"""
    s = setup_basic_state()

    # P1 está en posición 0, siguiente es P2
    next_player = get_player_by_turn_offset(s, PlayerId("P1"), 1)
    assert next_player == PlayerId("P2")

    # P2 está en posición 1, siguiente (wrap) es P1
    next_player2 = get_player_by_turn_offset(s, PlayerId("P2"), 1)
    assert next_player2 == PlayerId("P1")

    # P1, anterior (wrap) es P2
    prev_player = get_player_by_turn_offset(s, PlayerId("P1"), -1)
    assert prev_player == PlayerId("P2")


def test_get_players_in_floor():
    """get_players_in_floor retorna jugadores en piso correcto"""
    s = setup_basic_state()

    # Ambos jugadores en piso 1
    players_f1 = get_players_in_floor(s, 1)
    assert len(players_f1) == 2
    assert PlayerId("P1") in players_f1
    assert PlayerId("P2") in players_f1

    # Piso 2 vacío
    players_f2 = get_players_in_floor(s, 2)
    assert len(players_f2) == 0

    # Mover P2 a F2_R1
    s.players[PlayerId("P2")].room = RoomId("F2_R1")

    # Ahora piso 1 tiene 1 jugador
    players_f1_after = get_players_in_floor(s, 1)
    assert len(players_f1_after) == 1
    assert PlayerId("P1") in players_f1_after

    # Y piso 2 tiene 1 jugador
    players_f2_after = get_players_in_floor(s, 2)
    assert len(players_f2_after) == 1
    assert PlayerId("P2") in players_f2_after


def test_invert_sanity():
    """invert_sanity invierte cordura correctamente"""
    s = setup_basic_state()
    p1 = s.players[PlayerId("P1")]

    # Cordura positiva
    p1.sanity = 3
    invert_sanity(p1)
    assert p1.sanity == -3

    # Cordura negativa
    p1.sanity = -2
    invert_sanity(p1)
    assert p1.sanity == 2

    # Cordura 0
    p1.sanity = 0
    invert_sanity(p1)
    assert p1.sanity == 0

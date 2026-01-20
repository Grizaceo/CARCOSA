"""
Tests para el modelo de datos de habitaciones especiales (P1 - FASE 1.5.0)
"""
import pytest
from engine.state import RoomState, DeckState
from engine.types import RoomId, CardId


def test_room_state_has_special_fields():
    """RoomState tiene campos para habitaciones especiales"""
    room = RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=[]))

    assert room.special_card_id is None
    assert room.special_revealed is False
    assert room.special_destroyed is False
    assert room.special_activation_count == 0


def test_room_state_special_card_id_can_be_set():
    """Se puede asignar un ID de habitación especial"""
    room = RoomState(
        room_id=RoomId("F1_R1"),
        deck=DeckState(cards=[]),
        special_card_id="CAMARA_LETAL"
    )

    assert room.special_card_id == "CAMARA_LETAL"
    assert room.special_revealed is False
    assert room.special_destroyed is False


def test_room_state_special_revealed_flag():
    """Se puede marcar una habitación especial como revelada"""
    room = RoomState(
        room_id=RoomId("F1_R1"),
        deck=DeckState(cards=[]),
        special_card_id="PEEK"
    )

    # Inicialmente no revelada
    assert room.special_revealed is False

    # Revelar
    room.special_revealed = True
    assert room.special_revealed is True


def test_room_state_special_destroyed_flag():
    """Se puede marcar una habitación especial como destruida"""
    room = RoomState(
        room_id=RoomId("F1_R1"),
        deck=DeckState(cards=[]),
        special_card_id="ARMERY"
    )

    # Inicialmente no destruida
    assert room.special_destroyed is False

    # Destruir (por monstruo)
    room.special_destroyed = True
    assert room.special_destroyed is True


def test_room_state_activation_count():
    """Contador de activaciones funciona correctamente"""
    room = RoomState(
        room_id=RoomId("F1_R1"),
        deck=DeckState(cards=[]),
        special_card_id="SALON_BELLEZA"
    )

    # Inicialmente 0 activaciones
    assert room.special_activation_count == 0

    # Primera activación
    room.special_activation_count += 1
    assert room.special_activation_count == 1

    # Segunda activación
    room.special_activation_count += 1
    assert room.special_activation_count == 2

    # Tercera activación (Salón de Belleza sella en la 3ra)
    room.special_activation_count += 1
    assert room.special_activation_count == 3

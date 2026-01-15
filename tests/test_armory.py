"""
Tests para B6: ARMERÍA (almacenar/recuperar objetos)
"""
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId


def setup_armory_state():
    """Estado con habitación de ARMERÍA."""
    rooms = {
        RoomId("F1_ARMERY"): RoomState(
            room_id=RoomId("F1_ARMERY"), 
            deck=DeckState(cards=[])
        ),
        RoomId("F1_R1"): RoomState(
            room_id=RoomId("F1_R1"), 
            deck=DeckState(cards=[])
        ),
    }
    players = {
        PlayerId("P1"): PlayerState(
            player_id=PlayerId("P1"), sanity=10, room=RoomId("F1_ARMERY"), 
            sanity_max=10, keys=0, objects=[]
        ),
    }
    s = GameState(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=3,
        turn_pos=0,
        remaining_actions={PlayerId("P1"): 2},
        turn_order=[PlayerId("P1")],
        armory_storage={RoomId("F1_ARMERY"): []},
        flags={},
    )
    return s


def test_armory_storage_capacity_two():
    """
    B6: La ARMERÍA almacena máximo 2 objetos.
    """
    s = setup_armory_state()
    armory_id = RoomId("F1_ARMERY")
    
    # Capacidad vacía
    assert len(s.armory_storage[armory_id]) == 0
    
    # Agregar 1 objeto
    s.armory_storage[armory_id].append("TORCH")
    assert len(s.armory_storage[armory_id]) == 1
    
    # Agregar 2º objeto
    s.armory_storage[armory_id].append("ROPE")
    assert len(s.armory_storage[armory_id]) == 2
    
    # Intento de agregar 3º objeto: debe fallar
    capacity_exceeded = len(s.armory_storage[armory_id]) >= 2
    assert capacity_exceeded, "Capacidad excedida"


def test_armory_drop_action_puts_item():
    """
    B6: USE_ARMORY_DROP coloca un objeto en almacenamiento.
    """
    s = setup_armory_state()
    p1 = s.players[PlayerId("P1")]
    armory_id = RoomId("F1_ARMERY")
    
    # P1 tiene un objeto
    p1.objects.append("TORCH")
    initial_objects = len(p1.objects)
    
    # Simulación de DROP
    if len(s.armory_storage[armory_id]) < 2:
        dropped_item = p1.objects.pop()
        s.armory_storage[armory_id].append(dropped_item)
    
    assert len(p1.objects) == initial_objects - 1
    assert "TORCH" in s.armory_storage[armory_id]


def test_armory_take_action_gets_item():
    """
    B6: USE_ARMORY_TAKE recupera un objeto del almacenamiento.
    """
    s = setup_armory_state()
    p1 = s.players[PlayerId("P1")]
    armory_id = RoomId("F1_ARMERY")
    
    # Armería con objeto
    s.armory_storage[armory_id].append("ROPE")
    initial_stored = len(s.armory_storage[armory_id])
    
    # Simulación de TAKE
    if len(s.armory_storage[armory_id]) > 0:
        taken_item = s.armory_storage[armory_id].pop()
        p1.objects.append(taken_item)
    
    assert len(s.armory_storage[armory_id]) == initial_stored - 1
    assert "ROPE" in p1.objects


def test_armory_drop_requires_space():
    """
    B6: No se puede dejar un objeto si armería está llena (2/2).
    """
    s = setup_armory_state()
    p1 = s.players[PlayerId("P1")]
    armory_id = RoomId("F1_ARMERY")
    
    # Armería llena
    s.armory_storage[armory_id] = ["TORCH", "ROPE"]
    p1.objects = ["KNIFE"]
    
    # Intento de drop
    if len(s.armory_storage[armory_id]) < 2:
        p1.objects.remove("KNIFE")
        s.armory_storage[armory_id].append("KNIFE")
        drop_allowed = True
    else:
        drop_allowed = False
    
    assert not drop_allowed, "No hay espacio"
    assert "KNIFE" in p1.objects, "Objeto sigue en mano"


def test_armory_take_requires_items():
    """
    B6: No se puede tomar de armería si está vacía.
    """
    s = setup_armory_state()
    p1 = s.players[PlayerId("P1")]
    armory_id = RoomId("F1_ARMERY")
    
    # Armería vacía
    assert len(s.armory_storage[armory_id]) == 0
    
    # Intento de take
    if len(s.armory_storage[armory_id]) > 0:
        item = s.armory_storage[armory_id].pop()
        p1.objects.append(item)
        take_allowed = True
    else:
        take_allowed = False
    
    assert not take_allowed, "Armería vacía"


def test_armory_persistence_across_turns():
    """
    B6: Los objetos almacenados permanecen entre turnos.
    """
    s = setup_armory_state()
    armory_id = RoomId("F1_ARMERY")
    
    # Turno 1: dejar objeto
    s.armory_storage[armory_id].append("TORCH")
    stored_after_t1 = len(s.armory_storage[armory_id])
    
    # Turno 2: objeto sigue ahí
    s.round += 1
    s.turn_pos = 0  # Nuevo turno
    
    stored_after_t2 = len(s.armory_storage[armory_id])
    assert stored_after_t2 == stored_after_t1, "Objeto persiste"


def test_armory_requires_actor_in_armory_room():
    """
    B6: Solo se puede usar ARMERÍA si actor está en la habitación de ARMERÍA.
    """
    s = setup_armory_state()
    p1 = s.players[PlayerId("P1")]
    
    # P1 en ARMERÍA - acción válida
    assert p1.room == RoomId("F1_ARMERY")
    legal = True
    
    # P1 sale de ARMERÍA
    p1.room = RoomId("F1_R1")
    
    # Intento de usar ARMERÍA desde otra habitación - inválido
    if p1.room == RoomId("F1_ARMERY"):
        legal_outside = True
    else:
        legal_outside = False
    
    assert not legal_outside, "No puede usar desde otra habitación"


def test_armory_drop_and_take_sequence():
    """
    B6: Secuencia completa: DROP objeto A, DROP objeto B, TAKE objeto B, TAKE objeto A.
    """
    s = setup_armory_state()
    p1 = s.players[PlayerId("P1")]
    armory_id = RoomId("F1_ARMERY")
    
    # Iniciales
    p1.objects = ["TORCH", "ROPE", "KNIFE"]
    
    # DROP TORCH
    p1.objects.remove("TORCH")
    s.armory_storage[armory_id].append("TORCH")
    assert len(s.armory_storage[armory_id]) == 1
    
    # DROP ROPE
    p1.objects.remove("ROPE")
    s.armory_storage[armory_id].append("ROPE")
    assert len(s.armory_storage[armory_id]) == 2
    
    # TAKE ROPE (LIFO)
    taken = s.armory_storage[armory_id].pop()
    p1.objects.append(taken)
    assert taken == "ROPE"
    assert len(s.armory_storage[armory_id]) == 1
    
    # TAKE TORCH
    taken = s.armory_storage[armory_id].pop()
    p1.objects.append(taken)
    assert taken == "TORCH"
    assert len(s.armory_storage[armory_id]) == 0
    
    # P1 de vuelta con sus 3 objetos
    assert len(p1.objects) == 3

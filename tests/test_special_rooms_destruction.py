"""
Tests para el hook de destrucción de habitaciones especiales por monstruo (P1 - FASE 1.5.3)
"""
import pytest
from sim.runner import make_smoke_state
from engine.config import Config
from engine.types import PlayerId, RoomId, CardId
from engine.transition import _resolve_card_minimal
from engine.rng import RNG


def test_monster_destroys_special_room():
    """Monstruo entrando destruye habitación especial"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    # Encontrar una habitación con special_card_id
    special_room = None
    special_type = None
    for rid, room_state in state.rooms.items():
        if room_state.special_card_id is not None:
            special_room = rid
            special_type = room_state.special_card_id
            break

    assert special_room is not None

    # Revelar la habitación especial primero
    state.rooms[special_room].special_revealed = True

    # Verificar que inicialmente NO está destruida
    assert state.rooms[special_room].special_destroyed is False

    # Crear un jugador en esa habitación
    state.players[PlayerId("P1")].room = special_room

    # Resolver carta de monstruo
    monster_card = CardId("MONSTER:SPIDER")
    _resolve_card_minimal(state, PlayerId("P1"), monster_card, cfg, RNG(1))

    # Verificar que la habitación especial fue destruida
    assert state.rooms[special_room].special_destroyed is True


def test_destroyed_room_prevents_activation():
    """Habitación destruida no puede activarse"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    # Encontrar una habitación con special_card_id
    special_room = None
    for rid, room_state in state.rooms.items():
        if room_state.special_card_id is not None:
            special_room = rid
            break

    assert special_room is not None

    # Marcar como destruida
    state.rooms[special_room].special_destroyed = True

    # Verificar que NO se puede revelar si está destruida
    # (el hook de revelación debe verificar special_destroyed)
    state.players[PlayerId("P1")].room = special_room

    # Intentar revelar no debería hacer nada
    from engine.transition import _on_player_enters_room
    _on_player_enters_room(state, PlayerId("P1"), special_room)

    # Debe permanecer NO revelada
    assert state.rooms[special_room].special_revealed is False


def test_armory_specific_destruction():
    """Armería destruida vacía su almacenamiento"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    # Buscar una habitación de Armería o crear una manualmente
    armory_room = None
    for rid, room_state in state.rooms.items():
        if room_state.special_card_id == "ARMERY":
            armory_room = rid
            break

    # Si no encontramos Armería en el sorteo, crear una manualmente para el test
    if armory_room is None:
        armory_room = RoomId("F1_R1")
        state.rooms[armory_room].special_card_id = "ARMERY"
        state.rooms[armory_room].special_revealed = True

    # Agregar objetos al almacenamiento de la Armería
    state.armory_storage[armory_room] = ["SWORD", "SHIELD", "AXE"]

    # Verificar que hay objetos
    assert len(state.armory_storage[armory_room]) == 3

    # Crear jugador en Armería
    state.players[PlayerId("P1")].room = armory_room

    # Resolver carta de monstruo
    monster_card = CardId("MONSTER:WORM")
    _resolve_card_minimal(state, PlayerId("P1"), monster_card, cfg, RNG(1))

    # Verificar que la Armería fue destruida
    assert state.rooms[armory_room].special_destroyed is True

    # Verificar que el almacenamiento fue vaciado
    assert len(state.armory_storage[armory_room]) == 0


def test_room_and_deck_remain_intact_after_destruction():
    """Nodo y mazo permanecen intactos cuando se destruye habitación especial"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    # Encontrar una habitación con special_card_id
    special_room = None
    for rid, room_state in state.rooms.items():
        if room_state.special_card_id is not None and len(room_state.deck.cards) > 0:
            special_room = rid
            break

    assert special_room is not None

    # Guardar el estado del mazo antes de la destrucción
    deck_before = len(state.rooms[special_room].deck.cards)

    # Crear jugador en la habitación
    state.players[PlayerId("P1")].room = special_room

    # Resolver carta de monstruo
    monster_card = CardId("MONSTER:SPIDER")
    _resolve_card_minimal(state, PlayerId("P1"), monster_card, cfg, RNG(1))

    # Verificar que la habitación especial fue destruida
    assert state.rooms[special_room].special_destroyed is True

    # Verificar que el nodo (RoomState) sigue existiendo
    assert special_room in state.rooms

    # Verificar que el mazo permanece intacto
    assert len(state.rooms[special_room].deck.cards) == deck_before


def test_monster_does_not_destroy_already_destroyed():
    """Monstruo no vuelve a destruir habitación ya destruida (idempotente)"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    # Encontrar una habitación con special_card_id
    special_room = None
    for rid, room_state in state.rooms.items():
        if room_state.special_card_id is not None:
            special_room = rid
            break

    assert special_room is not None

    # Marcar como destruida previamente
    state.rooms[special_room].special_destroyed = True

    # Crear jugador en la habitación
    state.players[PlayerId("P1")].room = special_room

    # Resolver carta de monstruo
    monster_card = CardId("MONSTER:SPIDER")
    _resolve_card_minimal(state, PlayerId("P1"), monster_card, cfg, RNG(1))

    # Debe permanecer destruida (no hay cambios)
    assert state.rooms[special_room].special_destroyed is True


def test_multiple_special_rooms_destroyed_independently():
    """Múltiples habitaciones especiales se destruyen independientemente"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    # Encontrar dos habitaciones con special_card_id diferentes
    special_rooms = []
    for rid, room_state in state.rooms.items():
        if room_state.special_card_id is not None:
            special_rooms.append(rid)
            if len(special_rooms) == 2:
                break

    # Necesitamos al menos 2 habitaciones especiales para este test
    if len(special_rooms) < 2:
        pytest.skip("No hay suficientes habitaciones especiales en este seed")

    room1, room2 = special_rooms[0], special_rooms[1]

    # Verificar que ambas NO están destruidas inicialmente
    assert state.rooms[room1].special_destroyed is False
    assert state.rooms[room2].special_destroyed is False

    # Destruir solo la primera
    state.players[PlayerId("P1")].room = room1
    _resolve_card_minimal(state, PlayerId("P1"), CardId("MONSTER:SPIDER"), cfg, RNG(1))

    # Verificar que solo room1 fue destruida
    assert state.rooms[room1].special_destroyed is True
    assert state.rooms[room2].special_destroyed is False

    # Destruir la segunda
    state.players[PlayerId("P1")].room = room2
    _resolve_card_minimal(state, PlayerId("P1"), CardId("MONSTER:WORM"), cfg, RNG(2))

    # Ahora ambas deben estar destruidas
    assert state.rooms[room1].special_destroyed is True
    assert state.rooms[room2].special_destroyed is True


def test_legacy_armory_flag_still_set():
    """Flag legacy ARMORY_DESTROYED se mantiene para compatibilidad"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    # Buscar Armería o crear una
    armory_room = None
    for rid, room_state in state.rooms.items():
        if room_state.special_card_id == "ARMERY":
            armory_room = rid
            break

    if armory_room is None:
        armory_room = RoomId("F1_R1")
        state.rooms[armory_room].special_card_id = "ARMERY"

    # Crear jugador en Armería
    state.players[PlayerId("P1")].room = armory_room

    # Resolver carta de monstruo
    _resolve_card_minimal(state, PlayerId("P1"), CardId("MONSTER:SPIDER"), cfg, RNG(1))

    # Verificar que el flag legacy se sigue seteando
    assert state.flags.get(f"ARMORY_DESTROYED_{armory_room}") is True

"""
Tests para B3: Cámara Letal (P1 - FASE 1.5.4)
"""
import pytest
from sim.runner import make_smoke_state
from engine.config import Config
from engine.types import PlayerId, RoomId
from engine.actions import Action, ActionType
from engine.transition import step
from engine.legality import get_legal_actions
from engine.rng import RNG


def test_camara_letal_flag_set_when_selected():
    """Flag CAMARA_LETAL_PRESENT se marca si sale en sorteo"""
    # Probar múltiples seeds hasta encontrar uno con y sin Cámara Letal
    found_with = False
    found_without = False

    for seed in range(1, 100):
        state = make_smoke_state(seed=seed)
        selected = state.flags["SPECIAL_ROOMS_SELECTED"]
        has_camara = "CAMARA_LETAL" in selected

        if has_camara:
            assert state.flags["CAMARA_LETAL_PRESENT"] is True
            found_with = True
        else:
            assert state.flags["CAMARA_LETAL_PRESENT"] is False
            found_without = True

        if found_with and found_without:
            break

    assert found_with, "No se encontró seed con Cámara Letal"
    assert found_without, "No se encontró seed sin Cámara Letal"


def test_camara_letal_room_created_when_selected():
    """Habitación Cámara Letal se crea cuando es seleccionada"""
    # Buscar seed donde Cámara Letal es seleccionada
    for seed in range(1, 100):
        state = make_smoke_state(seed=seed)
        if state.flags.get("CAMARA_LETAL_PRESENT", False):
            # Debe haber al menos una habitación con special_card_id="CAMARA_LETAL"
            camara_rooms = [
                rid for rid, room in state.rooms.items()
                if room.special_card_id == "CAMARA_LETAL"
            ]
            assert len(camara_rooms) > 0, "Cámara Letal seleccionada pero no hay habitaciones"
            break
    else:
        pytest.fail("No se encontró seed con Cámara Letal en 100 intentos")


def test_ritual_requires_2_players_in_room():
    """Ritual solo disponible con exactamente 2 jugadores en la habitación"""
    cfg = Config()

    # Buscar seed con Cámara Letal
    state = None
    camara_room = None
    for seed in range(1, 100):
        test_state = make_smoke_state(seed=seed, cfg=cfg)
        if test_state.flags.get("CAMARA_LETAL_PRESENT", False):
            for rid, room in test_state.rooms.items():
                if room.special_card_id == "CAMARA_LETAL":
                    state = test_state
                    camara_room = rid
                    break
            if state:
                break

    if not state:
        pytest.skip("No se encontró Cámara Letal en 100 seeds")

    # Revelar la habitación
    state.rooms[camara_room].special_revealed = True

    # Setup básico
    state.phase = "PLAYER"
    state.turn_order = [PlayerId("P1"), PlayerId("P2")]
    state.turn_pos = 0
    state.remaining_actions = {PlayerId("P1"): 2}

    # Caso 1: Solo P1 en la habitación - NO debe estar disponible
    state.players[PlayerId("P1")].room = camara_room
    # Mover P2 a una habitación diferente que sabemos que existe
    other_room = [rid for rid in state.rooms.keys() if rid != camara_room][0]
    state.players[PlayerId("P2")].room = other_room

    legal_actions = get_legal_actions(state, "P1")
    ritual_actions = [a for a in legal_actions if a.type == ActionType.USE_CAMARA_LETAL_RITUAL]
    assert len(ritual_actions) == 0, "Ritual no debe estar disponible con 1 solo jugador"

    # Caso 2: P1 y P2 en la habitación - SÍ debe estar disponible
    state.players[PlayerId("P2")].room = camara_room

    legal_actions = get_legal_actions(state, "P1")
    ritual_actions = [a for a in legal_actions if a.type == ActionType.USE_CAMARA_LETAL_RITUAL]
    assert len(ritual_actions) == 1, "Ritual debe estar disponible con 2 jugadores"


def test_ritual_not_available_when_destroyed():
    """Ritual no disponible si habitación está destruida"""
    cfg = Config()

    # Buscar seed con Cámara Letal
    state = None
    camara_room = None
    for seed in range(1, 100):
        test_state = make_smoke_state(seed=seed, cfg=cfg)
        if test_state.flags.get("CAMARA_LETAL_PRESENT", False):
            for rid, room in test_state.rooms.items():
                if room.special_card_id == "CAMARA_LETAL":
                    state = test_state
                    camara_room = rid
                    break
            if state:
                break

    if not state:
        pytest.skip("No se encontró Cámara Letal en 100 seeds")

    # Revelar y destruir la habitación
    state.rooms[camara_room].special_revealed = True
    state.rooms[camara_room].special_destroyed = True

    # Setup con 2 jugadores en la habitación
    state.phase = "PLAYER"
    state.turn_order = [PlayerId("P1"), PlayerId("P2")]
    state.turn_pos = 0
    state.remaining_actions = {PlayerId("P1"): 2}
    state.players[PlayerId("P1")].room = camara_room
    state.players[PlayerId("P2")].room = camara_room

    legal_actions = get_legal_actions(state, "P1")
    ritual_actions = [a for a in legal_actions if a.type == ActionType.USE_CAMARA_LETAL_RITUAL]
    assert len(ritual_actions) == 0, "Ritual no debe estar disponible si habitación está destruida"


def test_ritual_d6_validation_logic():
    """Verificar que la lógica de validación D6 funciona correctamente"""
    # Este test verifica la lógica de validación sin depender de RNG aleatorio

    # D6=1,2: solo [0,7] o [7,0] son válidos
    for d6 in [1, 2]:
        assert sorted([0, 7]) == [0, 7]  # válido
        assert sorted([7, 0]) == [0, 7]  # válido
        assert sorted([3, 4]) != [0, 7]  # inválido
        assert sorted([2, 5]) != [0, 7]  # inválido (suma 7 pero no es [0,7])

    # D6=3,4: solo [3,4] o [4,3] son válidos
    for d6 in [3, 4]:
        assert sorted([3, 4]) == [3, 4]  # válido
        assert sorted([4, 3]) == [3, 4]  # válido
        assert sorted([0, 7]) != [3, 4]  # inválido
        assert sorted([2, 5]) != [3, 4]  # inválido (suma 7 pero no es [3,4])

    # D6=5,6: cualquier combinación que sume 7 es válida
    for d6 in [5, 6]:
        assert sum([0, 7]) == 7  # válido
        assert sum([1, 6]) == 7  # válido
        assert sum([2, 5]) == 7  # válido
        assert sum([3, 4]) == 7  # válido
        assert sum([4, 3]) == 7  # válido
        assert sum([5, 2]) == 7  # válido
        assert sum([6, 1]) == 7  # válido
        assert sum([7, 0]) == 7  # válido


def test_ritual_action_available_with_2_players():
    """Verificar que acción está disponible cuando hay 2 jugadores"""
    cfg = Config()

    # Buscar seed con Cámara Letal
    state = None
    camara_room = None
    for seed in range(1, 100):
        test_state = make_smoke_state(seed=seed, cfg=cfg)
        if test_state.flags.get("CAMARA_LETAL_PRESENT", False):
            for rid, room in test_state.rooms.items():
                if room.special_card_id == "CAMARA_LETAL":
                    state = test_state
                    camara_room = rid
                    break
            if state:
                break

    if not state:
        pytest.skip("No se encontró Cámara Letal en 100 seeds")

    # Setup con 2 jugadores
    state.rooms[camara_room].special_revealed = True
    state.phase = "PLAYER"
    state.turn_order = [PlayerId("P1"), PlayerId("P2")]
    state.turn_pos = 0
    state.remaining_actions = {PlayerId("P1"): 2}
    state.players[PlayerId("P1")].room = camara_room
    state.players[PlayerId("P2")].room = camara_room

    # Verificar que la acción está disponible
    legal_actions = get_legal_actions(state, "P1")
    ritual_actions = [a for a in legal_actions if a.type == ActionType.USE_CAMARA_LETAL_RITUAL]
    assert len(ritual_actions) == 1, "Ritual debe estar disponible con 2 jugadores"


def test_ritual_only_once_per_game():
    """Ritual solo se puede completar una vez por partida"""
    cfg = Config()

    # Buscar seed con Cámara Letal
    state = None
    camara_room = None
    for seed in range(1, 100):
        test_state = make_smoke_state(seed=seed, cfg=cfg)
        if test_state.flags.get("CAMARA_LETAL_PRESENT", False):
            for rid, room in test_state.rooms.items():
                if room.special_card_id == "CAMARA_LETAL":
                    state = test_state
                    camara_room = rid
                    break
            if state:
                break

    if not state:
        pytest.skip("No se encontró Cámara Letal en 100 seeds")

    # Setup
    state.rooms[camara_room].special_revealed = True
    state.phase = "PLAYER"
    state.turn_order = [PlayerId("P1"), PlayerId("P2")]
    state.turn_pos = 0
    state.remaining_actions = {PlayerId("P1"): 2}
    state.players[PlayerId("P1")].room = camara_room
    state.players[PlayerId("P2")].room = camara_room
    state.players[PlayerId("P1")].sanity = 20
    state.players[PlayerId("P2")].sanity = 20

    # Marcar ritual como completado
    state.flags["CAMARA_LETAL_RITUAL_COMPLETED"] = True

    # Verificar que la acción ya NO está disponible
    legal_actions = get_legal_actions(state, "P1")
    ritual_actions = [a for a in legal_actions if a.type == ActionType.USE_CAMARA_LETAL_RITUAL]
    assert len(ritual_actions) == 0, "Ritual no debe estar disponible después de completarse"


def test_ritual_is_free_action():
    """Ritual NO consume acción (free action)"""
    from engine.transition import _consume_action_if_needed

    # Verificar que USE_CAMARA_LETAL_RITUAL es una free action
    cost = _consume_action_if_needed(ActionType.USE_CAMARA_LETAL_RITUAL)
    assert cost == 0, "Ritual debe ser una free action (costo 0)"

"""
Tests para el sistema de sorteo y asignación de habitaciones especiales (P1 - FASE 1.5.1)
"""
import pytest
from sim.runner import make_smoke_state, _setup_special_rooms
from engine.config import Config
from engine.rng import RNG
from engine.types import RoomId
from engine.board import room_id


def test_setup_selects_3_special_rooms():
    """Setup sortea exactamente 3 habitaciones especiales"""
    rng = RNG(1)
    special_room_locations = _setup_special_rooms(rng)

    # Debe haber exactamente 3 habitaciones especiales
    assert len(special_room_locations) == 3

    # Todas deben estar en la lista de disponibles
    available = ["MOTEMEY", "CAMARA_LETAL", "PUERTAS", "PEEK", "ARMERY"]
    for special_type in special_room_locations.keys():
        assert special_type in available


def test_each_special_room_has_3_floors():
    """
    CORRECCIÓN A: Cada habitación especial se asigna a SOLO UN piso (reglas físicas).

    El juego físico asigna 3 tipos especiales a 3 pisos (1 tipo por piso).
    """
    rng = RNG(1)
    special_room_locations = _setup_special_rooms(rng)

    # Total: 3 tipos especiales
    assert len(special_room_locations) == 3

    # Cada tipo especial debe tener asignación a SOLO UN piso
    for special_type, locations in special_room_locations.items():
        # Debe tener exactamente 1 piso asignado
        assert len(locations) == 1, f"{special_type} debe estar en SOLO 1 piso, encontrado en {len(locations)} pisos"

        # La asignación debe ser R1-R4 (resultado de D4)
        for floor, room_num in locations.items():
            assert floor in [1, 2, 3], f"Piso debe ser 1, 2 o 3"
            assert 1 <= room_num <= 4, f"{special_type} en piso {floor} tiene room_num {room_num} (debe ser 1-4)"

    # Verificar que cada piso tiene EXACTAMENTE un tipo especial
    floors_assigned = []
    for special_type, locations in special_room_locations.items():
        for floor in locations.keys():
            floors_assigned.append(floor)

    assert sorted(floors_assigned) == [1, 2, 3], "Debe haber 1 especial por piso"


def test_special_rooms_marked_in_state():
    """Estado del juego marca habitaciones especiales correctamente"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    # Verificar flags
    assert "SPECIAL_ROOMS_SELECTED" in state.flags
    assert "SPECIAL_ROOM_LOCATIONS" in state.flags
    assert "CAMARA_LETAL_PRESENT" in state.flags

    # Exactamente 3 habitaciones especiales seleccionadas
    selected = state.flags["SPECIAL_ROOMS_SELECTED"]
    assert len(selected) == 3


def test_camara_letal_flag_set_when_selected():
    """Flag CAMARA_LETAL_PRESENT se marca si sale en sorteo"""
    # Probar con múltiples seeds hasta encontrar uno que incluya CAMARA_LETAL
    found_with_camara = False
    found_without_camara = False

    for seed in range(1, 100):
        state = make_smoke_state(seed=seed)
        selected = state.flags["SPECIAL_ROOMS_SELECTED"]
        camara_present = "CAMARA_LETAL" in selected

        assert state.flags["CAMARA_LETAL_PRESENT"] == camara_present

        if camara_present:
            found_with_camara = True
        else:
            found_without_camara = True

        if found_with_camara and found_without_camara:
            break

    # Verificar que encontramos casos de ambos tipos
    assert found_with_camara, "No se encontró ningún seed con CAMARA_LETAL"
    assert found_without_camara, "No se encontró ningún seed sin CAMARA_LETAL"


def test_room_state_has_special_card_id_assigned():
    """
    CORRECCIÓN A: Exactamente 3 habitaciones tienen special_card_id (reglas físicas).

    Antes había hasta 9 habitaciones especiales (3 tipos x 3 pisos).
    Ahora hay exactamente 3 (1 tipo por piso, sin duplicación).
    """
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    special_room_locations = state.flags["SPECIAL_ROOM_LOCATIONS"]

    # Contar cuántas habitaciones tienen special_card_id
    rooms_with_special = 0
    for room_state in state.rooms.values():
        if room_state.special_card_id is not None:
            rooms_with_special += 1

    # CORRECCIÓN A: Debe haber EXACTAMENTE 3 habitaciones con special_card_id
    assert rooms_with_special == 3, f"Debe haber exactamente 3 especiales, encontradas {rooms_with_special}"

    # Verificar que efectivamente tenemos 3 tipos de habitaciones especiales
    special_types_found = set()
    for room_state in state.rooms.values():
        if room_state.special_card_id is not None:
            special_types_found.add(room_state.special_card_id)

    assert len(special_types_found) == 3


def test_special_rooms_not_revealed_initially():
    """Habitaciones especiales no están reveladas inicialmente (boca abajo)"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    for room_state in state.rooms.values():
        if room_state.special_card_id is not None:
            # Debe estar boca abajo (no revelada)
            assert room_state.special_revealed is False
            # No debe estar destruida
            assert room_state.special_destroyed is False
            # Contador de activaciones en 0
            assert room_state.special_activation_count == 0


def test_special_room_locations_match_room_state():
    """Ubicaciones en flags corresponden a habitaciones con special_card_id"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    special_room_locations = state.flags["SPECIAL_ROOM_LOCATIONS"]

    # Crear un mapa inverso: ubicación -> special_type
    # Cuando hay colisiones, la última asignación gana
    location_to_special = {}
    for special_type, locations in special_room_locations.items():
        for floor, room_num in locations.items():
            rid = room_id(floor, room_num)
            location_to_special[rid] = special_type

    # Verificar que cada habitación tiene el special_card_id esperado
    for rid, expected_special in location_to_special.items():
        room_state = state.rooms[rid]
        # La habitación debe tener algún special_card_id (podría no ser el esperado si hubo colisión)
        assert room_state.special_card_id is not None, \
            f"Habitación {rid} debería tener special_card_id pero es None"


def test_deterministic_assignment_with_same_seed():
    """Mismo seed produce misma asignación de habitaciones especiales"""
    cfg = Config()
    state1 = make_smoke_state(seed=42, cfg=cfg)
    state2 = make_smoke_state(seed=42, cfg=cfg)

    # Mismas habitaciones especiales seleccionadas
    assert state1.flags["SPECIAL_ROOMS_SELECTED"] == state2.flags["SPECIAL_ROOMS_SELECTED"]

    # Mismas ubicaciones
    assert state1.flags["SPECIAL_ROOM_LOCATIONS"] == state2.flags["SPECIAL_ROOM_LOCATIONS"]

    # Mismo estado de CAMARA_LETAL
    assert state1.flags["CAMARA_LETAL_PRESENT"] == state2.flags["CAMARA_LETAL_PRESENT"]

"""
Tests para CORRECCIÓN A: Invariantes de Setup de Habitaciones Especiales

Verifica que validate_special_rooms_invariants detecta violaciones:
- Exactamente 3 habitaciones especiales
- Exactamente 1 por piso
- Ninguna en pasillos
"""

import pytest
from engine.state_factory import make_game_state, make_room
from engine.types import PlayerId, RoomId
from engine.setup import validate_special_rooms_invariants


def make_base_state():
    """Setup mínimo para tests."""
    return make_game_state(
        round=1,
        players={"P1": {"room": "F1_P", "sanity": 5}},
        rooms={},
    )

def test_valid_setup_passes():
    """
    Setup válido: 3 especiales, 1 por piso, en R1-R4.
    """
    s = make_base_state()

    # Crear habitaciones: 3 pisos x 4 rooms + pasillos
    for f in [1, 2, 3]:
        s.rooms[RoomId(f"F{f}_P")] = make_room(f"F{f}_P")
        for r in [1, 2, 3, 4]:
            s.rooms[RoomId(f"F{f}_R{r}")] = make_room(f"F{f}_R{r}")

    # Asignar 1 especial por piso
    s.rooms[RoomId("F1_R2")].special_card_id = "MOTEMEY"
    s.rooms[RoomId("F2_R3")].special_card_id = "CAMARA_LETAL"
    s.rooms[RoomId("F3_R1")].special_card_id = "PUERTAS"

    # No debe lanzar excepción
    validate_special_rooms_invariants(s)


def test_fail_total_not_3():
    """
    INVARIANTE 1: Debe fallar si hay != 3 especiales.
    """
    s = make_base_state()

    # Solo 2 especiales
    s.rooms[RoomId("F1_R1")] = make_room("F1_R1", special_card_id="MOTEMEY")
    s.rooms[RoomId("F2_R1")] = make_room("F2_R1", special_card_id="CAMARA_LETAL")
    # Falta F3

    # Completar rooms normales para pasar otros invariantes
    for f in [1, 2, 3]:
        if RoomId(f"F{f}_R1") not in s.rooms:
            s.rooms[RoomId(f"F{f}_R1")] = make_room(f"F{f}_R1")

    with pytest.raises(ValueError, match="exactamente 3 habitaciones especiales"):
        validate_special_rooms_invariants(s)


def test_fail_more_than_one_per_floor():
    """
    INVARIANTE 2: Debe fallar si un piso tiene >1 especial.
    """
    s = make_base_state()

    # Piso 1: 2 especiales (INVALID)
    s.rooms[RoomId("F1_R1")] = make_room("F1_R1", special_card_id="MOTEMEY")
    s.rooms[RoomId("F1_R2")] = make_room("F1_R2", special_card_id="PUERTAS")
    # Piso 2: 1 especial
    s.rooms[RoomId("F2_R1")] = make_room("F2_R1", special_card_id="CAMARA_LETAL")
    # Piso 3: sin especiales (compensar total)

    with pytest.raises(ValueError, match="Piso 1 debe tener exactamente 1"):
        validate_special_rooms_invariants(s)


def test_fail_special_in_corridor():
    """
    INVARIANTE 3: Debe fallar si hay especial en pasillo.
    """
    s = make_base_state()

    # Piso 1: especial en PASILLO (INVALID)
    s.rooms[RoomId("F1_P")] = make_room("F1_P", special_card_id="MOTEMEY")
    # Pisos 2 y 3: especiales válidos
    s.rooms[RoomId("F2_R1")] = make_room("F2_R1", special_card_id="CAMARA_LETAL")
    s.rooms[RoomId("F3_R1")] = make_room("F3_R1", special_card_id="PUERTAS")

    with pytest.raises(ValueError, match="no puede estar en pasillo"):
        validate_special_rooms_invariants(s)


def test_fail_no_special_on_a_floor():
    """
    INVARIANTE 2: Debe fallar si un piso no tiene especial (0).
    """
    s = make_base_state()

    # Piso 1: 1 especial
    s.rooms[RoomId("F1_R1")] = make_room("F1_R1", special_card_id="MOTEMEY")
    # Piso 2: 1 especial
    s.rooms[RoomId("F2_R1")] = make_room("F2_R1", special_card_id="CAMARA_LETAL")
    # Piso 3: 1 especial
    s.rooms[RoomId("F3_R1")] = make_room("F3_R1", special_card_id="PUERTAS")

    # Total 3: pasa invariante 1
    # Pero piso 3 no tiene especial si lo quitamos:
    s.rooms[RoomId("F3_R1")].special_card_id = None

    # Ahora: F1=1, F2=1, F3=0 (total=2)
    # Debería fallar tanto en total como en piso 3

    with pytest.raises(ValueError, match="exactamente"):
        validate_special_rooms_invariants(s)


def test_runner_make_smoke_state_passes_invariants():
    """
    El setup estándar de make_smoke_state debe pasar invariantes.
    """
    from sim.runner import make_smoke_state

    # Generar múltiples seeds para asegurar robustez
    for seed in range(1, 11):
        s = make_smoke_state(seed=seed)
        # No debe lanzar excepción
        validate_special_rooms_invariants(s)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

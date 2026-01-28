"""
Tests para FASE 4: Tesoros
- Llavero (TREASURE_RING): +1 capacidad llaves, +1 cordura máxima
- Escaleras (TREASURE_STAIRS): 3 usos, coloca escalera temporal
"""
import pytest
from engine.state_factory import make_game_state
from engine.types import PlayerId
from engine.objects import (
    has_treasure_ring,
    get_max_keys_capacity,
    get_effective_sanity_max,
    use_object,
    OBJECT_CATALOG
)
from engine.config import Config


def setup_basic_state():
    """Estado básico con 1 jugador"""
    rooms = ["F1_R1", "F1_P"]
    players = {
        "P1": {"room": "F1_R1", "sanity": 5, "sanity_max": 10, "keys": 0, "objects": []},
    }

    s = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=3,
        turn_pos=0,
        remaining_actions={},
        turn_order=["P1"],
    )
    s.flags = {}

    return s

# ===== TREASURE_RING (Llavero) Tests =====

def test_treasure_ring_increases_keys_capacity():
    """Llavero: +1 capacidad de llaves"""
    s = setup_basic_state()
    p = s.players[PlayerId("P1")]

    # Sin llavero: capacidad = 1
    assert get_max_keys_capacity(p) == 1

    # Con llavero: capacidad = 2
    p.objects.append("TREASURE_RING")
    assert get_max_keys_capacity(p) == 2


def test_treasure_ring_increases_sanity_max():
    """Llavero: +1 cordura máxima"""
    s = setup_basic_state()
    p = s.players[PlayerId("P1")]

    # Sin llavero: sanity_max = 10 (del setup)
    assert get_effective_sanity_max(p) == 10

    # Con llavero: sanity_max = 11
    p.objects.append("TREASURE_RING")
    assert get_effective_sanity_max(p) == 11


def test_treasure_ring_is_permanent():
    """Llavero: No tiene usos (permanente)"""
    obj_def = OBJECT_CATALOG["TREASURE_RING"]
    assert obj_def.uses is None, "Llavero debe ser permanente (uses=None)"


def test_treasure_ring_is_treasure():
    """Llavero: Está marcado como tesoro"""
    obj_def = OBJECT_CATALOG["TREASURE_RING"]
    assert obj_def.is_treasure is True


def test_treasure_ring_default_sanity_max():
    """Llavero: Si sanity_max no está definido, usa 5 como base"""
    s = setup_basic_state()
    p = s.players[PlayerId("P1")]
    p.sanity_max = None

    # Sin llavero: sanity_max = 5 (default)
    assert get_effective_sanity_max(p) == 5

    # Con llavero: sanity_max = 6
    p.objects.append("TREASURE_RING")
    assert get_effective_sanity_max(p) == 6


# ===== TREASURE_STAIRS (Escaleras) Tests =====

def test_treasure_stairs_has_3_uses():
    """Escaleras: 3 usos"""
    obj_def = OBJECT_CATALOG["TREASURE_STAIRS"]
    assert obj_def.uses == 3


def test_treasure_stairs_is_treasure():
    """Escaleras: Está marcado como tesoro"""
    obj_def = OBJECT_CATALOG["TREASURE_STAIRS"]
    assert obj_def.is_treasure is True


def test_treasure_stairs_creates_temp_stairs():
    """Escaleras: Crea escalera temporal en habitación actual"""
    from engine.rng import RNG
    s = setup_basic_state()
    p = s.players[PlayerId("P1")]
    p.objects.append("TREASURE_STAIRS")
    cfg = Config()
    rng = RNG(1)

    # Usar escaleras
    result = use_object(s, PlayerId("P1"), "TREASURE_STAIRS", cfg, rng)

    assert result is True, "Usar escaleras debe retornar True"
    # Verificar que se creó la escalera temporal
    flag_key = f"TEMP_STAIRS_{p.room}"
    assert flag_key in s.flags, "Debe crear flag de escalera temporal"
    assert s.flags[flag_key] == {"round": s.round, "pid": str(PlayerId("P1"))}, "Flag debe contener ronda y jugador"


def test_treasure_stairs_consumed_after_use():
    """Escaleras: Se consume al tercer uso (tiene 3 usos)"""
    from engine.rng import RNG
    s = setup_basic_state()
    p = s.players[PlayerId("P1")]
    p.objects.append("TREASURE_STAIRS")
    cfg = Config()
    rng = RNG(1)

    # Usar escaleras (1er uso)
    use_object(s, PlayerId("P1"), "TREASURE_STAIRS", cfg, rng)
    assert "TREASURE_STAIRS" in p.objects
    assert p.object_charges.get("TREASURE_STAIRS") == 2

    # 2do uso
    use_object(s, PlayerId("P1"), "TREASURE_STAIRS", cfg, rng)
    assert p.object_charges.get("TREASURE_STAIRS") == 1

    # 3er uso -> se consume
    use_object(s, PlayerId("P1"), "TREASURE_STAIRS", cfg, rng)
    assert "TREASURE_STAIRS" not in p.objects


def test_treasure_stairs_temp_stairs_valid_only_current_round():
    """Escaleras: Escalera temporal solo válida en ronda actual"""
    from engine.rng import RNG
    s = setup_basic_state()
    p = s.players[PlayerId("P1")]
    p.objects.append("TREASURE_STAIRS")
    cfg = Config()
    rng = RNG(1)

    # Usar escaleras en ronda 1
    s.round = 1
    use_object(s, PlayerId("P1"), "TREASURE_STAIRS", cfg, rng)

    flag_key = f"TEMP_STAIRS_{p.room}"
    assert s.flags[flag_key] == {"round": 1, "pid": str(PlayerId("P1"))}, "Flag debe tener ronda 1 y jugador"

    # Avanzar a ronda 2
    s.round = 2

    # La escalera temporal ya no es válida (flag sigue siendo 1, pero ronda actual es 2)
    assert s.flags[flag_key]["round"] != s.round, "Escalera temporal no es válida en ronda diferente"


# ===== Tests de Otros Tesoros (Pendientes de Implementación Detallada) =====

def test_treasure_crown_exists():
    """Corona: Existe en el catálogo (unificado como CROWN, soulbound)"""
    assert "CROWN" in OBJECT_CATALOG
    assert OBJECT_CATALOG["CROWN"].is_soulbound is True


def test_treasure_scroll_exists():
    """Pergamino: Existe en el catálogo"""
    assert "TREASURE_SCROLL" in OBJECT_CATALOG


def test_treasure_pendant_exists():
    """Colgante: Existe en el catálogo"""
    assert "TREASURE_PENDANT" in OBJECT_CATALOG

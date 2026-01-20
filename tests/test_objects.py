"""
Tests para sistema de objetos con efectos (FASE 0.3)
"""
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState, MonsterState
from engine.types import PlayerId, RoomId
from engine.config import Config
from engine.objects import use_object, OBJECT_CATALOG
from engine.rng import RNG


def setup_object_state():
    """Estado básico para tests de objetos."""
    rooms = {
        RoomId("F1_R1"): RoomState(
            room_id=RoomId("F1_R1"),
            deck=DeckState(cards=[])
        ),
        RoomId("F1_P"): RoomState(
            room_id=RoomId("F1_P"),
            deck=DeckState(cards=[])
        ),
        RoomId("F2_R1"): RoomState(
            room_id=RoomId("F2_R1"),
            deck=DeckState(cards=[])
        ),
    }
    players = {
        PlayerId("P1"): PlayerState(
            player_id=PlayerId("P1"),
            sanity=5,
            room=RoomId("F1_R1"),
            sanity_max=10,
            keys=0,
            objects=[]
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
        flags={},
    )
    return s


def test_use_vial():
    """Vial recupera 2 cordura"""
    s = setup_object_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()
    rng = RNG(1)

    # P1 tiene vial
    p1.objects.append("VIAL")
    p1.sanity = 3  # Cordura inicial

    # Usar vial
    result = use_object(s, PlayerId("P1"), "VIAL", cfg, rng)

    assert result == True
    assert p1.sanity == 5  # 3 + 2
    assert "VIAL" not in p1.objects  # Consumido


def test_use_vial_respects_max_sanity():
    """Vial no excede cordura máxima"""
    s = setup_object_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()
    rng = RNG(1)

    # P1 tiene vial
    p1.objects.append("VIAL")
    p1.sanity = 9  # Cercano al máximo
    p1.sanity_max = 10

    # Usar vial
    result = use_object(s, PlayerId("P1"), "VIAL", cfg, rng)

    assert result == True
    assert p1.sanity == 10  # Clamped a max
    assert "VIAL" not in p1.objects


def test_use_compass():
    """Brújula mueve al pasillo"""
    s = setup_object_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()
    rng = RNG(1)

    # P1 tiene brújula y está en habitación
    p1.objects.append("COMPASS")
    p1.room = RoomId("F1_R1")

    # Usar brújula
    result = use_object(s, PlayerId("P1"), "COMPASS", cfg, rng)

    assert result == True
    assert p1.room == RoomId("F1_P")  # Movido al pasillo piso 1
    assert "COMPASS" not in p1.objects  # Consumido


def test_use_blunt():
    """Contundente aturde monstruo"""
    s = setup_object_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()
    rng = RNG(1)

    # P1 tiene contundente
    p1.objects.append("BLUNT")

    # Hay un monstruo en la habitación de P1
    s.monsters.append(MonsterState(monster_id="SKELETON", room=RoomId("F1_R1")))

    # Usar contundente
    result = use_object(s, PlayerId("P1"), "BLUNT", cfg, rng)

    assert result == True
    assert "BLUNT" not in p1.objects  # Consumido

    # Verificar que monstruo está aturdido
    stun_flag = s.flags.get("STUN_SKELETON_UNTIL_ROUND")
    assert stun_flag is not None
    assert stun_flag == s.round + 2  # Aturdido por 2 rondas


def test_use_object_not_in_inventory():
    """No se puede usar objeto que no se tiene"""
    s = setup_object_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()
    rng = RNG(1)

    # P1 NO tiene vial
    assert "VIAL" not in p1.objects

    # Intentar usar vial
    result = use_object(s, PlayerId("P1"), "VIAL", cfg, rng)

    assert result == False
    assert p1.sanity == 5  # Sin cambios


def test_use_object_unknown():
    """No se puede usar objeto desconocido"""
    s = setup_object_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()
    rng = RNG(1)

    # P1 tiene objeto desconocido
    p1.objects.append("UNKNOWN_OBJECT")

    # Intentar usar
    result = use_object(s, PlayerId("P1"), "UNKNOWN_OBJECT", cfg, rng)

    assert result == False


def test_object_catalog():
    """Catálogo de objetos tiene definiciones correctas"""
    assert "COMPASS" in OBJECT_CATALOG
    assert "VIAL" in OBJECT_CATALOG
    assert "BLUNT" in OBJECT_CATALOG

    # Vial es consumible (1 uso)
    vial = OBJECT_CATALOG["VIAL"]
    assert vial.uses == 1
    assert vial.is_blunt == False

    # Blunt es contundente
    blunt = OBJECT_CATALOG["BLUNT"]
    assert blunt.is_blunt == True

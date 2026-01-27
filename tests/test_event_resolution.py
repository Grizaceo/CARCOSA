"""
Tests para sistema de resolución de eventos (FASE 0.1)
"""
import pytest
from engine.state_factory import make_game_state
from engine.types import PlayerId, CardId, RoomId
from engine.config import Config
from engine.transition import _resolve_card_minimal
from engine.rng import RNG


def setup_event_state():
    """Estado básico para tests de eventos."""
    rooms = ["F1_R1", "F1_R2"]
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


def test_event_card_triggers_resolution():
    """EVENT:X en carta debe llamar a _resolve_event()"""
    s = setup_event_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()
    rng = RNG(1)

    initial_sanity = p1.sanity

    # Resolver carta de evento
    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:REFLEJO_AMARILLO"), cfg, rng)

    # Verificar que el evento se ejecutó (-2 cordura)
    assert p1.sanity == initial_sanity - 2


def test_event_returns_to_bottom():
    """Evento resuelto vuelve al fondo del mazo"""
    s = setup_event_state()
    cfg = Config()
    rng = RNG(1)

    # Agregar deck a la habitación de P1
    room_deck = s.rooms[RoomId("F1_R1")].deck
    initial_deck_size = len(room_deck.cards)

    # Resolver evento
    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:REFLEJO_AMARILLO"), cfg, rng)

    # Verificar que la carta volvió al mazo
    assert len(room_deck.cards) == initial_deck_size + 1
    assert str(room_deck.cards[-1]) == "EVENT:REFLEJO_AMARILLO"


def test_total_calculation():
    """Total = d6 + cordura, clamp mínimo 0"""
    s = setup_event_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()

    # Test con cordura positiva
    p1.sanity = 3
    rng = RNG(1)  # Seed fijo para d6 predecible
    # Con seed=1, primer d6 debería dar un valor consistente

    initial_sanity = p1.sanity
    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:ESPEJO_AMARILLO"), cfg, rng)

    # Espejo invierte cordura, así que debería ser negativa
    assert p1.sanity == -initial_sanity

    # Test con cordura negativa (Total debe ser >= 0)
    s2 = setup_event_state()
    p2 = s2.players[PlayerId("P1")]
    p2.sanity = -10  # Muy negativa
    rng2 = RNG(2)

    # HAY_CADAVER usa Total, deberíamos ver efecto consistente con Total >= 0
    _resolve_card_minimal(s2, PlayerId("P1"), CardId("EVENT:HAY_CADAVER"), cfg, rng2)

    # Con cordura -10 y d6 (1-6), Total = max(0, -10 + d6) = 0
    # Así que efecto sería Total 0-2 → skip turn
    assert s2.flags.get("SKIP_TURN_P1") == True


def test_event_reflejo_amarillo():
    """Reflejo de Amarillo aplica -2 cordura"""
    s = setup_event_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()
    rng = RNG(1)

    initial_sanity = p1.sanity

    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:REFLEJO_AMARILLO"), cfg, rng)

    assert p1.sanity == initial_sanity - 2


def test_event_espejo_amarillo():
    """Espejo de Amarillo invierte cordura"""
    s = setup_event_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()
    rng = RNG(1)

    # Cordura positiva
    p1.sanity = 3
    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:ESPEJO_AMARILLO"), cfg, rng)
    assert p1.sanity == -3

    # Cordura negativa
    p1.sanity = -2
    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:ESPEJO_AMARILLO"), cfg, rng)
    assert p1.sanity == 2


def test_event_hay_cadaver_total_low():
    """Hay un Cadáver con Total bajo: pierde turno"""
    s = setup_event_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()

    # Forzar Total bajo con cordura muy negativa
    p1.sanity = -10
    rng = RNG(1)  # d6=1-6, Total = max(0, -10+d6) = 0-0 (muy bajo)

    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:HAY_CADAVER"), cfg, rng)

    # Con Total 0-2, debería setear flag de skip turn
    assert s.flags.get("SKIP_TURN_P1") == True


def test_event_divan_amarillo():
    """Un Diván de Amarillo remueve estados"""
    s = setup_event_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()

    # Agregar estados
    from engine.state import StatusInstance
    p1.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=2))
    assert len(p1.statuses) == 1

    # Forzar Total bajo para efecto de remover estados
    p1.sanity = -10
    rng = RNG(1)

    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:DIVAN_AMARILLO"), cfg, rng)

    # Con Total 0-3, remueve estados
    assert len(p1.statuses) == 0


def test_event_cambia_caras():
    """Cambia Caras intercambia posiciones"""
    s = setup_event_state()
    p1 = s.players[PlayerId("P1")]
    p2 = s.players[PlayerId("P2")]
    cfg = Config()
    rng = RNG(1)

    initial_p1_room = p1.room
    initial_p2_room = p2.room

    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:CAMBIA_CARAS"), cfg, rng)

    # Debería haber intercambiado con P2 (según Total)
    # Con sanity=5 + d6, Total será >= 5, así que swap con izquierda
    # P1 está en posición 0, izquierda es P2
    assert p1.room == initial_p2_room
    assert p2.room == initial_p1_room


def test_event_comida_servida_total_0():
    """Una Comida Servida con Total 0: -3 cordura"""
    s = setup_event_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()

    # Forzar Total 0 con cordura muy negativa
    p1.sanity = -10
    rng = RNG(1)

    initial_sanity = p1.sanity
    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:COMIDA_SERVIDA"), cfg, rng)

    # Con Total 0, -3 cordura
    assert p1.sanity == initial_sanity - 3


def test_event_comida_servida_total_high():
    """Una Comida Servida con Total alto: trae otro jugador y +2 cordura"""
    s = setup_event_state()
    p1 = s.players[PlayerId("P1")]
    p2 = s.players[PlayerId("P2")]
    cfg = Config()

    # Forzar Total alto
    p1.sanity = 10
    rng = RNG(1)  # d6 + 10 = Total >= 7

    initial_p1_sanity = p1.sanity
    initial_p2_sanity = p2.sanity
    initial_p2_room = p2.room

    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:COMIDA_SERVIDA"), cfg, rng)

    # Con Total 7+, P2 debería estar en la habitación de P1
    assert p2.room == p1.room
    # Ambos +2 cordura
    assert p1.sanity == min(initial_p1_sanity + 2, 10)
    assert p2.sanity == min(initial_p2_sanity + 2, 10)


def test_event_furia_amarillo_total_0():
    """La Furia de Amarillo con Total 0: dobla efecto del Rey"""
    s = setup_event_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()

    # Forzar Total 0
    p1.sanity = -10
    rng = RNG(1)

    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:FURIA_AMARILLO"), cfg, rng)

    # Con Total 0, dobla daño del Rey PERMANENTEMENTE
    assert s.flags.get("KING_DAMAGE_DOUBLE_PERMANENT") is True


def test_event_furia_amarillo_total_high():
    """La Furia de Amarillo con Total alto: aturde al Rey"""
    s = setup_event_state()
    p1 = s.players[PlayerId("P1")]
    cfg = Config()

    # Forzar Total alto
    p1.sanity = 10
    rng = RNG(1)  # d6 + 10 = Total >= 5

    _resolve_card_minimal(s, PlayerId("P1"), CardId("EVENT:FURIA_AMARILLO"), cfg, rng)

    # Con Total 5+, aturde al Rey 1 ronda (vanished)
    assert s.king_vanished_turns > 0

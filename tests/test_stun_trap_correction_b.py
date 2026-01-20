"""
Tests para CORRECCIÓN B: STUN y Trampas - Reglas Definitivas

Cubre:
- TRAPPED_SPIDER: 3 turnos + escape roll automático
- Escape exitoso: libera + STUN 1 turno al monstruo fuente
- Escape fallido: pierde las 2 acciones ese turno
- Contundente: STUN 2 turnos al monstruo
- Rey de Amarillo: inmune al STUN
"""

import pytest
from engine.state import GameState, PlayerState, MonsterState, StatusInstance, DeckState, RoomState
from engine.types import PlayerId, RoomId, CardId
from engine.actions import ActionType, Action
from engine.transition import step
from engine.config import Config
from engine.rng import RNG


def make_test_state() -> GameState:
    """
    Setup base para tests: 1 jugador, 1 monstruo araña, configuración mínima.
    """
    s = GameState(
        round=1,
        players={
            PlayerId("P1"): PlayerState(
                player_id=PlayerId("P1"),
                sanity=5,
                room=RoomId("F1_R1"),
                sanity_max=5,
                keys=0,
                objects=[],
                soulbound_items=[],
                statuses=[],
                at_umbral=False,
                at_minus5=False
            )
        },
        monsters=[
            MonsterState(
                monster_id="SPIDER_001",
                room=RoomId("F1_R1"),
                stunned_remaining_rounds=0
            )
        ],
        rooms={
            RoomId("F1_R1"): RoomState(
                room_id=RoomId("F1_R1"),
                deck=DeckState(cards=[]),
                revealed=0
            )
        },
        phase="PLAYER",
        turn_order=[PlayerId("P1")],
        starter_pos=0,
        turn_pos=0,
        remaining_actions={PlayerId("P1"): 2},
        king_floor=1,
        false_king_floor=2,
        keys_destroyed=0,
        limited_action_floor_next=None,
        king_vanish_ends=0,
        game_over=False,
        outcome=None
    )
    return s


def test_trapped_spider_duration_3_turns():
    """
    TRAPPED_SPIDER debe tener duración de 3 turnos y decrementar cada ronda.
    """
    p = PlayerState(
        player_id=PlayerId("P1"),
        sanity=5,
        room=RoomId("F1_R1"),
        statuses=[
            StatusInstance(
                status_id="TRAPPED_SPIDER",
                remaining_rounds=3,
                metadata={"source_monster_id": "SPIDER_001"}
            )
        ]
    )

    # Verificar duración inicial
    assert p.statuses[0].remaining_rounds == 3
    assert p.statuses[0].metadata["source_monster_id"] == "SPIDER_001"

    # Simular tick de ronda
    for st in p.statuses:
        if st.remaining_rounds != -1:
            st.remaining_rounds -= 1

    assert p.statuses[0].remaining_rounds == 2

    # Segundo tick
    for st in p.statuses:
        if st.remaining_rounds != -1:
            st.remaining_rounds -= 1

    assert p.statuses[0].remaining_rounds == 1

    # Tercer tick
    for st in p.statuses:
        if st.remaining_rounds != -1:
            st.remaining_rounds -= 1

    # Remover estados expirados
    p.statuses = [st for st in p.statuses if st.remaining_rounds > 0 or st.remaining_rounds == -1]

    # Debe estar removido
    assert len(p.statuses) == 0


def test_spider_escape_roll_success_releases_and_stuns():
    """
    Escape exitoso (d6 + cordura >= 3): remueve TRAPPED_SPIDER y aplica STUN 1 turno al monstruo fuente.
    """
    s = make_test_state()
    p1 = s.players[PlayerId("P1")]

    # Aplicar TRAPPED_SPIDER
    p1.statuses.append(
        StatusInstance(
            status_id="TRAPPED_SPIDER",
            remaining_rounds=3,
            metadata={"source_monster_id": "SPIDER_001"}
        )
    )

    # RNG que garantiza éxito: d6=3, cordura=5 → total=8 >= 3
    rng = RNG(42)
    # Forzar roll específico (necesitamos saber el seed que produce d6=3)
    # Para este test, cualquier roll >= 3 con cordura 5 debería pasar
    # Vamos a forzarlo manualmente en el test

    # Mock RNG: d6=3 garantizado
    class MockRNG:
        def randint(self, a, b):
            if (a, b) == (1, 6):
                return 3  # d6=3
            return a

    mock_rng = MockRNG()

    # Primera acción del jugador: debería disparar escape automático
    action = Action(actor="P1", type=ActionType.MEDITATE, data={})
    s_new = step(s, action, mock_rng, Config())

    p1_new = s_new.players[PlayerId("P1")]
    spider = s_new.monsters[0]

    # Verificar que el jugador se liberó
    assert not any(st.status_id == "TRAPPED_SPIDER" for st in p1_new.statuses)

    # Verificar que el monstruo fue stuneado por 1 turno
    assert spider.stunned_remaining_rounds == 1


def test_spider_escape_roll_fail_loses_actions():
    """
    Escape fallido (d6 + cordura < 3): jugador pierde las 2 acciones ese turno.
    """
    s = make_test_state()
    p1 = s.players[PlayerId("P1")]
    p1.sanity = -3  # cordura negativa para garantizar falla

    # Aplicar TRAPPED_SPIDER
    p1.statuses.append(
        StatusInstance(
            status_id="TRAPPED_SPIDER",
            remaining_rounds=3,
            metadata={"source_monster_id": "SPIDER_001"}
        )
    )

    # Mock RNG: d6=1 → total = 1 + (-3) = -2 < 3 (falla)
    class MockRNG:
        def randint(self, a, b):
            if (a, b) == (1, 6):
                return 1  # d6=1
            return a

    mock_rng = MockRNG()

    # Primera acción del jugador: debería disparar escape automático y fallar
    action = Action(actor="P1", type=ActionType.MEDITATE, data={})
    s_new = step(s, action, mock_rng, Config())

    p1_new = s_new.players[PlayerId("P1")]

    # Verificar que el jugador sigue trapped
    assert any(st.status_id == "TRAPPED_SPIDER" for st in p1_new.statuses)

    # Verificar que perdió todas sus acciones
    assert s_new.remaining_actions[PlayerId("P1")] == 0


def test_blunt_stuns_monster_2_turns():
    """
    Objeto contundente: STUN de 2 turnos al monstruo.
    """
    s = make_test_state()
    p1 = s.players[PlayerId("P1")]
    p1.objects.append("BLUNT")

    # Usar contundente
    from engine.objects import use_object
    success = use_object(s, PlayerId("P1"), "BLUNT", Config(), RNG(1))

    assert success
    assert "BLUNT" not in p1.objects  # Se consumió

    # Verificar que el monstruo fue stuneado por 2 turnos
    spider = s.monsters[0]
    assert spider.stunned_remaining_rounds == 2


def test_yellow_king_not_stunnable():
    """
    Rey de Amarillo no puede ser stuneado.
    """
    s = make_test_state()
    # Cambiar el monstruo a Rey de Amarillo
    s.monsters[0].monster_id = "YELLOW_KING_001"

    p1 = s.players[PlayerId("P1")]
    p1.objects.append("BLUNT")

    # Usar contundente
    from engine.objects import use_object
    success = use_object(s, PlayerId("P1"), "BLUNT", Config(), RNG(1))

    assert success

    # Verificar que el Rey NO fue stuneado
    king = s.monsters[0]
    assert king.stunned_remaining_rounds == 0


def test_stun_decrements_at_end_of_round():
    """
    stunned_remaining_rounds se decrementa al final de ronda.
    """
    from engine.transition import _apply_status_effects_end_of_round

    s = make_test_state()
    spider = s.monsters[0]
    spider.stunned_remaining_rounds = 2

    # Aplicar efectos de fin de ronda
    _apply_status_effects_end_of_round(s)

    # Verificar que decrementó
    assert spider.stunned_remaining_rounds == 1

    # Segundo tick
    _apply_status_effects_end_of_round(s)
    assert spider.stunned_remaining_rounds == 0

    # Tercer tick (ya en 0, no debe ser negativo)
    _apply_status_effects_end_of_round(s)
    assert spider.stunned_remaining_rounds == 0


def test_escape_only_once_per_turn():
    """
    El intento de escape automático solo debe ejecutarse una vez por turno del jugador.
    """
    s = make_test_state()
    p1 = s.players[PlayerId("P1")]

    # Aplicar TRAPPED_SPIDER
    p1.statuses.append(
        StatusInstance(
            status_id="TRAPPED_SPIDER",
            remaining_rounds=3,
            metadata={"source_monster_id": "SPIDER_001"}
        )
    )

    # Mock RNG: siempre éxito
    class MockRNG:
        def __init__(self):
            self.call_count = 0

        def randint(self, a, b):
            if (a, b) == (1, 6):
                self.call_count += 1
                return 6  # Siempre éxito
            return a

    mock_rng = MockRNG()

    # Primera acción: dispara escape
    action1 = Action(actor="P1", type=ActionType.MEDITATE, data={})
    s = step(s, action1, mock_rng, Config())

    # El jugador debería estar libre ahora
    assert not any(st.status_id == "TRAPPED_SPIDER" for st in s.players[PlayerId("P1")].statuses)

    # El RNG debería haberse llamado exactamente 1 vez para el escape
    assert mock_rng.call_count == 1

    # Verificar que el flag de escape se creó
    assert s.flags.get(f"ESCAPE_ATTEMPT_P1_ROUND_{s.round}", False) == True

    # El jugador todavía tiene 1 acción (MEDITATE consumió 1, empezó con 2)
    assert s.remaining_actions[PlayerId("P1")] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

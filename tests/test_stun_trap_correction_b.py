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
from engine.state import MonsterState, StatusInstance
from engine.state_factory import make_game_state, make_player
from engine.types import PlayerId, RoomId
from engine.actions import ActionType, Action
from engine.transition import step
from engine.config import Config
from engine.rng import RNG


def make_test_state():
    """
    Setup base para tests: 1 jugador, 1 monstruo araña, configuración mínima.
    """
    s = make_game_state(
        round=1,
        players={
            "P1": {"room": "F1_R1", "sanity": 5, "sanity_max": 5, "keys": 0, "objects": []}
        },
        rooms={"F1_R1": {}},
        phase="PLAYER",
        turn_order=["P1"],
        starter_pos=0,
        turn_pos=0,
        remaining_actions={"P1": 2},
        king_floor=1,
    )
    s.monsters = [
        MonsterState(
            monster_id="SPIDER_001",
            room=RoomId("F1_R1"),
            stunned_remaining_rounds=0
        )
    ]
    s.false_king_floor = 2
    s.keys_destroyed = 0
    s.limited_action_floor_next = None
    s.king_vanish_ends = 0
    s.game_over = False
    s.outcome = None
    return s

def test_trapped_spider_duration_3_turns():
    """
    TRAPPED_SPIDER debe tener duración de 3 turnos y decrementar cada ronda.
    """
    p = make_player(
        player_id="P1",
        room="F1_R1",
        sanity=5,
    )
    p.statuses = [
        StatusInstance(
            status_id="TRAPPED_SPIDER",
            remaining_rounds=3,
            metadata={"source_monster_id": "SPIDER_001"}
        )
    ]

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
    Escape exitoso (d6 >= 3): remueve TRAPPED y aplica STUN 1 turno al monstruo.
    CANON: Escape es MANUAL via ESCAPE_TRAPPED action.
    """
    s = make_test_state()
    p1 = s.players[PlayerId("P1")]

    # Aplicar TRAPPED (canónico)
    p1.statuses.append(
        StatusInstance(
            status_id="TRAPPED",
            remaining_rounds=3,
            metadata={"source_monster_id": "SPIDER_001"}
        )
    )


    # Mock RNG: d6=3 guaranteed. Sanity=5. Total 8 >= 3. Success.
    class MockRNG:
        def randint(self, a, b):
            if (a, b) == (1, 6):
                return 3  # d6=3
            return a

    mock_rng = MockRNG()

    # Acción MANUAL de escape
    action = Action(actor="P1", type=ActionType.ESCAPE_TRAPPED, data={})
    s_new = step(s, action, mock_rng, Config())

    p1_new = s_new.players[PlayerId("P1")]
    spider = s_new.monsters[0]

    # Verificar que el jugador se liberó
    assert not any(st.status_id == "TRAPPED" for st in p1_new.statuses)

    # Verificar que el monstruo fue stuneado por 1 turno
    assert spider.stunned_remaining_rounds == 1


def test_spider_escape_roll_fail_loses_actions():
    """
    Escape fallido (d6 + sanity < 3): jugador pierde todas las acciones ese turno.
    CANON: Escape es MANUAL via ESCAPE_TRAPPED action.
    """
    s = make_test_state()
    p1 = s.players[PlayerId("P1")]
    p1.sanity = 0 # Baseline sanity for failure case

    # Aplicar TRAPPED
    p1.statuses.append(
        StatusInstance(
            status_id="TRAPPED",
            remaining_rounds=3,
            metadata={"source_monster_id": "SPIDER_001"}
        )
    )

    # Mock RNG: d6=2. Total = 2 + 0 = 2 < 3 -> falla
    class MockRNG:
        def randint(self, a, b):
            if (a, b) == (1, 6):
                return 2  # d6=2
            return a

    mock_rng = MockRNG()

    # Acción MANUAL de escape
    action = Action(actor="P1", type=ActionType.ESCAPE_TRAPPED, data={})
    s_new = step(s, action, mock_rng, Config())

    p1_new = s_new.players[PlayerId("P1")]

    # Verificar que el jugador sigue trapped
    assert any(st.status_id == "TRAPPED" for st in p1_new.statuses)

    # CANON: Fallo termina turno inmediatamente (0 acciones)
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


def test_stun_decrements_at_monster_phase():
    """
    stunned_remaining_rounds se decrementa en Fase de Monstruos (no en end_of_round types).
    """
    from engine.transition import _monster_phase

    s = make_test_state()
    spider = s.monsters[0]
    spider.stunned_remaining_rounds = 2

    # Aplicar Fase de Monstruos
    _monster_phase(s, Config())

    # Verificar que decrementó
    assert spider.stunned_remaining_rounds == 1

    # Segundo tick
    _monster_phase(s, Config())
    assert spider.stunned_remaining_rounds == 0

    # Tercer tick (ya en 0, no debe ser negativo ni atacar si estaba stuneado? Si llega 0 ataca?)
    # Canon: Si empieza fase stun=0, ataca. Si empieza stun>0, decrementa y NO ataca.
    # Aquí solo probamos decremento.
    _monster_phase(s, Config())
    assert spider.stunned_remaining_rounds == 0


# test_escape_only_once_per_turn ELIMINADO
# CANON: Ya no hay auto-escape. El escape es manual via ESCAPE_TRAPPED action.
# Este test testeaba comportamiento obsoleto (auto-escape al inicio del turno).


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

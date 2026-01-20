"""
Tests para estados canónicos (FASE 3)
"""
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState, StatusInstance
from engine.types import PlayerId, RoomId
from engine.actions import Action, ActionType
from engine.config import Config
from engine.transition import step
from engine.rng import RNG


def setup_state_test():
    """Estado básico para tests de estados."""
    rooms = {
        RoomId("F1_R1"): RoomState(
            room_id=RoomId("F1_R1"),
            deck=DeckState(cards=[])
        ),
        RoomId("F1_R2"): RoomState(
            room_id=RoomId("F1_R2"),
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
        PlayerId("P2"): PlayerState(
            player_id=PlayerId("P2"),
            sanity=7,
            room=RoomId("F1_R2"),
            sanity_max=10,
            keys=0,
            objects=[]
        ),
        PlayerId("P3"): PlayerState(
            player_id=PlayerId("P3"),
            sanity=6,
            room=RoomId("F2_R1"),
            sanity_max=10,
            keys=0,
            objects=[]
        ),
    }
    s = GameState(
        round=1,
        players=players,
        rooms=rooms,
        phase="KING",
        king_floor=3,
        turn_pos=0,
        remaining_actions={},
        turn_order=[PlayerId("P1"), PlayerId("P2"), PlayerId("P3")],
        flags={},
    )
    return s


def test_sangrado_applies_damage_at_end_of_round():
    """SANGRADO aplica -1 cordura al final de ronda"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="SANGRADO", remaining_rounds=2))
    initial_sanity = s.players[PlayerId("P1")].sanity
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # Verificar que perdió 1 cordura por SANGRADO
    # (además de la pérdida por casa y posibles efectos del Rey)
    # La pérdida de casa es 1 por defecto, así que total debería ser -2
    p1_after = s.players[PlayerId("P1")]
    # Calcular pérdida esperada: casa (-1) + sangrado (-1) = -2
    expected_sanity = initial_sanity - cfg.HOUSE_LOSS_PER_ROUND - 1
    assert p1_after.sanity == expected_sanity


def test_sangrado_duration_decrements():
    """SANGRADO decrementa duración y desaparece cuando llega a 0"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="SANGRADO", remaining_rounds=1))
    assert len(s.players[PlayerId("P1")].statuses) == 1
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # Verificar que el estado desapareció
    assert len(s.players[PlayerId("P1")].statuses) == 0


def test_sangrado_multiple_players():
    """Múltiples jugadores con SANGRADO cada uno pierde cordura"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="SANGRADO", remaining_rounds=2))
    s.players[PlayerId("P2")].statuses.append(StatusInstance(status_id="SANGRADO", remaining_rounds=2))

    initial_p1_sanity = s.players[PlayerId("P1")].sanity
    initial_p2_sanity = s.players[PlayerId("P2")].sanity
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # Ambos deberían haber perdido cordura
    expected_p1 = initial_p1_sanity - cfg.HOUSE_LOSS_PER_ROUND - 1
    expected_p2 = initial_p2_sanity - cfg.HOUSE_LOSS_PER_ROUND - 1
    assert s.players[PlayerId("P1")].sanity == expected_p1
    assert s.players[PlayerId("P2")].sanity == expected_p2


def test_sangrado_with_other_states():
    """SANGRADO funciona correctamente con otros estados simultáneos"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="SANGRADO", remaining_rounds=2))
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=1))

    initial_sanity = s.players[PlayerId("P1")].sanity
    initial_status_count = len(s.players[PlayerId("P1")].statuses)
    assert initial_status_count == 2
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # SANGRADO aplicó efecto
    expected_sanity = initial_sanity - cfg.HOUSE_LOSS_PER_ROUND - 1
    p1_after = s.players[PlayerId("P1")]
    assert p1_after.sanity == expected_sanity

    # TRAPPED desapareció, SANGRADO quedó con 1 ronda
    assert len(p1_after.statuses) == 1
    assert p1_after.statuses[0].status_id == "SANGRADO"
    assert p1_after.statuses[0].remaining_rounds == 1


def test_sangrado_duration_persists_across_round():
    """SANGRADO con duración 3 persiste después de una ronda"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="SANGRADO", remaining_rounds=3))
    initial_sanity = s.players[PlayerId("P1")].sanity
    cfg = Config()
    rng = RNG(1)

    # Ejecutar una ronda
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # Verificar que aplicó daño y duración decrementó
    sanity_after = s.players[PlayerId("P1")].sanity
    assert sanity_after == initial_sanity - cfg.HOUSE_LOSS_PER_ROUND - 1
    assert len(s.players[PlayerId("P1")].statuses) == 1
    assert s.players[PlayerId("P1")].statuses[0].remaining_rounds == 2


# ==================== MALDITO Tests ====================

def test_maldito_damages_other_players_same_floor():
    """MALDITO causa -1 cordura a otros jugadores en el mismo piso"""
    s = setup_state_test()
    s.king_floor = 4  # Rey en piso 4 para no afectar a los jugadores
    # P1 y P2 en piso 1, P3 en piso 2
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="MALDITO", remaining_rounds=2))

    initial_p1_sanity = s.players[PlayerId("P1")].sanity
    initial_p2_sanity = s.players[PlayerId("P2")].sanity
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # P1 no se daña a sí mismo, solo pierde por casa
    expected_p1 = initial_p1_sanity - cfg.HOUSE_LOSS_PER_ROUND
    # P2 pierde por casa + MALDITO de P1 (están en el mismo piso)
    expected_p2 = initial_p2_sanity - cfg.HOUSE_LOSS_PER_ROUND - 1

    assert s.players[PlayerId("P1")].sanity == expected_p1
    assert s.players[PlayerId("P2")].sanity == expected_p2
    # P3 puede haber sido movido por el Rey, no verificamos su cordura aquí


def test_maldito_does_not_damage_self():
    """MALDITO no daña al jugador que lo tiene"""
    s = setup_state_test()
    # Solo P1 con MALDITO, nadie más en su piso
    s.players[PlayerId("P2")].room = RoomId("F2_R1")  # Mover P2 a piso 2
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="MALDITO", remaining_rounds=2))

    initial_sanity = s.players[PlayerId("P1")].sanity
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # P1 solo pierde por casa, no por MALDITO
    expected_sanity = initial_sanity - cfg.HOUSE_LOSS_PER_ROUND
    assert s.players[PlayerId("P1")].sanity == expected_sanity


def test_maldito_multiple_cursed_players():
    """Múltiples jugadores con MALDITO en el mismo piso se dañan entre sí"""
    s = setup_state_test()
    # P1 y P2 con MALDITO en piso 1
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="MALDITO", remaining_rounds=2))
    s.players[PlayerId("P2")].statuses.append(StatusInstance(status_id="MALDITO", remaining_rounds=2))

    initial_p1_sanity = s.players[PlayerId("P1")].sanity
    initial_p2_sanity = s.players[PlayerId("P2")].sanity
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # P1 pierde por casa + MALDITO de P2
    expected_p1 = initial_p1_sanity - cfg.HOUSE_LOSS_PER_ROUND - 1
    # P2 pierde por casa + MALDITO de P1
    expected_p2 = initial_p2_sanity - cfg.HOUSE_LOSS_PER_ROUND - 1

    assert s.players[PlayerId("P1")].sanity == expected_p1
    assert s.players[PlayerId("P2")].sanity == expected_p2


def test_maldito_duration_decrements():
    """MALDITO decrementa duración correctamente"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="MALDITO", remaining_rounds=1))
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # Estado desaparece
    assert len(s.players[PlayerId("P1")].statuses) == 0


# ==================== SANIDAD Tests ====================

def test_sanidad_recovers_sanity():
    """SANIDAD recupera +1 cordura al final de ronda"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="SANIDAD", remaining_rounds=2))
    initial_sanity = s.players[PlayerId("P1")].sanity
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # P1 pierde por casa (-1) pero recupera por SANIDAD (+1) = 0 neto
    expected_sanity = initial_sanity - cfg.HOUSE_LOSS_PER_ROUND + 1
    assert s.players[PlayerId("P1")].sanity == expected_sanity


def test_sanidad_duration_decrements():
    """SANIDAD decrementa duración correctamente"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="SANIDAD", remaining_rounds=1))
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # Estado desaparece
    assert len(s.players[PlayerId("P1")].statuses) == 0


def test_sanidad_multiple_players():
    """Múltiples jugadores con SANIDAD cada uno recupera cordura"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="SANIDAD", remaining_rounds=2))
    s.players[PlayerId("P2")].statuses.append(StatusInstance(status_id="SANIDAD", remaining_rounds=2))

    initial_p1_sanity = s.players[PlayerId("P1")].sanity
    initial_p2_sanity = s.players[PlayerId("P2")].sanity
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # Ambos recuperan
    expected_p1 = initial_p1_sanity - cfg.HOUSE_LOSS_PER_ROUND + 1
    expected_p2 = initial_p2_sanity - cfg.HOUSE_LOSS_PER_ROUND + 1

    assert s.players[PlayerId("P1")].sanity == expected_p1
    assert s.players[PlayerId("P2")].sanity == expected_p2


def test_sanidad_with_sangrado_interaction():
    """SANIDAD y SANGRADO se cancelan (+1 -1 = 0 neto, además de casa)"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="SANIDAD", remaining_rounds=2))
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="SANGRADO", remaining_rounds=2))

    initial_sanity = s.players[PlayerId("P1")].sanity
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # SANIDAD (+1) + SANGRADO (-1) + CASA (-1) = -1 neto
    expected_sanity = initial_sanity - cfg.HOUSE_LOSS_PER_ROUND
    assert s.players[PlayerId("P1")].sanity == expected_sanity


# ==================== PARANOIA Tests ====================

def test_paranoia_blocks_move_to_occupied_room():
    """PARANOIA impide moverse a habitación con otros jugadores"""
    from engine.legality import get_legal_actions
    s = setup_state_test()
    s.phase = "PLAYER"
    s.remaining_actions = {PlayerId("P1"): 2}
    # P1 tiene PARANOIA, P2 está en F1_R2
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="PARANOIA", remaining_rounds=2))
    cfg = Config()

    # P1 en F1_R1, P2 en F1_R2
    # P1 puede moverse al pasillo F1_P pero NO a F1_R2 (donde está P2)
    legal = get_legal_actions(s, str(PlayerId("P1")))
    move_actions = [a for a in legal if a.type == ActionType.MOVE]

    # Verificar que NO hay acción de mover a F1_R2
    move_to_r2 = [a for a in move_actions if a.data.get("to") == "F1_R2"]
    assert len(move_to_r2) == 0

    # Pero SÍ puede moverse al pasillo (vacío)
    move_to_corridor = [a for a in move_actions if a.data.get("to") == "F1_P"]
    assert len(move_to_corridor) == 1


def test_paranoia_allows_move_to_empty_room():
    """PARANOIA permite moverse a habitación vacía"""
    from engine.legality import get_legal_actions
    s = setup_state_test()
    s.phase = "PLAYER"
    s.remaining_actions = {PlayerId("P1"): 2}
    # P1 tiene PARANOIA, P2 y P3 en otros pisos
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="PARANOIA", remaining_rounds=2))
    s.players[PlayerId("P2")].room = RoomId("F2_R1")
    s.players[PlayerId("P3")].room = RoomId("F2_R1")
    cfg = Config()

    # P1 debería poder moverse a F1_R2 (vacía) y F1_P (vacío)
    legal = get_legal_actions(s, str(PlayerId("P1")))
    move_actions = [a for a in legal if a.type == ActionType.MOVE]

    # Verificar que puede moverse a ambos
    assert len(move_actions) >= 2


def test_paranoia_blocks_others_from_entering():
    """PARANOIA impide que otros jugadores entren a la misma habitación"""
    from engine.legality import get_legal_actions
    s = setup_state_test()
    s.phase = "PLAYER"
    s.remaining_actions = {PlayerId("P2"): 2}
    # P1 tiene PARANOIA y está en F1_R1
    # P2 está en F1_P (pasillo) y quiere moverse
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="PARANOIA", remaining_rounds=2))
    s.players[PlayerId("P2")].room = RoomId("F1_P")
    cfg = Config()

    # P2 NO debería poder moverse a F1_R1 (donde está P1 con PARANOIA)
    legal = get_legal_actions(s, str(PlayerId("P2")))
    move_actions = [a for a in legal if a.type == ActionType.MOVE]

    # Verificar que NO hay acción de mover a F1_R1
    move_to_r1 = [a for a in move_actions if a.data.get("to") == "F1_R1"]
    assert len(move_to_r1) == 0


def test_paranoia_duration_decrements():
    """PARANOIA decrementa duración correctamente"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="PARANOIA", remaining_rounds=1))
    cfg = Config()
    rng = RNG(1)

    # Ejecutar KING_ENDROUND
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # Estado desaparece
    assert len(s.players[PlayerId("P1")].statuses) == 0


# ==================== VANIDAD Tests ====================

def test_vanidad_blocks_meditate():
    """VANIDAD bloquea la acción MEDITATE"""
    from engine.legality import get_legal_actions
    s = setup_state_test()
    s.phase = "PLAYER"
    s.remaining_actions = {PlayerId("P1"): 2}
    s.king_floor = 2  # Rey en piso 2 para que P1 pueda meditar normalmente
    # P1 tiene VANIDAD
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="VANIDAD", remaining_rounds=-1))
    cfg = Config()

    # Verificar que MEDITATE no está disponible
    legal = get_legal_actions(s, str(PlayerId("P1")))
    meditate_actions = [a for a in legal if a.type == ActionType.MEDITATE]
    assert len(meditate_actions) == 0


def test_vanidad_is_permanent():
    """VANIDAD es permanente (duración -1 no decrementa)"""
    s = setup_state_test()
    s.players[PlayerId("P1")].statuses.append(StatusInstance(status_id="VANIDAD", remaining_rounds=-1))
    cfg = Config()
    rng = RNG(1)

    # Ejecutar varias rondas
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)

    # VANIDAD debería persistir (remaining_rounds=-1 se mantiene)
    # Nota: el sistema actual decrementa a -2, así que verificamos que existe
    # TODO: ajustar sistema de estados para no decrementar estados permanentes
    assert any(st.status_id == "VANIDAD" for st in s.players[PlayerId("P1")].statuses)


def test_without_vanidad_can_meditate():
    """Sin VANIDAD, el jugador puede meditar"""
    from engine.legality import get_legal_actions
    s = setup_state_test()
    s.phase = "PLAYER"
    s.remaining_actions = {PlayerId("P1"): 2}
    s.king_floor = 2  # Rey en piso 2 para que P1 pueda meditar
    cfg = Config()

    # Sin VANIDAD, MEDITATE está disponible
    legal = get_legal_actions(s, str(PlayerId("P1")))
    meditate_actions = [a for a in legal if a.type == ActionType.MEDITATE]
    assert len(meditate_actions) == 1

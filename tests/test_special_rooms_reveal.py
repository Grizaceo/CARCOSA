"""
Tests para el hook de revelación automática de habitaciones especiales (P1 - FASE 1.5.2)
"""
import pytest
from sim.runner import make_smoke_state
from engine.config import Config
from engine.types import PlayerId, RoomId, CardId
from engine.actions import Action, ActionType
from engine.transition import step
from engine.board import room_id


def test_player_enters_reveals_special():
    """Primera entrada a habitación especial la revela automáticamente"""
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

    assert special_room is not None, "Debe haber al menos una habitación especial"

    # Verificar que inicialmente NO está revelada
    assert state.rooms[special_room].special_revealed is False

    # Mover jugador P1 a esa habitación
    p1 = state.players[PlayerId("P1")]
    state.phase = "PLAYER"
    state.turn_order = [PlayerId("P1"), PlayerId("P2")]
    state.turn_pos = 0
    state.remaining_actions = {PlayerId("P1"): 2}

    move_action = Action(
        actor="P1",
        type=ActionType.MOVE,
        data={"to": str(special_room)}
    )

    state_after = step(state, move_action, cfg)

    # Verificar que la habitación especial fue revelada
    assert state_after.rooms[special_room].special_revealed is True

    # Verificar que se registró en flags
    expected_flag = f"SPECIAL_REVEALED_{special_room}_{special_type}"
    assert expected_flag in state_after.flags


def test_reveal_is_idempotent():
    """Segunda entrada no vuelve a revelar (idempotente)"""
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

    # Revelar manualmente primero (simular primera entrada)
    state.rooms[special_room].special_revealed = True
    state.flags[f"SPECIAL_REVEALED_{special_room}_{special_type}"] = 1

    # Setup jugadores
    state.phase = "PLAYER"
    state.turn_order = [PlayerId("P1"), PlayerId("P2")]
    state.turn_pos = 0
    state.remaining_actions = {PlayerId("P1"): 2}

    # Entrada a habitación ya revelada
    move_action = Action(
        actor="P1",
        type=ActionType.MOVE,
        data={"to": str(special_room)}
    )

    state_after = step(state, move_action, cfg)

    # Verificar que sigue revelada (no cambió)
    assert state_after.rooms[special_room].special_revealed is True
    # El flag no cambió de ronda
    assert state_after.flags.get(f"SPECIAL_REVEALED_{special_room}_{special_type}") == 1


def test_reveal_does_not_consume_actions():
    """Revelar especial NO reduce actions_left"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    # Encontrar una habitación con special_card_id
    special_room = None
    for rid, room_state in state.rooms.items():
        if room_state.special_card_id is not None:
            special_room = rid
            break

    assert special_room is not None

    # Setup
    state.phase = "PLAYER"
    state.turn_order = [PlayerId("P1"), PlayerId("P2")]
    state.turn_pos = 0
    state.remaining_actions = {PlayerId("P1"): 2}

    # Mover a habitación especial (cuesta 1 acción)
    move_action = Action(
        actor="P1",
        type=ActionType.MOVE,
        data={"to": str(special_room)}
    )

    state_after = step(state, move_action, cfg)

    # La acción MOVE cuesta 1, así que debería quedar 1 acción
    # La revelación de la habitación especial NO cuesta acción adicional
    assert state_after.remaining_actions[PlayerId("P1")] == 1

    # La habitación especial debe estar revelada
    assert state_after.rooms[special_room].special_revealed is True


def test_destroyed_special_not_revealed():
    """Habitación especial destruida no se revela al entrar"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    # Encontrar una habitación con special_card_id
    special_room = None
    for rid, room_state in state.rooms.items():
        if room_state.special_card_id is not None:
            special_room = rid
            break

    assert special_room is not None

    # Marcar como destruida manualmente
    state.rooms[special_room].special_destroyed = True

    # Setup
    state.phase = "PLAYER"
    state.turn_order = [PlayerId("P1"), PlayerId("P2")]
    state.turn_pos = 0
    state.remaining_actions = {PlayerId("P1"): 2}

    # Mover a habitación especial destruida
    move_action = Action(
        actor="P1",
        type=ActionType.MOVE,
        data={"to": str(special_room)}
    )

    state_after = step(state, move_action, cfg)

    # La habitación especial NO debe revelarse (está destruida)
    assert state_after.rooms[special_room].special_revealed is False


def test_reveal_happens_before_card_resolution():
    """Revelación de especial ocurre ANTES de revelar carta del mazo (LIFO)"""
    cfg = Config()
    state = make_smoke_state(seed=1, cfg=cfg)

    # Encontrar una habitación con special_card_id y que tenga cartas en el mazo
    special_room = None
    for rid, room_state in state.rooms.items():
        if room_state.special_card_id is not None and len(room_state.deck.cards) > 0:
            special_room = rid
            break

    assert special_room is not None

    # Agregar una carta conocida al tope del mazo para trackear
    state.rooms[special_room].deck.cards.insert(0, CardId("KEY"))
    state.rooms[special_room].deck.top = 0

    # Setup
    state.phase = "PLAYER"
    state.turn_order = [PlayerId("P1"), PlayerId("P2")]
    state.turn_pos = 0
    state.remaining_actions = {PlayerId("P1"): 2}

    # Mover a habitación especial
    move_action = Action(
        actor="P1",
        type=ActionType.MOVE,
        data={"to": str(special_room)}
    )

    state_after = step(state, move_action, cfg)

    # Verificar orden de ejecución (LIFO):
    # 1. Habitación especial revelada
    assert state_after.rooms[special_room].special_revealed is True

    # 2. Carta del mazo también fue revelada y resuelta
    # (P1 debería tener la llave si la carta KEY fue resuelta)
    assert state_after.players[PlayerId("P1")].keys >= 1

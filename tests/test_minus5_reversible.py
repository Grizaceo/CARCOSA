from engine.config import Config
from engine.state_factory import make_game_state
from engine.types import PlayerId
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step


def test_minus5_is_reversible_and_only_limits_while_at_minus5():
    # Evita daño extra por presencia del Rey
    cfg = Config(KING_PRESENCE_START_ROUND=99)

    rooms = [
        str(corridor_id(1)),
        str(corridor_id(2)),
        str(corridor_id(3)),
    ]

    # Dos jugadores para evitar derrota automática por "todos en -5"
    players = {
        "P1": {"room": str(corridor_id(3)), "sanity": -4},
        "P2": {"room": str(corridor_id(1)), "sanity": 3},
    }

    # Importante: forzamos que en la próxima ronda empiece P1 (si no, P1 no podría actuar legalmente)
    s = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="KING",
        king_floor=1,
        starter_pos=1,  # con 2 jugadores, _start_new_round hará (1+1)%2=0 => empieza P1
        turn_pos=1,
    )
    rng = RNG(2)

    # Fin de ronda: Casa -1 => P1 pasa de -4 a -5 (pero no pierden porque P2 no está en -5)
    s2 = step(s, Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 1}), rng, cfg)

    # CANON Fix #A: Interrupt triggered. P1 must accept consequences to proceed (or Sacrifice).
    # Test assumes they stay at -5, so they ACCEPT.
    pending = s2.flags.get("PENDING_SACRIFICE_CHECK")
    if isinstance(pending, list):
        assert pending and pending[0] == "P1"
    else:
        assert pending == "P1"
    s2 = step(s2, Action(actor="P1", type=ActionType.ACCEPT_SACRIFICE, data={}), rng, cfg)

    assert s2.phase == "PLAYER"
    assert s2.players[PlayerId("P1")].sanity == -5
    # CANON Fix #G: No reduced actions at -5. Base actions 2.
    assert s2.remaining_actions[PlayerId("P1")] == 2

    # P1 medita en pasillo: -5 -> -3 (cura 2), debe salir del estado -5
    s3 = step(s2, Action(actor="P1", type=ActionType.MEDITATE, data={}), rng, cfg)
    assert s3.players[PlayerId("P1")].sanity == -3
    assert s3.players[PlayerId("P1")].at_minus5 is False


def test_minus5_chain_queues_next_sacrifice():
    cfg = Config(KING_PRESENCE_START_ROUND=99)

    rooms = [
        str(corridor_id(1)),
        str(corridor_id(2)),
    ]

    players = {
        "P1": {"room": str(corridor_id(1)), "sanity": -5},
        "P2": {"room": str(corridor_id(2)), "sanity": -4},
    }

    s = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=1,
        turn_pos=0,
        turn_order=["P1", "P2"],
        remaining_actions={"P1": 2, "P2": 2},
    )
    s.flags["PENDING_SACRIFICE_CHECK"] = "P1"
    rng = RNG(1)

    s2 = step(s, Action(actor="P1", type=ActionType.ACCEPT_SACRIFICE, data={}), rng, cfg)

    pending = s2.flags.get("PENDING_SACRIFICE_CHECK")
    if isinstance(pending, list):
        assert pending and pending[0] == "P2"
    else:
        assert pending == "P2"
    assert s2.players[PlayerId("P2")].sanity == -4
    assert not s2.game_over

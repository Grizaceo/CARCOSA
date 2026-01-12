from engine.config import Config
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step


def test_minus5_is_reversible_and_only_limits_while_at_minus5():
    # Evita daño extra por presencia del Rey
    cfg = Config(KING_PRESENCE_START_ROUND=99)

    rooms = {
        corridor_id(1): RoomState(room_id=corridor_id(1), deck=DeckState(cards=[])),
        corridor_id(2): RoomState(room_id=corridor_id(2), deck=DeckState(cards=[])),
        corridor_id(3): RoomState(room_id=corridor_id(3), deck=DeckState(cards=[])),
    }

    # Dos jugadores para evitar derrota automática por "todos en -5"
    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=-4, room=corridor_id(2)),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=3, room=corridor_id(1)),
    }

    # Importante: forzamos que en la próxima ronda empiece P1 (si no, P1 no podría actuar legalmente)
    s = GameState(
        round=1,
        players=players,
        rooms=rooms,
        phase="KING",
        king_floor=1,
        starter_pos=1,  # con 2 jugadores, _start_new_round hará (1+1)%2=0 => empieza P1
        turn_pos=1,
    )
    rng = RNG(1)

    # Fin de ronda: Casa -1 => P1 pasa de -4 a -5 (pero no pierden porque P2 no está en -5)
    s2 = step(s, Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 1}), rng, cfg)

    assert s2.phase == "PLAYER"
    assert s2.players[PlayerId("P1")].sanity == -5
    assert s2.remaining_actions[PlayerId("P1")] == 1

    # P1 medita: -5 -> -4, debe salir del estado -5
    s3 = step(s2, Action(actor="P1", type=ActionType.MEDITATE, data={}), rng, cfg)
    assert s3.players[PlayerId("P1")].sanity == -4
    assert s3.players[PlayerId("P1")].at_minus5 is False

from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId, CardId
from engine.board import corridor_id, room_id
from engine.transition import step


def test_end_of_round_d6_2_global_sanity_loss_only():
    rng = RNG(42)

    # jugadores en piso 3, Rey en piso 1 => no reciben presencia
    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=corridor_id(3)),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=3, room=corridor_id(3)),
    }

    rooms = {
        corridor_id(1): RoomState(room_id=corridor_id(1), deck=DeckState(cards=[])),
        corridor_id(2): RoomState(room_id=corridor_id(2), deck=DeckState(cards=[])),
        corridor_id(3): RoomState(room_id=corridor_id(3), deck=DeckState(cards=[])),
        room_id(1,1): RoomState(room_id=room_id(1,1), deck=DeckState(cards=[CardId("EVENT:X")])),
    }

    s = GameState(round=2, players=players, rooms=rooms, king_floor=1, phase="KING")

    # d6=2 => todos pierden 1 adicional
    a = Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 2, "d6": 2})
    s2 = step(s, a, rng)

    # pérdidas: -1 (casa) -1 (d6=2) = -2
    assert s2.players[PlayerId("P1")].sanity == 1
    assert s2.players[PlayerId("P2")].sanity == 1
    assert s2.round == 3
    assert s2.phase == "PLAYER"

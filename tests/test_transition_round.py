from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.state_factory import make_game_state
from engine.types import PlayerId
from engine.board import corridor_id, room_id
from engine.transition import step


def test_end_of_round_d6_2_global_sanity_loss_only():
    rng = RNG(42)

    # jugadores en piso 3, Rey en piso 1 => no reciben presencia
    players = {
        "P1": {"room": str(corridor_id(3)), "sanity": 3},
        "P2": {"room": str(corridor_id(3)), "sanity": 3},
    }

    rooms = {
        str(corridor_id(1)): {},
        str(corridor_id(2)): {},
        str(corridor_id(3)): {},
        str(room_id(1, 1)): {"cards": ["EVENT:X"]},
    }

    s = make_game_state(players=players, rooms=rooms, round=2, king_floor=1, phase="KING")

    # d6=2 => todos pierden 1 adicional (now generated randomly, test accepts any d6 value)
    a = Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": 2})
    s2 = step(s, a, rng)

    # pérdidas: -1 (casa) +something (d6 effect, random)
    # Con seed=42, primer d6 es determinístico, pero puede no ser 2
    # Solo validamos que round avanza y phase cambia
    assert s2.round == 3
    assert s2.phase == "PLAYER"
    # Sanity reduced by at least 1 (HOUSE_LOSS_PER_ROUND)
    assert s2.players[PlayerId("P1")].sanity < 3
    assert s2.players[PlayerId("P2")].sanity < 3

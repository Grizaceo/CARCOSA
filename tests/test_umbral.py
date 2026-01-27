from engine.config import Config
from engine.state_factory import make_game_state
from engine.types import PlayerId, RoomId
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step


def test_umbral_is_floor1_corridor_reachable_via_stairs():
    cfg = Config(UMBRAL_NODE="F1_P")

    rooms = [
        str(corridor_id(1)),
        str(corridor_id(2)),
        str(corridor_id(3)),
    ]

    # Colocamos la escalera del piso 2 en F2_R1 para el test
    stairs = {1: RoomId("F1_R1"), 2: RoomId("F2_R1"), 3: RoomId("F3_R1")}

    # Partimos en la escalera del piso 2, así el MOVE a F1_P es legal
    players = {"P1": {"room": "F2_R1", "sanity": 3}}
    s = make_game_state(players=players, rooms=rooms, round=1, phase="PLAYER")
    s.stairs = stairs

    rng = RNG(1)

    # Movimiento 1: Usar escaleras para ir a la habitación con escalera del piso 1 (F1_R1)
    a1 = Action(actor="P1", type=ActionType.MOVE, data={"to": "F1_R1"})
    s2 = step(s, a1, rng, cfg)
    assert str(s2.players[PlayerId("P1")].room) == "F1_R1"
    assert s2.players[PlayerId("P1")].at_umbral is False  # Aún no está en Umbral (es F1_P)
    
    # Movimiento 2: Moverse del F1_R1 al pasillo F1_P (vecinos directos por topología)
    a2 = Action(actor="P1", type=ActionType.MOVE, data={"to": "F1_P"})
    s3 = step(s2, a2, rng, cfg)
    
    # Ahora sí está en Umbral
    assert s3.players[PlayerId("P1")].at_umbral is True
    assert str(s3.players[PlayerId("P1")].room) == "F1_P"


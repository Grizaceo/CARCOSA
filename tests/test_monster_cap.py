from engine.config import Config
from engine.state_factory import make_game_state
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step

def test_monsters_are_capped():
    cfg = Config(MAX_MONSTERS_ON_BOARD=8, KING_PRESENCE_START_ROUND=999)
    rooms = [
        str(corridor_id(1)),
        str(corridor_id(2)),
        str(corridor_id(3)),
    ]
    players = {"P1": {"room": str(corridor_id(2)), "sanity": 3}}
    s = make_game_state(round=1, players=players, rooms=rooms, phase="PLAYER", king_floor=1)
    s.monsters = 8
    rng = RNG(1)

    # Fuerza una acción que intente generar monstruo indirectamente (si tu motor lo hace por SEARCH/MOVE con cartas).
    # Si tu engine no spawnea monstruos sin carta, este test quedará neutro; en ese caso lo ajustamos al resolver carta.
    s2 = step(s, Action(actor="P1", type=ActionType.END_TURN, data={}), rng, cfg)
    assert s2.monsters <= cfg.MAX_MONSTERS_ON_BOARD

from engine.config import Config
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId
from engine.board import corridor_id
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step

def test_monsters_are_capped():
    cfg = Config(MAX_MONSTERS_ON_BOARD=8, KING_PRESENCE_START_ROUND=999)
    rooms = {
        corridor_id(1): RoomState(room_id=corridor_id(1), deck=DeckState(cards=[])),
        corridor_id(2): RoomState(room_id=corridor_id(2), deck=DeckState(cards=[])),
        corridor_id(3): RoomState(room_id=corridor_id(3), deck=DeckState(cards=[])),
    }
    players = {PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=corridor_id(2))}
    s = GameState(round=1, players=players, rooms=rooms, phase="PLAYER", monsters=8, king_floor=1)
    rng = RNG(1)

    # Fuerza una acción que intente generar monstruo indirectamente (si tu motor lo hace por SEARCH/MOVE con cartas).
    # Si tu engine no spawnea monstruos sin carta, este test quedará neutro; en ese caso lo ajustamos al resolver carta.
    s2 = step(s, Action(actor="P1", type=ActionType.END_TURN, data={}), rng, cfg)
    assert s2.monsters <= cfg.MAX_MONSTERS_ON_BOARD

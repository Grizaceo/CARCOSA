"""
Tests para verificar que SEARCH resuelve cartas correctamente.
Regresión: asegurar que _resolve_card_minimal no vuelva a un estado placeholder.
"""
from engine.actions import Action, ActionType
from engine.config import Config
from engine.rng import RNG
from engine.state_factory import make_game_state
from engine.types import PlayerId, RoomId, CardId
from engine.board import corridor_id
from engine.transition import step


def test_search_can_find_key():
    """Test que SEARCH en una sala con KEY la resuelve y da la llave al jugador."""
    cfg = Config(KING_PRESENCE_START_ROUND=999)
    
    # Setup: sala con KEY al inicio del mazo
    rooms = {
        str(corridor_id(1)): {},
        str(corridor_id(2)): {},
        str(corridor_id(3)): {},
        "F1_R1": {"cards": ["KEY", "EVENT:X", "MONSTER:SPIDER"]},
    }
    
    players = {
        "P1": {"room": "F1_R1", "sanity": 3, "keys": 0},
        "P2": {"room": str(corridor_id(2)), "sanity": 3, "keys": 0},
    }
    
    state = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=1,
        turn_order=["P1", "P2"],
        remaining_actions={"P1": 2, "P2": 2},
    )
    
    # P1 executes SEARCH
    action = Action(actor="P1", type=ActionType.SEARCH, data={})
    rng = RNG(1)
    state = step(state, action, rng, cfg)
    
    # Verificar que P1 ahora tiene 1 llave
    assert state.players[PlayerId("P1")].keys == 1, f"Expected 1 key, got {state.players[PlayerId('P1')].keys}"
    
    # Verificar que la carta fue revelada (top incrementó)
    assert state.rooms[RoomId("F1_R1")].deck.top == 1


def test_search_reveals_and_resolves_state():
    """Test que SEARCH resuelve cartas STATE:<id> agregando StatusInstance."""
    cfg = Config(KING_PRESENCE_START_ROUND=999)
    
    rooms = {
        str(corridor_id(1)): {},
        str(corridor_id(2)): {},
        str(corridor_id(3)): {},
        "F1_R1": {"cards": ["STATE:STUN", "EVENT:X"]},
    }
    
    players = {
        "P1": {"room": "F1_R1", "sanity": 3, "keys": 0},
        "P2": {"room": str(corridor_id(2)), "sanity": 3, "keys": 0},
    }
    
    state = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=1,
        turn_order=["P1", "P2"],
        remaining_actions={"P1": 2, "P2": 2},
    )
    
    # P1 executes SEARCH
    action = Action(actor="P1", type=ActionType.SEARCH, data={})
    rng = RNG(1)
    state = step(state, action, rng, cfg)
    
    # Verificar que P1 ahora tiene 1 status
    assert len(state.players[PlayerId("P1")].statuses) == 1
    assert state.players[PlayerId("P1")].statuses[0].status_id == "STUN"


def test_move_reveals_and_resolves_monster():
    """Test que MOVE resuelve cartas MONSTER creando MonsterState."""
    cfg = Config(MAX_MONSTERS_ON_BOARD=8, KING_PRESENCE_START_ROUND=999)
    
    rooms = {
        str(corridor_id(1)): {},
        str(corridor_id(2)): {},
        str(corridor_id(3)): {},
        "F1_R1": {"cards": ["MONSTER:SPIDER", "EVENT:X"]},
    }
    
    players = {
        "P1": {"room": str(corridor_id(1)), "sanity": 3, "keys": 0},
        "P2": {"room": str(corridor_id(2)), "sanity": 3, "keys": 0},
    }
    
    state = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=1,
        turn_order=["P1", "P2"],
        remaining_actions={"P1": 2, "P2": 2},
    )
    
    # P1 executes MOVE to F1_R1
    action = Action(actor="P1", type=ActionType.MOVE, data={"to": "F1_R1"})
    rng = RNG(1)
    state = step(state, action, rng, cfg)
    
    # Verificar que se agregó un monstruo
    assert len(state.monsters) == 1
    assert state.monsters[0].monster_id == "SPIDER"


def test_no_duplicate_keys_beyond_pool():
    """Test que no se permitan más llaves que KEYS_TOTAL."""
    cfg = Config(KEYS_TOTAL=2, KING_PRESENCE_START_ROUND=999)
    
    rooms = {
        str(corridor_id(1)): {},
        str(corridor_id(2)): {},
        str(corridor_id(3)): {},
        "F1_R1": {"cards": ["KEY", "KEY", "KEY"]},
    }
    
    players = {
        "P1": {"room": "F1_R1", "sanity": 3, "keys": 0},
        "P2": {"room": str(corridor_id(2)), "sanity": 3, "keys": 0},
    }
    
    state = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=1,
        turn_order=["P1", "P2"],
        remaining_actions={"P1": 2, "P2": 2},
    )
    
    # P1 búsqueda 3 veces
    rng = RNG(1)
    for i in range(3):
        action = Action(actor="P1", type=ActionType.SEARCH, data={})
        state = step(state, action, rng, cfg)
        if state.remaining_actions[PlayerId("P1")] <= 0:
            break
    
    # Verificar que P1 nunca supera KEYS_TOTAL (2)
    assert state.players[PlayerId("P1")].keys <= cfg.KEYS_TOTAL

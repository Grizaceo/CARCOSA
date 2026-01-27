
import pytest
from engine.state_factory import make_game_state
from engine.types import PlayerId, RoomId
from engine.actions import ActionType
from engine.config import Config
from engine.transition import step
from engine.legality import get_legal_actions

def test_yellow_doors_mechanic():
    # Setup: 2 Players in different rooms. P1 in Yellow Doors.
    rooms = {
        "F1_R1": {"special_card_id": "PUERTAS_AMARILLO", "special_revealed": True},
        "F1_R2": {},
    }
    players = {
        "P1": {"room": "F1_R1", "sanity": 5},
        "P2": {"room": "F1_R2", "sanity": 5},
    }
    s = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        king_floor=1,
        turn_order=["P1", "P2"],
        remaining_actions={"P1": 1},
    )
    s.seed = 1
    
    # Check Legality
    # P1 is active
    legal = get_legal_actions(s, "P1")
    # Should have USE_YELLOW_DOORS with target P2
    yellow_actions = [a for a in legal if a.type == ActionType.USE_YELLOW_DOORS]
    assert len(yellow_actions) == 1
    assert yellow_actions[0].data["target_player"] == "P2"
    
    # Execute Action
    action = yellow_actions[0]
    cfg = Config()
    from engine.rng import RNG
    rng = RNG(1)
    
    s_next = step(s, action, rng, cfg)
    
    # Verify Effects
    p1_next = s_next.players[PlayerId("P1")]
    p2_next = s_next.players[PlayerId("P2")]
    
    # 1. Teleport: P1 should be in P2's room (F1_R2)
    assert p1_next.room == RoomId("F1_R2")
    
    # 2. Damage: P2 should lose 1 Sanity (5 -> 4)
    assert p2_next.sanity == 4
    
    # 3. P1 Sanity unchanged (cost is action, not sanity) - verify canon rules about cost
    # Report says: "Gasta Acción: Si". Current implementation checks this.
    assert p1_next.sanity == 5


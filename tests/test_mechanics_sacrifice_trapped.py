from engine.config import Config
from engine.state import GameState, PlayerState, RoomState, DeckState, StatusInstance, MonsterState
from engine.types import PlayerId, RoomId
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.transition import step

def setup_basic_state(sanity_p1=3, sanity_p2=3):
    rooms = {
        RoomId("F1_R1"): RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=[])),
        RoomId("F1_P"): RoomState(room_id=RoomId("F1_P"), deck=DeckState(cards=[])), # Pasillo
    }
    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=sanity_p1, room=RoomId("F1_R1"), sanity_max=5),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=sanity_p2, room=RoomId("F1_R1")),
    }
    s = GameState(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=3, # Far away
        turn_pos=0,
        remaining_actions={PlayerId("P1"): 2, PlayerId("P2"): 2},
        turn_order=[PlayerId("P1"), PlayerId("P2")],
        flags={},
    )
    rng = RNG(42)
    cfg = Config()
    return s, rng, cfg

# --- SACRIFICE AND MINUS 5 TESTS ---

def test_sacrifice_behavior_transition_to_minus5():
    """
    Verifica que al entrar en -5 se pueda sacrificar.
    """
    s, rng, cfg = setup_basic_state(sanity_p1=-5, sanity_p2=3)
    s.players[PlayerId("P1")].at_minus5 = True # Asumimos que ya entro
    
    # Action
    action = Action(actor="P1", type=ActionType.SACRIFICE, data={})
    
    # Pre-assertions
    assert s.players[PlayerId("P1")].sanity == -5
    
    s_new = step(s, action, rng, cfg)
    
    p1 = s_new.players[PlayerId("P1")]
    # Check Reset
    assert p1.sanity == 0, "Sacrifice should reset sanity to 0"
    assert p1.at_minus5 is False, "Should remove -5 status"
    
    # Check Cost (Max Sanity reduced)
    assert p1.sanity_max == 4, "Cost: should reduce max sanity by 1 (was 5)"

# --- TRAPPED TESTS ---

def test_trapped_legality():
    s, rng, cfg = setup_basic_state()
    p1 = s.players[PlayerId("P1")]
    
    # Case 1: NOT Trapped -> Action Illegal (not generated)
    from engine.legality import get_legal_actions
    acts = get_legal_actions(s, "P1")
    assert not any(a.type == ActionType.ESCAPE_TRAPPED for a in acts), "Should not be legal if not trapped"
    
    # Case 2: Trapped -> Action Legal AND Blocking
    p1.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=2))
    acts_trapped = get_legal_actions(s, "P1")
    
    # Check Escape is present
    assert any(a.type == ActionType.ESCAPE_TRAPPED for a in acts_trapped), "Should be legal if trapped"
    
    # Check others are BLOCKED (e.g. MOVE, SEARCH)
    assert not any(a.type == ActionType.MOVE for a in acts_trapped), "MOVES should be blocked when Trapped"
    assert not any(a.type == ActionType.SEARCH for a in acts_trapped), "SEARCH should be blocked when Trapped"
    
    allowed_types = {ActionType.ESCAPE_TRAPPED, ActionType.SACRIFICE, ActionType.END_TURN}
    action_types = {a.type for a in acts_trapped}
    for at in action_types:
        assert at in allowed_types, f"Illegal action type allowed while TRAPPED: {at}"

def test_trapped_resolution_success():
    """
    Atrapado: consume accion + remueve estado con umbral (d6 + sanity >= 3).
    """
    s, rng, cfg = setup_basic_state()
    p1 = s.players[PlayerId("P1")]
    p1.sanity = 0 # Baseline sanity to make formula easy (d6 >= 3)
    p1.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=2))
    
    # Add monster to room
    s.monsters.append(MonsterState(monster_id="M1", room=p1.room))
    
    class MockRNG(RNG):
        def randint(self, a, b):
            return 3 # 3 + 0 = 3 (Success)
            
    mock_rng = MockRNG(0)
    
    action = Action(actor="P1", type=ActionType.ESCAPE_TRAPPED, data={})
    
    s_new = step(s, action, mock_rng, cfg)
    
    p1_new = s_new.players[PlayerId("P1")]
    
    # Check Status Removed
    assert not any(st.status_id == "TRAPPED" for st in p1_new.statuses), "Trapped status should be removed on success"
    
    # Check Action Cost
    # Initial was 2. Éxito: queda con 1 acción restante (gastó 1)
    assert s_new.remaining_actions[PlayerId("P1")] == 1, "Should have 1 action remaining after success"
    
    # Check Monster Stun - Monster queda stunned 1 turno
    monster = s_new.monsters[0]
    assert monster.stunned_remaining_rounds == 1, "Monster should be stunned for 1 round"


def test_trapped_resolution_failure():
    s, rng, cfg = setup_basic_state()
    p1 = s.players[PlayerId("P1")]
    p1.sanity = 0 # Baseline
    p1.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=2))
    
    class MockRNGFail(RNG):
        def randint(self, a, b):
            return 2 # 2 + 0 = 2 < 3 (Failure)
            
    mock_rng = MockRNGFail(0)
    
    action = Action(actor="P1", type=ActionType.ESCAPE_TRAPPED, data={})
    s_new = step(s, action, mock_rng, cfg)
    
    p1_new = s_new.players[PlayerId("P1")]
    
    # Status Persists
    assert any(st.status_id == "TRAPPED" for st in p1_new.statuses), "Trapped status should persist on failure"
    
    # CANON: Fallo termina turno inmediatamente (0 acciones)
    assert s_new.remaining_actions[PlayerId("P1")] == 0, "Failure should end turn immediately (0 actions)"

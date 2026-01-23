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
    Verifica que al entrar en -5 (y elegir sacrificio, si fuese automatico o accion),
    se evite el daño a otros y se aplique el costo.
    NOTA: Segun PO.4 (implementado) entrar a -5 es automatico.
    Pero la tarea pide "Sacrificio: ... resetea cordura + aplica cost".
    Asumimos que 'Sacrifice' es una ACCION que se toma UNA VEZ EN -5 para 'salir' de ese estado
    reseteando a 0, pagando costo, y evitando que ESTE jugador cause mas problemas (o quizas previniendo daño previo?)
    
    Re-leendo prompt: "Sacrificio: evita daño a otros + resetea cordura + aplica costo."
    Si P1 entra a -5, otros pierden 1 sanity (ya implementado).
    Quizas 'Sacrificio' es la opcion de 'Rendirse' o 'Aceptar destino' para VOLVER??
    O es una reaccion inmediata?
    Asumiremos el flujo:
    1. Player moves to -5.
    2. Player uses SACRIFICE action (legal at -5).
    3. Effect: Sanity -> 0, SanityMax -> -1 (Cost), No damage to others (this part might be retroactive or prevent future??
       "evita daño a otros" might mean "stops the aura of damage"? 
       Or maybe it replaces the entry event? But entry event is automatic.
       Let's assume "Sacrifice" is an action you do INSTAD of suffering/causing more.
       But since entry is instant, maybe it REVERSES it?
       for the test, we checking:
       - Starts at -5
       - Actions SACRIFICE
       - Ends at 0 sc
       - Sanity Max reduced
       - (Implicitly) Player is functional again.
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
    
    # Case 2: Trapped -> Action Legal
    p1.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=2))
    acts_trapped = get_legal_actions(s, "P1")
    assert any(a.type == ActionType.ESCAPE_TRAPPED for a in acts_trapped), "Should be legal if trapped"

def test_trapped_resolution_success():
    """
    Atrapado: consume accion + remueve estado con umbral (d6 >= 3).
    Exito tambien STUN al monstruo.
    """
    s, rng, cfg = setup_basic_state()
    p1 = s.players[PlayerId("P1")]
    p1.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=2))
    
    # Add monster to room
    s.monsters.append(MonsterState(monster_id="M1", room=p1.room))
    
    # Force RNG success (>= 3)
    # Action consume 1 action check?
    # We rely on step logic for cost.
    
    # Mock RNG to return 3
    # Step() creates a clone of RNG?? No, it uses it.
    # Note: transition.py calls rng.randint(1,6) for things.
    # We need to ensure the FIRST call for this action is our d6.
    # assuming logic: d6 = rng.randint(1,6)
    
    # We need a predictable RNG or mock.
    # In engine/transition.py, we pass rng.
    # Let's peek at `rng.py`... standard random.
    # We can seed it.
    rng = RNG(100) 
    # Let's verify what 100 gives for d6? We can't easily without running it.
    # Instead, we will loop until we find a seed or just trust 'average' probability 
    # OR better: run in a loop until success if we were simulating, but here we want determinism.
    # We will just verify behavior IF implementation connects d6 correctly.
    # For a PR that FAILS, we expect assertions to fail regardless of RNG because logic isn't there.
    # BUT, to write a GOOD test, we should control RNG.
    # Let's subclass RNG for the test.
    
    class MockRNG(RNG):
        def randint(self, a, b):
            return 3 # Success
            
    mock_rng = MockRNG(0)
    
    action = Action(actor="P1", type=ActionType.ESCAPE_TRAPPED, data={})
    
    s_new = step(s, action, mock_rng, cfg)
    
    p1_new = s_new.players[PlayerId("P1")]
    
    # Check Status Removed
    assert not any(st.status_id == "TRAPPED" for st in p1_new.statuses), "Trapped status should be removed on success"
    
    # Check Action Cost
    # Initial was 2. Éxito: queda con 1 acción restante (gastó 1)
    assert s_new.remaining_actions[PlayerId("P1")] == 1, "Should have 1 action remaining after success"
    
    # Check Monster Stun - CANON: Monster queda stunned 1 turno
    monster = s_new.monsters[0]
    assert monster.stunned_remaining_rounds == 1, "Monster should be stunned for 1 round"


def test_trapped_resolution_failure():
    s, rng, cfg = setup_basic_state()
    p1 = s.players[PlayerId("P1")]
    p1.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=2))
    
    class MockRNGFail(RNG):
        def randint(self, a, b):
            return 2 # Failure (<3)
            
    mock_rng = MockRNGFail(0)
    
    action = Action(actor="P1", type=ActionType.ESCAPE_TRAPPED, data={})
    s_new = step(s, action, mock_rng, cfg)
    
    p1_new = s_new.players[PlayerId("P1")]
    
    # Status Persists
    assert any(st.status_id == "TRAPPED" for st in p1_new.statuses), "Trapped status should persist on failure"
    
    # CANON: Fallo termina turno inmediatamente (0 acciones)
    assert s_new.remaining_actions[PlayerId("P1")] == 0, "Failure should end turn immediately (0 actions)"

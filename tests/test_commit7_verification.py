from engine.state import DeckState
from engine.state_factory import make_game_state, make_room
from engine.transition import step, _check_defeat
from engine.actions import Action, ActionType
from engine.types import PlayerId, CardId
from engine.config import Config
from engine.board import corridor_id, room_id

def test_motemey_rejected_card_goes_bottom():
    """Verifica que la carta rechazada en Motemey va al fondo del mazo."""
    deck = DeckState(cards=[CardId("C1"), CardId("C2"), CardId("C3")])
    # Setup Motemey room
    rid = room_id(1, 1)
    rooms = {str(rid): {"special_card_id": "MOTEMEY", "special_revealed": True}}

    s = make_game_state(round=1, players={"P1": {"room": str(rid), "sanity": 5}}, rooms=rooms)
    s.motemey_deck = deck
    s.pending_motemey_choice = {
        "P1": [CardId("C1"), CardId("C2")] # C1, C2 drawn. Top should be 2.
    }
    deck.top = 2
    cfg = Config()

    # Eligimos índice 0 (C1). C2 debe ir al fondo.
    action = Action(actor="P1", type=ActionType.USE_MOTEMEY_BUY_CHOOSE, data={"chosen_index": 0})
    s2 = step(s, action, None, cfg)

    # C1 en objetos (si implementado) o hand
    assert "C1" in s2.players[PlayerId("P1")].objects
    
    # C2 debe estar al fondo del mazo
    # El mazo original era [C1, C2, C3].
    # C1, C2 drawn. Restan C3.
    # Put bottom C2 -> [C1, C2, C3, C2] logically?
    # Engine put_bottom implementation: inserts at end?
    # Let's check DeckState logic. usually appends.
    # Since we assume C1, C2 were technically "removed" from availability by draw_top (top+=2).
    # If put_bottom appends C2, and top is 2.
    # Cards: [C1, C2, C3, C2].
    # Remaining: C3, C2.
    # top should be 2.
    
    final_deck = s2.motemey_deck
    assert final_deck.cards[-1] == "C2"
    # assert len(final_deck.cards) == 4 # Falla por compactación (remueve usados)
    # Tras compactación: [C1, C2] removidos (estaban en index 0, 1). Quedaba [C3].
    # Se agrega C2 al fondo -> [C3, C2]. Len 2.
    assert len(final_deck.cards) == 2
    assert final_deck.remaining() == 2
    assert final_deck.top == 0
    
def test_lethal_chamber_revealed_increases_key_pool():
    """
    Verifica que si la Cámara Letal está revelada, el pool de llaves aumenta a 7.
    Derrota si <= 3 llaves disponibles.
    
    Caso base: KEYS_TOTAL = 6.
    Keys destroyed = 3. Available = 3. -> DERROTA (All minus 5 check is separate).
    Condition 2: <= 3 keys available.
    
    Caso Camara: KEYS_TOTAL = 7.
    Keys destroyed = 3. Available = 4. -> NO DERROTA.
    """
    s = make_game_state(players={"P1": {"room": str(corridor_id(1)), "sanity": 5}}, rooms=[str(corridor_id(1))])
    s.keys_destroyed = 3
    cfg = Config()
    
    # Caso 1: Sin cámara letal revelada
    # _check_defeat returns True if defeat
    assert _check_defeat(s, cfg) == True
    
    # Caso 2: Cámara letal revelada
    # Setup room
    rid = room_id(1, 1)
    s.rooms[rid] = make_room(str(rid), special_card_id="CAMARA_LETAL", special_revealed=True)
    
    # Debe ser False (Victoria/Derrota check returns True if GAME OVER)
    # If defeat condition met -> True.
    # Here, 7 total - 3 destroyed = 4 available. > 3. So NOT defeat.
    assert _check_defeat(s, cfg) == False

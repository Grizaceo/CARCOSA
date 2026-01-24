
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState, StatusInstance
from engine.types import PlayerId, RoomId
from engine.actions import Action, ActionType, Action
from engine.transition import step, _advance_turn_or_king, _start_new_round
from engine.config import Config
from engine.rng import RNG
from engine.legality import get_legal_actions

def make_state():
    # Setup P1 and P2 in Taberna (F1_R1)
    rooms = {
        RoomId("F1_R1"): RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=[]), special_card_id="TABERNA", special_revealed=True),
        RoomId("F1_R2"): RoomState(room_id=RoomId("F1_R2"), deck=DeckState(cards=[])),
        RoomId("F1_R3"): RoomState(room_id=RoomId("F1_R3"), deck=DeckState(cards=[])),
    }
    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=RoomId("F1_R1")),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=3, room=RoomId("F1_R1")),
    }
    s = GameState(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        turn_order=[PlayerId("P1"), PlayerId("P2")],
        remaining_actions={PlayerId("P1"): 2, PlayerId("P2"): 2},
        turn_pos=0, # P1
        starter_pos=0 # P1 starts R1
    )
    return s

def test_taberna_reset_per_turn():
    s = make_state()
    cfg = Config()
    rng = RNG(0)
    
    # --- P1 Start ---
    # Verificar Taberna legal
    acts = get_legal_actions(s, "P1")
    assert any(a.type == ActionType.USE_TABERNA_ROOMS for a in acts)
    
    # Use Taberna
    action = Action(actor="P1", type=ActionType.USE_TABERNA_ROOMS, data={"room_a": "F1_R2", "room_b": "F1_R3"})
    s = step(s, action, rng, cfg)
    
    # Verificar Taberna blocked (ya usada)
    acts = get_legal_actions(s, "P1")
    assert not any(a.type == ActionType.USE_TABERNA_ROOMS for a in acts)
    assert s.taberna_used_this_turn[PlayerId("P1")] is True
    
    # End P1 turn manually (consume actions)
    s.remaining_actions[PlayerId("P1")] = 0
    # Auto-advance happens inside step if actions <= 0? Yes if last step consumed.
    # But if we manually set 0, we need to call advance manually or step END_TURN.
    # Let's verify who is active.
    # Step logic calls _advance_turn_or_king if remaining_actions <= 0.
    # But Taberna costs 0 actions. Remaining is still 2.
    # P1 ends turn
    s = step(s, Action(actor="P1", type=ActionType.END_TURN, data={}), rng, cfg)
    
    # --- P2 Turn ---
    assert s.turn_order[s.turn_pos] == PlayerId("P2")
    
    # P2 uses Taberna
    acts = get_legal_actions(s, "P2")
    assert any(a.type == ActionType.USE_TABERNA_ROOMS for a in acts)
    
    s = step(s, Action(actor="P2", type=ActionType.USE_TABERNA_ROOMS, data={"room_a": "F1_R2", "room_b": "F1_R3"}), rng, cfg)
    assert s.taberna_used_this_turn[PlayerId("P2")] is True
    
    # P2 ends turn
    s = step(s, Action(actor="P2", type=ActionType.END_TURN, data={}), rng, cfg)
    
    # --- End of Round / King Phase ---
    assert s.phase == "KING"
    # King Action
    s = step(s, Action(actor="KING", type=ActionType.KING_ENDROUND, data={}), rng, cfg)
    
    # --- Round 2 Start ---
    # Starter shifts to P2 (Round 2 starter = Round 1 starter + 1 = P2)
    assert s.round == 2
    assert s.starter_pos == 1
    assert s.turn_order[s.starter_pos] == PlayerId("P2")
    assert s.turn_pos == 1 # Starts with P2
    
    # P2 should be fresh (reset taberna)
    # Check flag is cleared for P2
    assert PlayerId("P2") not in s.taberna_used_this_turn
    
    # P2 acts and uses taberna again
    s = step(s, Action(actor="P2", type=ActionType.USE_TABERNA_ROOMS, data={"room_a": "F1_R2", "room_b": "F1_R3"}), rng, cfg)
    assert s.taberna_used_this_turn[PlayerId("P2")] is True
    s = step(s, Action(actor="P2", type=ActionType.END_TURN, data={}), rng, cfg)
    
    # --- Round 2 P1 Turn ---
    # Now it's P1's turn
    assert s.turn_order[s.turn_pos] == PlayerId("P1")
    
    # P1 should be fresh (reset taberna)
    assert PlayerId("P1") not in s.taberna_used_this_turn
    acts = get_legal_actions(s, "P1")
    assert any(a.type == ActionType.USE_TABERNA_ROOMS for a in acts)
    
    # P1 uses Taberna
    s = step(s, Action(actor="P1", type=ActionType.USE_TABERNA_ROOMS, data={"room_a": "F1_R2", "room_b": "F1_R3"}), rng, cfg)
    assert s.taberna_used_this_turn[PlayerId("P1")] is True
    

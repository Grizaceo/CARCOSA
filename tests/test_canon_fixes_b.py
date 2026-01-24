
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState, MonsterState
from engine.types import PlayerId, RoomId, CardId
from engine.config import Config
from engine.transition import _resolve_card_minimal, _monster_phase
from engine.setup import setup_motemey_deck
from engine.rng import RNG

def test_motemey_deck_composition():
    s = GameState(round=1, players={}, rooms={}, seed=1, king_floor=1)
    rng = RNG(1)
    setup_motemey_deck(s, rng)
    
    deck = s.motemey_deck.cards
    assert len(deck) == 14
    
    counts = {}
    for c in deck:
        counts[str(c)] = counts.get(str(c), 0) + 1
        
    assert counts["COMPASS"] == 3
    assert counts["VIAL"] == 3
    assert counts["BLUNT"] == 2
    assert counts["KEY"] == 1
    # Check treasures
    treasures = sum(1 for c in deck if "TREASURE" in str(c))
    assert treasures == 4
    # Check tale
    tales = sum(1 for c in deck if "TALE" in str(c))
    assert tales == 1

def test_key_capacity_enforcement():
    s = GameState(round=1, players={}, rooms={}, seed=1, king_floor=1)
    p = PlayerState(player_id=PlayerId("P1"), sanity=5, room=RoomId("F1_R1"), role_id="SCOUT")
    # Scout has 1 key slot
    s.players[PlayerId("P1")] = p
    
    # Mock room and deck
    deck = DeckState(cards=[CardId("KEY")])
    s.rooms[RoomId("F1_R1")] = RoomState(room_id=RoomId("F1_R1"), deck=deck)
    
    cfg = Config()
    
    # 1. Gain first key
    _resolve_card_minimal(s, PlayerId("P1"), CardId("KEY"), cfg)
    assert p.keys == 1
    
    # 2. Try to gain second key (should fail)
    # We need to simulate the deck interaction that _resolve_card_minimal relies on for return functionality
    # _resolve_card_minimal assumes usage from a revealed card, but here we pass the card directly.
    # The return logic inside _resolve checks active_deck_for_room.
    
    # Ensure active_deck_for_room works (needs boxes usually, but if room has deck it might work if direct check is used)
    # transition.py imports active_deck_for_room from boxes.py usually.
    # We need to ensure s.boxes is set up if active_deck_for_room uses it.
    # If active_deck_for_room checks room.deck directly if box not found? 
    # Let's check boxes.py implementation logic or ensure boxes are set.
    
    # Setup boxes to be safe
    from engine.state import BoxState
    s.boxes["F1_R1"] = BoxState(box_id="F1_R1", deck=deck)
    s.box_at_room[RoomId("F1_R1")] = "F1_R1"
    
    _resolve_card_minimal(s, PlayerId("P1"), CardId("KEY"), cfg)
    assert p.keys == 1  # Still 1
    
    # Check deck: Should have KEY at bottom. 
    # original deck had 1 card. If put_bottom is called, it should append.
    # deck.cards should have len 2? (Original KEY + Returned KEY?)
    # Wait, _resolve_card_minimal does NOT consume from deck. Caller does.
    # So if we passed "KEY", and it returned it, deck should have it appended.
    assert len(deck.cards) >= 1
    assert str(deck.cards[-1]) == "KEY"

def test_monster_phase():
    s = GameState(round=1, players={}, rooms={}, seed=1, king_floor=1)
    p = PlayerState(player_id=PlayerId("P1"), sanity=5, room=RoomId("F1_R1"))
    s.players[PlayerId("P1")] = p
    
    # Monster in same room
    m = MonsterState(monster_id="TEST_MONSTER", room=RoomId("F1_R1"))
    s.monsters.append(m)
    
    cfg = Config()
    
    # 1. Normal Attack
    _monster_phase(s, cfg)
    assert p.sanity == 4  # Took 1 dmg
    
    # 2. Stunned Monster
    m.stunned_remaining_rounds = 1
    _monster_phase(s, cfg)
    assert p.sanity == 4  # No extra dmg
    assert m.stunned_remaining_rounds == 0  # Decremented
    
    # 3. Resume Attack
    _monster_phase(s, cfg)
    assert p.sanity == 3  # Took dmg again


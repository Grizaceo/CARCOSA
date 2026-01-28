
import pytest
from engine.state import MonsterState
from engine.state_factory import make_game_state, make_room
from engine.types import PlayerId, RoomId
from engine.config import Config
from engine.rng import RNG
from engine.setup import setup_canonical_deck
from engine.transition import _resolve_card_minimal, _start_new_round
from engine.objects import use_object


class TestOmens:
    
    def test_canonical_deck_count(self):
        """Verify deck has 108 cards total across all rooms."""
        cfg = Config()
        rng = RNG(seed=42)
        s = make_game_state(round=1, players={}, rooms=[])
        
        setup_canonical_deck(s, rng)
        
        total_cards = 0
        for rid, room in s.rooms.items():
            if room.deck:
                total_cards += len(room.deck.cards)
                
        assert total_cards == 108, f"Expected 108 cards, got {total_cards}"
        
        # Verify specific counts (sample)
        all_cards = []
        for rid, room in s.rooms.items():
            if room.deck:
                all_cards.extend(room.deck.cards)
        
        setup_canonical_deck(s, rng)
        
        total_cards = 0
        for rid, room in s.rooms.items():
            if room.deck:
                total_cards += len(room.deck.cards)
                
        assert total_cards == 108, f"Expected 108 cards, got {total_cards}"
        
        # Verify specific counts (sample)
        all_cards = []
        for rid, room in s.rooms.items():
            if room.deck:
                all_cards.extend(room.deck.cards)
                
        omens = [c for c in all_cards if str(c).startswith("OMEN:")]
        assert len(omens) == 4, f"Expected 4 Omens, got {len(omens)}"
        assert "OMEN:ARAÑA" in omens
        assert "OMEN:DUENDE" in omens

    class MockRNG:
        def __init__(self, d6_val=3):
            self.d6_val = d6_val
        def randint(self, a, b):
            return self.d6_val
        def choice(self, seq):
            if not seq: return None
            return seq[0]

    def test_omen_spider_logic(self):
        """Test Spider Omen Logic: Low Roll -> Spider, High Roll -> Baby Spider."""
        cfg = Config()
        
        # Case 1: Low Roll (0-1) -> Big Spider
        rng_low = self.MockRNG(d6_val=1)
        
        # Setup low sanity player (total <= 1)
        p_low = {"room": "F1_R1", "sanity": -2}
        s = make_game_state(round=1, players={"p1": p_low}, rooms=["F1_R1"])
        s.rooms[RoomId("F1_R1")] = make_room("F1_R1")
        
        # 1 + (-2) = -1 -> Low -> Big Spider
        _resolve_card_minimal(s, PlayerId("p1"), "OMEN:ARAÑA", cfg, rng_low)
        
        assert len(s.monsters) == 1
        assert "SPIDER" in s.monsters[0].monster_id
        assert "BABY" not in s.monsters[0].monster_id
        assert not s.flags.get("SKIP_TURN_p1")
        
        # Case 2: High Roll (2+) -> Baby Spider + Skip Turn
        rng_high = self.MockRNG(d6_val=6)
        s2 = make_game_state(round=1, players={"p1": {"room": "F1_R1", "sanity": 5}}, rooms=["F1_R1"])
        s2.rooms[RoomId("F1_R1")] = make_room("F1_R1")
        
        _resolve_card_minimal(s2, PlayerId("p1"), "OMEN:ARAÑA", cfg, rng_high)
        
        assert len(s2.monsters) == 1
        assert "BABY_SPIDER" in s2.monsters[0].monster_id
        assert s2.flags.get("SKIP_TURN_p1") is True


    def test_baby_spider_stun_death(self):
        """Baby Spider dies if stunned (e.g. by BLUNT)."""
        cfg = Config()
        rng = RNG(seed=1)
        s = make_game_state(round=1, players={"p1": {"room": "F1_R1", "sanity": 5, "objects": ["BLUNT"]}}, rooms=["F1_R1"])
        
        # Add Baby Spider in same room
        baby = MonsterState(monster_id="MONSTER:BABY_SPIDER", room=RoomId("F1_R1"))
        s.monsters.append(baby)
        
        assert len(s.monsters) == 1
        
        # Use Blunt
        use_object(s, PlayerId("p1"), "BLUNT", cfg, rng)
        
        # Baby should be dead (removed)
        assert len(s.monsters) == 0

    def test_ice_servant_action_cap(self):
        """Ice Servant limits actions on floor to 1."""
        cfg = Config()
        rng = RNG(seed=1)
        s = make_game_state(round=1, players={"p1": {"room": "F1_R1", "sanity": 5}}, rooms=["F1_R1"], turn_order=["p1"])
        s.starter_pos = 0 # manually set
        
        # Add Ice Servant
        servant = MonsterState(monster_id="MONSTER:ICE_SERVANT", room=RoomId("F1_R2"))
        s.monsters.append(servant)
        
        # Normal actions (should be 2 normally)
        # Run start of round logic
        _start_new_round(s, cfg)
        
        # Check actions
        assert s.remaining_actions[PlayerId("p1")] == 1, "Should be capped to 1 by Ice Servant"
        
        # Move servant to other floor
        servant.room = RoomId("F2_R1")
        _start_new_round(s, cfg)
        assert s.remaining_actions[PlayerId("p1")] == 2, "Should be 2 if servant is on other floor"

    def test_omen_duende_logic(self):
        """Duende: Low (0-1) -> Spawn, High (2+) -> Lose Object."""
        cfg = Config()
        
        # Case 1: Low (0-1) -> Spawn (steals objects)
        rng_low = self.MockRNG(d6_val=1)
        s = make_game_state(round=1, players={"p1": {"room": "F1_R1", "sanity": 0, "objects": ["COMPASS"]}}, rooms=["F1_R1"])
        s.rooms[RoomId("F1_R1")] = make_room("F1_R1")
        
        _resolve_card_minimal(s, PlayerId("p1"), "OMEN:DUENDE", cfg, rng_low)
        
        assert len(s.monsters) == 1
        assert "DUENDE" in s.monsters[0].monster_id
        assert s.players[PlayerId("p1")].objects == []  # stolen
        
        # Case 2: High (2+) -> Lose Object
        rng_high = self.MockRNG(d6_val=2)
        s2 = make_game_state(round=1, players={"p1": {"room": "F1_R1", "sanity": 0, "objects": ["COMPASS"]}}, rooms=["F1_R1"])
        s2.rooms[RoomId("F1_R1")] = make_room("F1_R1")
        
        _resolve_card_minimal(s2, PlayerId("p1"), "OMEN:DUENDE", cfg, rng_high)
        
        assert len(s2.monsters) == 0  # No spawn on high
        assert len(s2.players[PlayerId("p1")].objects) == 0

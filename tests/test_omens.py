
import pytest
from engine.state import GameState, PlayerState, DeckState, MonsterState, RoomState
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
        s = GameState(round=1, players={})
        
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

    def test_omen_spider_progression(self):
        """Test Spider Omen Logic: 0-1 -> Spider, 2+ -> Baby Spider."""
        cfg = Config()
        rng = RNG(seed=1)
        p1 = PlayerState(player_id=PlayerId("p1"), room=RoomId("F1_R1"), sanity=5)
        s = GameState(round=1, players={PlayerId("p1"): p1})
        s.rooms[RoomId("F1_R1")] = RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=[]))
        
        # 1st Omen: ARAÑA
        # Should spawn SPIDER
        _resolve_card_minimal(s, PlayerId("p1"), "OMEN:ARAÑA", cfg, rng)
        
        # Check monster count
        assert len(s.monsters) == 1
        assert "SPIDER" in s.monsters[0].monster_id
        assert "BABY" not in s.monsters[0].monster_id
        
        # Check flag
        assert s.flags["OMEN_REVEALED_COUNT_ARAÑA"] == 1
        
        # 2nd Omen: ARAÑA (Simulate finding another one)
        # Should spawn SPIDER? No, rule says if ALREADY EXISTS, discard.
        # So effectively nothing happens (no new monster).
        _resolve_card_minimal(s, PlayerId("p1"), "OMEN:ARAÑA", cfg, rng)
        assert len(s.monsters) == 1 # Still 1
        assert s.flags["OMEN_REVEALED_COUNT_ARAÑA"] == 2
        
        # 3rd Omen: ARAÑA (Count 3, so index 2+)
        # Should spawn BABY SPIDER
        _resolve_card_minimal(s, PlayerId("p1"), "OMEN:ARAÑA", cfg, rng)
        assert len(s.monsters) == 2
        
        # Identify second monster
        m2 = s.monsters[1]
        assert "BABY_SPIDER" in m2.monster_id

    def test_baby_spider_stun_death(self):
        """Baby Spider dies if stunned (e.g. by BLUNT)."""
        cfg = Config()
        rng = RNG(seed=1)
        p1 = PlayerState(player_id=PlayerId("p1"), room=RoomId("F1_R1"), objects=["BLUNT"], sanity=5)
        s = GameState(round=1, players={PlayerId("p1"): p1})
        
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
        p1 = PlayerState(player_id=PlayerId("p1"), room=RoomId("F1_R1"), sanity=5)
        s = GameState(round=1, players={PlayerId("p1"): p1}, turn_order=[PlayerId("p1")])
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

    def test_omen_duende_progression(self):
        """Duende: 0-1 -> Spawn, 2+ -> Lose Object."""
        cfg = Config()
        rng = RNG(seed=1)
        p1 = PlayerState(player_id=PlayerId("p1"), room=RoomId("F1_R1"), objects=["COMPASS"], sanity=5)
        s = GameState(round=1, players={PlayerId("p1"): p1})
        s.rooms[RoomId("F1_R1")] = RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=[]))
        
        # 1st: Spawn
        _resolve_card_minimal(s, PlayerId("p1"), "OMEN:DUENDE", cfg, rng)
        assert len(s.monsters) == 1
        assert "DUENDE" in s.monsters[0].monster_id
        
        # 3rd (Skip 2nd for brevity, assume count=3 triggers 2+)
        s.flags["OMEN_REVEALED_COUNT_DUENDE"] = 2 # Pretend 2 already seen (so next is 3rd)
        _resolve_card_minimal(s, PlayerId("p1"), "OMEN:DUENDE", cfg, rng)
        
        # Should lose object
        assert len(p1.objects) == 0, "Should have lost COMPASS"

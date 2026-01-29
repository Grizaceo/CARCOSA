"""
Tests para el sistema de memoria de cartas.
"""
import pytest
from sim.memory import (
    CardMemory, BotMemory, TeamMemory,
    card_priority, create_team_memory, create_bot_memories,
    PRIORITY_KEY, PRIORITY_MONSTER, PRIORITY_EVENT, MEMORY_DECAY_ROUNDS
)


class TestCardPriority:
    """Tests para priorización de cartas."""
    
    def test_key_has_highest_priority(self):
        assert card_priority("KEY_1") == PRIORITY_KEY
        assert card_priority("LLAVE_DORADA") == PRIORITY_KEY
    
    def test_monster_has_high_priority(self):
        assert card_priority("MONSTER_SPIDER") == PRIORITY_MONSTER
        assert card_priority("ARAÑA_GIGANTE") == PRIORITY_MONSTER
    
    def test_event_has_low_priority(self):
        assert card_priority("EVENT_FIRE") == PRIORITY_EVENT


class TestCardMemory:
    """Tests para memoria de carta individual."""
    
    def test_age_increments(self):
        card = CardMemory(card_id="KEY_1", box_id="F1_R1", position_in_deck=0, priority=1)
        assert card.rounds_since_seen == 0
        card.age()
        assert card.rounds_since_seen == 1
    
    def test_expires_after_decay(self):
        card = CardMemory(card_id="KEY_1", box_id="F1_R1", position_in_deck=0, priority=1)
        for _ in range(MEMORY_DECAY_ROUNDS + 1):
            card.age()
        assert card.is_expired() is True


class TestBotMemory:
    """Tests para memoria individual de bot."""
    
    def test_can_add_to_empty_slots(self):
        bot = BotMemory(player_id="P1", max_slots=2)
        card = CardMemory(card_id="KEY_1", box_id="F1_R1", position_in_deck=0, priority=PRIORITY_KEY)
        assert bot.can_add(card) is True
    
    def test_add_memory_succeeds(self):
        bot = BotMemory(player_id="P1", max_slots=2)
        card = CardMemory(card_id="KEY_1", box_id="F1_R1", position_in_deck=0, priority=PRIORITY_KEY)
        replaced = bot.add_memory(card)
        assert replaced is None
        assert len(bot.remembered_cards) == 1
    
    def test_key_replaces_event(self):
        """KEY de mayor prioridad reemplaza EVENT de menor prioridad."""
        bot = BotMemory(player_id="P1", max_slots=1)
        
        event = CardMemory(card_id="EVENT_1", box_id="F1_R1", position_in_deck=0, priority=PRIORITY_EVENT)
        bot.add_memory(event)
        
        key = CardMemory(card_id="KEY_1", box_id="F1_R2", position_in_deck=0, priority=PRIORITY_KEY)
        replaced = bot.add_memory(key)
        
        assert replaced == event
        assert len(bot.remembered_cards) == 1
        assert bot.remembered_cards[0].card_id == "KEY_1"
    
    def test_event_does_not_replace_key(self):
        """EVENT de menor prioridad NO reemplaza KEY."""
        bot = BotMemory(player_id="P1", max_slots=1)
        
        key = CardMemory(card_id="KEY_1", box_id="F1_R1", position_in_deck=0, priority=PRIORITY_KEY)
        bot.add_memory(key)
        
        event = CardMemory(card_id="EVENT_1", box_id="F1_R2", position_in_deck=0, priority=PRIORITY_EVENT)
        replaced = bot.add_memory(event)
        
        assert replaced is None  # No se reemplazó nada
        assert bot.remembered_cards[0].card_id == "KEY_1"


class TestTeamMemory:
    """Tests para memoria de equipo."""
    
    def test_share_card_adds_to_pool(self):
        team = create_team_memory()
        card = CardMemory(card_id="KEY_1", box_id="F1_R1", position_in_deck=0, priority=PRIORITY_KEY)
        team.share_card(card, from_player="P1")
        
        assert len(team.known_cards) == 1
        assert team.known_cards[0].card_id == "KEY_1"
    
    def test_optimize_assignments_distributes_cards(self):
        """Verificar que optimize_assignments distribuye entre bots."""
        team = create_team_memory()
        bots = create_bot_memories(["P1", "P2"])
        
        # Agregar 4 cartas al pool
        cards = [
            CardMemory(card_id="KEY_1", box_id="F1_R1", position_in_deck=0, priority=PRIORITY_KEY),
            CardMemory(card_id="KEY_2", box_id="F1_R2", position_in_deck=0, priority=PRIORITY_KEY),
            CardMemory(card_id="MONSTER_1", box_id="F2_R1", position_in_deck=0, priority=PRIORITY_MONSTER),
            CardMemory(card_id="EVENT_1", box_id="F2_R2", position_in_deck=0, priority=PRIORITY_EVENT),
        ]
        for card in cards:
            team.share_card(card, from_player="P1")
        
        team.optimize_assignments(bots)
        
        # Cada bot debe tener 2 cartas (max slots)
        assert len(bots["P1"].remembered_cards) == 2
        assert len(bots["P2"].remembered_cards) == 2
        
        # Las llaves deben ser recordadas primero
        all_remembered = [c.card_id for bot in bots.values() for c in bot.remembered_cards]
        assert "KEY_1" in all_remembered
        assert "KEY_2" in all_remembered
    
    def test_sync_updates_room_positions(self):
        """Verificar que sync actualiza posiciones de rooms."""
        team = create_team_memory()
        
        card = CardMemory(card_id="KEY_1", box_id="BOX_A", position_in_deck=0, priority=PRIORITY_KEY)
        team.share_card(card, from_player="P1")
        
        # Simular sync con box_at_room
        class MockState:
            box_at_room = {"F1_R1": "BOX_A", "F1_R2": "BOX_B"}
        
        team.sync_from_state(MockState())
        
        # La carta debe saber que está en F1_R1
        assert team.known_cards[0].current_room == "F1_R1"
    
    def test_get_key_rooms(self):
        """Verificar obtención de habitaciones con llaves."""
        team = create_team_memory()
        team.room_for_box = {"BOX_A": "F1_R1", "BOX_B": "F1_R2"}
        
        key1 = CardMemory(card_id="KEY_1", box_id="BOX_A", position_in_deck=0, priority=PRIORITY_KEY)
        key1.current_room = "F1_R1"
        team.share_card(key1, from_player="P1")
        
        rooms = team.get_key_rooms()
        assert "F1_R1" in rooms

"""
Tests para el sistema de roles.
"""
import pytest
from engine.state_factory import make_game_state, make_player
from engine.types import PlayerId
from engine.config import Config
from engine.legality import get_legal_actions
from engine.actions import ActionType
from engine.roles import (
    get_role, get_sanity_max, get_key_slots, get_object_slots, get_starting_items,
    has_ability, blocks_meditation, can_use_double_roll, get_scout_actions,
    should_stun_scout_on_stairs, brawler_blunt_free
)


def create_test_player(role_id: str, room: str = "F1_R1", sanity: int = 5):
    """Crea un jugador de prueba con rol."""
    return make_player(
        player_id="P1",
        room=room,
        sanity=sanity,
        sanity_max=10,
        role_id=role_id,
    )


def create_test_state(players: dict):
    """Crea un estado de juego de prueba."""
    rooms = ["F1_R1", "F1_P", "F2_R1"]
    players_cfg = {}
    for pid, player in players.items():
        players_cfg[str(pid)] = {
            "room": str(player.room),
            "sanity": player.sanity,
            "sanity_max": player.sanity_max,
            "keys": player.keys,
            "objects": list(player.objects),
        }
    s = make_game_state(
        round=1,
        players=players_cfg,
        rooms=rooms,
        phase="PLAYER",
        king_floor=3,
        turn_order=list(players_cfg.keys()),
    )
    for pid, player in players.items():
        s.players[pid] = player
    return s


class TestRoleDefinitions:
    """Tests para definiciones de roles."""
    
    def test_healer_stats(self):
        """Healer: max 4, 1 llave, 2 objetos"""
        assert get_sanity_max("HEALER") == 4
        assert get_key_slots("HEALER") == 1
        assert get_object_slots("HEALER") == 2
    
    def test_tank_stats(self):
        """Tank: max 7, 1 llave, 3 objetos"""
        assert get_sanity_max("TANK") == 7
        assert get_key_slots("TANK") == 1
        assert get_object_slots("TANK") == 3
    
    def test_high_roller_stats(self):
        """High Roller: max 5, 2 llaves, 2 objetos"""
        assert get_sanity_max("HIGH_ROLLER") == 5
        assert get_key_slots("HIGH_ROLLER") == 2
        assert get_object_slots("HIGH_ROLLER") == 2
    
    def test_scout_stats(self):
        """Scout: max 3, 1 llave, 1 objeto"""
        assert get_sanity_max("SCOUT") == 3
        assert get_key_slots("SCOUT") == 1
        assert get_object_slots("SCOUT") == 1
    
    def test_brawler_stats(self):
        """Brawler: max 3, 1 llave, 2 objetos, inicia con contundente"""
        assert get_sanity_max("BRAWLER") == 3
        assert get_key_slots("BRAWLER") == 1
        assert get_object_slots("BRAWLER") == 2
        assert "BLUNT" in get_starting_items("BRAWLER")
    
    def test_psychic_stats(self):
        """Psychic: max 4, 1 llave, 2 objetos"""
        assert get_sanity_max("PSYCHIC") == 4
        assert get_key_slots("PSYCHIC") == 1
        assert get_object_slots("PSYCHIC") == 2


class TestTankBlockMeditation:
    """Tests para habilidad del Tank: bloquea meditación de otros."""
    
    def test_tank_blocks_others_meditation(self):
        """Tank bloquea meditación de otros en su habitación"""
        tank = make_player(player_id="TANK", room="F1_R1", sanity=5, sanity_max=7, role_id="TANK")
        
        other = make_player(player_id="OTHER", room="F1_R1", sanity=5, sanity_max=5, role_id="HEALER")
        
        # Test función blocks_meditation
        assert blocks_meditation(tank, other) is True
    
    def test_tank_can_meditate_self(self):
        """Tank puede meditar donde quiera"""
        tank = create_test_player("TANK", "F1_R1")
        tank.player_id = PlayerId("TANK")
        
        players = {tank.player_id: tank}
        s = create_test_state(players)
        s.turn_order = [tank.player_id]
        s.remaining_actions = {tank.player_id: 2}
        
        legal = get_legal_actions(s, "TANK")
        meditate = [a for a in legal if a.type == ActionType.MEDITATE]
        
        assert len(meditate) > 0, "Tank debe poder meditar"
    
    def test_tank_blocks_others_in_legality(self):
        """get_legal_actions no incluye MEDITATE para otros en habitación del Tank"""
        tank = make_player(player_id="TANK", room="F1_R1", sanity=5, sanity_max=7, role_id="TANK")
        
        other = make_player(player_id="OTHER", room="F1_R1", sanity=5, sanity_max=5, role_id="HEALER")
        
        players = {tank.player_id: tank, other.player_id: other}
        s = create_test_state(players)
        s.turn_order = [other.player_id, tank.player_id]
        s.remaining_actions = {other.player_id: 2, tank.player_id: 2}
        
        legal = get_legal_actions(s, "OTHER")
        meditate = [a for a in legal if a.type == ActionType.MEDITATE]
        
        assert len(meditate) == 0, "OTHER no debe poder meditar con Tank presente"


class TestHighRollerDoubleRoll:
    """Tests para High Roller: doble d6."""
    
    def test_can_use_double_roll(self):
        """High Roller puede usar doble d6 una vez por turno"""
        hr = create_test_player("HIGH_ROLLER")
        
        assert can_use_double_roll(hr, used_this_turn=False) is True
        assert can_use_double_roll(hr, used_this_turn=True) is False
    
    def test_non_high_roller_cannot_double_roll(self):
        """Otros roles no pueden usar doble d6"""
        healer = create_test_player("HEALER")
        
        assert can_use_double_roll(healer, used_this_turn=False) is False


class TestScoutAbilities:
    """Tests para Scout: movimiento extra y penalidad escaleras."""
    
    def test_scout_gets_extra_action(self):
        """Scout obtiene +1 a sus acciones"""
        scout = create_test_player("SCOUT")
        
        assert get_scout_actions(scout, base_actions=2) == 3
    
    def test_non_scout_no_extra_action(self):
        """Otros roles no tienen acción extra"""
        healer = create_test_player("HEALER")
        
        assert get_scout_actions(healer, base_actions=2) == 2
    
    def test_scout_stun_on_low_stairs_roll(self):
        """Scout queda stuneado si d6+cordura < 3"""
        scout = create_test_player("SCOUT", sanity=0)
        
        # d6=1, cordura=0 → total=1 < 3 → STUN
        assert should_stun_scout_on_stairs(scout, roll=1) is True
        
        # d6=3, cordura=0 → total=3 >= 3 → NO STUN
        assert should_stun_scout_on_stairs(scout, roll=3) is False


class TestBrawlerAbilities:
    """Tests para Brawler: contundente gratis + reacción."""
    
    def test_brawler_blunt_free(self):
        """Brawler puede usar contundente sin acción"""
        brawler = create_test_player("BRAWLER")
        
        assert brawler_blunt_free(brawler) is True
    
    def test_non_brawler_blunt_costs_action(self):
        """Otros roles gastan acción por contundente"""
        healer = create_test_player("HEALER")
        
        assert brawler_blunt_free(healer) is False
    
    def test_brawler_starts_with_blunt(self):
        """Brawler inicia con contundente"""
        items = get_starting_items("BRAWLER")
        
        assert "BLUNT" in items

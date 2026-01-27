"""
Tests para condiciones de VICTORIA y DERROTA canónicas.
"""
import pytest
from engine.state_factory import make_game_state
from engine.types import PlayerId, RoomId
from engine.config import Config
from engine.transition import _check_victory, _check_defeat


def create_base_state(player_rooms: dict, player_keys: dict, player_sanity: dict):
    """Helper para crear estados de prueba."""
    rooms = ["F1_R1", "F1_P", "F2_R1", "F2_P", "F3_R1", "F3_P"]
    players = {}
    for pid, room in player_rooms.items():
        players[pid] = {
            "room": room,
            "sanity": player_sanity.get(pid, 5),
            "sanity_max": 10,
            "keys": player_keys.get(pid, 0),
        }
    s = make_game_state(
        players=players,
        rooms=rooms,
        round=1,
        phase="PLAYER",
        king_floor=3,
        turn_order=list(player_rooms.keys()),
        remaining_actions={pid: 2 for pid in player_rooms},
    )
    s.turn_pos = 0
    s.flags = {}
    return s


# ===== TESTS DE VICTORIA =====

class TestVictoryCondition:
    """Tests para condición de victoria: todos en F2_P + >=4 llaves"""
    
    def test_victory_all_in_f2p_with_4_keys(self):
        """Victoria cuando todos en F2_P y tienen 4+ llaves"""
        s = create_base_state(
            player_rooms={"P1": "F2_P", "P2": "F2_P", "P3": "F2_P"},
            player_keys={"P1": 2, "P2": 1, "P3": 1},  # Total: 4
            player_sanity={"P1": 5, "P2": 5, "P3": 5}
        )
        cfg = Config()
        
        result = _check_victory(s, cfg)
        
        assert result is True
        assert s.game_over is True
        assert s.outcome == "WIN"
    
    def test_no_victory_not_all_in_f2p(self):
        """No victoria si alguien no está en F2_P"""
        s = create_base_state(
            player_rooms={"P1": "F2_P", "P2": "F1_R1", "P3": "F2_P"},  # P2 no en F2_P
            player_keys={"P1": 2, "P2": 1, "P3": 1},
            player_sanity={"P1": 5, "P2": 5, "P3": 5}
        )
        cfg = Config()
        
        result = _check_victory(s, cfg)
        
        assert result is False
        assert s.game_over is False
    
    def test_no_victory_less_than_4_keys(self):
        """No victoria con menos de 4 llaves"""
        s = create_base_state(
            player_rooms={"P1": "F2_P", "P2": "F2_P", "P3": "F2_P"},
            player_keys={"P1": 1, "P2": 1, "P3": 1},  # Total: 3
            player_sanity={"P1": 5, "P2": 5, "P3": 5}
        )
        cfg = Config()
        
        result = _check_victory(s, cfg)
        
        assert result is False
        assert s.game_over is False
    
    def test_victory_with_more_than_4_keys(self):
        """Victoria con 5+ llaves"""
        s = create_base_state(
            player_rooms={"P1": "F2_P", "P2": "F2_P"},
            player_keys={"P1": 3, "P2": 2},  # Total: 5
            player_sanity={"P1": 5, "P2": 5}
        )
        cfg = Config()
        
        result = _check_victory(s, cfg)
        
        assert result is True
        assert s.outcome == "WIN"


# ===== TESTS DE DERROTA =====

class TestDefeatConditions:
    """Tests para condiciones de derrota"""
    
    def test_defeat_all_at_minus5(self):
        """Derrota cuando todos en -5 cordura"""
        s = create_base_state(
            player_rooms={"P1": "F1_R1", "P2": "F2_R1", "P3": "F3_R1"},
            player_keys={"P1": 0, "P2": 0, "P3": 0},
            player_sanity={"P1": -5, "P2": -5, "P3": -5}
        )
        cfg = Config()
        
        result = _check_defeat(s, cfg)
        
        assert result is True
        assert s.game_over is True
        # Since no source was tracked for the initial -5, it defaults to UNKNOWN
        assert s.outcome == "LOSE_ALL_MINUS5 (UNKNOWN)"
    
    def test_no_defeat_one_not_minus5(self):
        """No derrota si al menos uno no está en -5"""
        s = create_base_state(
            player_rooms={"P1": "F1_R1", "P2": "F2_R1", "P3": "F3_R1"},
            player_keys={"P1": 0, "P2": 0, "P3": 0},
            player_sanity={"P1": -5, "P2": -5, "P3": 0}  # P3 no en -5
        )
        cfg = Config()
        
        result = _check_defeat(s, cfg)
        
        assert result is False
        assert s.game_over is False
    
    def test_defeat_keys_destroyed_to_3(self):
        """Derrota cuando solo quedan 3 llaves en juego"""
        s = create_base_state(
            player_rooms={"P1": "F1_R1", "P2": "F2_R1"},
            player_keys={"P1": 0, "P2": 0},
            player_sanity={"P1": 5, "P2": 5}
        )
        s.keys_destroyed = 3  # 6 - 3 = 3 llaves disponibles (KEYS_TOTAL=6 por defecto)
        cfg = Config()
        
        result = _check_defeat(s, cfg)
        
        assert result is True
        assert s.outcome == "LOSE_KEYS_DESTROYED"
    
    def test_no_defeat_4_keys_available(self):
        """No derrota con 4 llaves disponibles"""
        s = create_base_state(
            player_rooms={"P1": "F1_R1", "P2": "F2_R1"},
            player_keys={"P1": 0, "P2": 0},
            player_sanity={"P1": 5, "P2": 5}
        )
        s.keys_destroyed = 2  # 6 - 2 = 4 llaves (no derrota)
        cfg = Config(KEYS_TOTAL=6)
        
        result = _check_defeat(s, cfg)
        
        assert result is False
        assert s.game_over is False

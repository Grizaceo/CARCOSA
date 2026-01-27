"""
Tests para REINA HELADA - Bloqueo de movimiento
"""
import pytest
from engine.state_factory import make_game_state
from engine.types import PlayerId, RoomId, CardId
from engine.config import Config
from engine.transition import step
from engine.actions import Action, ActionType
from engine.rng import RNG
from engine.legality import get_legal_actions


def setup_state_with_queen():
    """Estado con mazo que contiene Reina Helada"""
    rooms = {
        "F1_R1": {"cards": ["MONSTER:REINA_HELADA"]},
        "F1_R2": {},
        "F1_P": {},
        "F2_R1": {},
        "F2_P": {},
    }

    players = {
        "P1": {"room": "F1_R2", "sanity": 5, "sanity_max": 10},
        "P2": {"room": "F1_R1", "sanity": 5, "sanity_max": 10},
        "P3": {"room": "F2_R1", "sanity": 5, "sanity_max": 10},
    }

    s = make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=3,
        turn_pos=0,
        remaining_actions={"P1": 2, "P2": 2, "P3": 2},
        turn_order=["P1", "P2", "P3"],
    )
    s.flags = {}

    return s

def test_reina_helada_blocks_movement_on_reveal():
    """Cuando Reina Helada es revelada, los jugadores en ese piso no pueden moverse"""
    s = setup_state_with_queen()
    cfg = Config()
    rng = RNG(42)
    
    # P2 está en F1_R1 y busca, revelando la Reina Helada
    s.turn_order = [PlayerId("P2"), PlayerId("P1"), PlayerId("P3")]
    s.turn_pos = 0
    
    # Antes de revelar, P2 puede moverse
    legal_before = get_legal_actions(s, "P2")
    move_before = [a for a in legal_before if a.type == ActionType.MOVE]
    assert len(move_before) > 0, "P2 debe poder moverse antes de revelar Reina"
    
    # P2 busca y revela la Reina Helada
    action = Action(actor="P2", type=ActionType.SEARCH, data={})
    s = step(s, action, rng, cfg)
    
    # Ahora P1 y P2 (en piso 1) deben estar en movement_blocked_players
    assert PlayerId("P1") in s.movement_blocked_players, "P1 (piso 1) debe estar bloqueado"
    assert PlayerId("P2") in s.movement_blocked_players, "P2 (piso 1) debe estar bloqueado"
    assert PlayerId("P3") not in s.movement_blocked_players, "P3 (piso 2) NO debe estar bloqueado"


def test_reina_helada_movement_blocked_no_move_actions():
    """Jugadores bloqueados no tienen acciones de MOVE disponibles"""
    s = setup_state_with_queen()
    cfg = Config()
    rng = RNG(42)
    
    # P2 busca y revela la Reina
    s.turn_order = [PlayerId("P2"), PlayerId("P1"), PlayerId("P3")]
    s.turn_pos = 0
    action = Action(actor="P2", type=ActionType.SEARCH, data={})
    s = step(s, action, rng, cfg)
    
    # P1 ahora tiene el turno (después de que P2 use su acción)
    s.turn_pos = 1
    s.remaining_actions[PlayerId("P1")] = 2
    
    # P1 NO debe tener acciones de movimiento
    legal = get_legal_actions(s, "P1")
    move_actions = [a for a in legal if a.type == ActionType.MOVE]
    assert len(move_actions) == 0, "P1 bloqueado NO debe poder moverse"
    
    # Pero SÍ puede hacer otras acciones
    meditate = [a for a in legal if a.type == ActionType.MEDITATE]
    assert len(meditate) > 0, "P1 bloqueado SÍ debe poder meditar"


def test_reina_helada_p3_not_blocked():
    """Jugadores en otros pisos NO están bloqueados"""
    s = setup_state_with_queen()
    cfg = Config()
    rng = RNG(42)
    
    # P2 revela la Reina
    s.turn_order = [PlayerId("P2"), PlayerId("P3"), PlayerId("P1")]
    s.turn_pos = 0
    action = Action(actor="P2", type=ActionType.SEARCH, data={})
    s = step(s, action, rng, cfg)
    
    # P3 tiene el turno
    s.turn_pos = 1
    s.remaining_actions[PlayerId("P3")] = 2
    
    # P3 (piso 2) SÍ puede moverse
    legal = get_legal_actions(s, "P3")
    move_actions = [a for a in legal if a.type == ActionType.MOVE]
    assert len(move_actions) > 0, "P3 (piso 2) SÍ debe poder moverse"


def test_movement_block_cleared_on_new_round():
    """El bloqueo de movimiento se limpia al inicio de nueva ronda"""
    s = setup_state_with_queen()
    cfg = Config()
    rng = RNG(42)
    
    # Simular que hay jugadores bloqueados
    s.movement_blocked_players = [PlayerId("P1"), PlayerId("P2")]
    
    # Simular KING_ENDROUND para pasar a nueva ronda
    s.phase = "KING"
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)
    
    # Debe haberse limpiado la lista
    assert len(s.movement_blocked_players) == 0, "movement_blocked_players debe estar vacío"


# ===== ACCION_REDUCIDA Tests =====

def test_accion_reducida_in_reina_floor():
    """Jugadores en piso de Reina Helada solo tienen 1 acción en turnos posteriores"""
    s = setup_state_with_queen()
    cfg = Config()
    rng = RNG(42)
    
    # P2 busca y revela la Reina en F1_R1
    s.turn_order = [PlayerId("P2"), PlayerId("P1"), PlayerId("P3")]
    s.turn_pos = 0
    action = Action(actor="P2", type=ActionType.SEARCH, data={})
    s = step(s, action, rng, cfg)
    
    # Verificar que la Reina está en el tablero
    reina = [m for m in s.monsters if m.monster_id == "REINA_HELADA"]
    assert len(reina) == 1, "Reina Helada debe estar en el tablero"
    
    # Pasar a nueva ronda (aquí aplica ACCION_REDUCIDA)
    s.phase = "KING"
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)
    
    # P1 y P2 (en piso 1 con la Reina) deben tener solo 1 acción
    # P3 (en piso 2) debe tener 2 acciones
    assert s.remaining_actions[PlayerId("P1")] == 1, "P1 en piso Reina debe tener 1 acción"
    assert s.remaining_actions[PlayerId("P2")] == 1, "P2 en piso Reina debe tener 1 acción"
    assert s.remaining_actions[PlayerId("P3")] == 2, "P3 fuera del piso Reina debe tener 2 acciones"


def test_accion_reducida_not_applied_if_reina_stunned():
    """Si la Reina está stuneada, no aplica acción reducida"""
    s = setup_state_with_queen()
    cfg = Config()
    rng = RNG(42)
    
    # Revelar la Reina
    s.turn_order = [PlayerId("P2"), PlayerId("P1"), PlayerId("P3")]
    s.turn_pos = 0
    action = Action(actor="P2", type=ActionType.SEARCH, data={})
    s = step(s, action, rng, cfg)
    
    # Stunear la Reina manualmente
    for m in s.monsters:
        if m.monster_id == "REINA_HELADA":
            m.stunned_remaining_rounds = 2
    
    # Pasar a nueva ronda
    s.phase = "KING"
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)
    
    # P1 debe tener 2 acciones (Reina stuneada no reduce)
    assert s.remaining_actions[PlayerId("P1")] == 2, "P1 debe tener 2 acciones si Reina está stuneada"


def test_iluminado_adds_action_even_with_reina():
    """ILUMINADO otorga +1 acción incluso en piso de Reina (1+1=2)"""
    from engine.state import StatusInstance
    s = setup_state_with_queen()
    cfg = Config()
    rng = RNG(42)
    
    # Revelar la Reina
    s.turn_order = [PlayerId("P2"), PlayerId("P1"), PlayerId("P3")]
    s.turn_pos = 0
    action = Action(actor="P2", type=ActionType.SEARCH, data={})
    s = step(s, action, rng, cfg)
    
    # P1 tiene ILUMINADO
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="ILUMINADO", remaining_rounds=2)
    )
    
    # Pasar a nueva ronda
    s.phase = "KING"
    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s = step(s, action, rng, cfg)
    
    # P1 debe tener 2 acciones (1 base por Reina + 1 por ILUMINADO)
    assert s.remaining_actions[PlayerId("P1")] == 2, "P1 con ILUMINADO en piso Reina debe tener 2 acciones"

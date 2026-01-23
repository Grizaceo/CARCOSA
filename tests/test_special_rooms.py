
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId
from engine.actions import Action, ActionType
from engine.transition import step
from engine.config import Config
from engine.rng import RNG
# from engine.setup import setup_game  <-- Removed
from engine.effects.states_canonical import has_status

def create_base_state():
    """Helper: crea un estado básico funcional."""
    s = GameState(round=1, players={})
    # Setup mínimo
    s.rooms = {}
    # Crear algunas habitaciones genéricas
    for r in ["F1_R1", "F1_R2", "F1_R3", "F1_R4"]:
        s.rooms[RoomId(r)] = RoomState(room_id=RoomId(r), deck=DeckState(cards=[]))
    
    s.players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), room=RoomId("F1_R1"), sanity=3, sanity_max=5)
    }
    s.turn_order = ["P1"]
    s.remaining_actions["P1"] = 2
    s.phase = "PLAYER"
    return s

def test_legality_special_rooms():
    """Verifica que las acciones especiales aparezcan en la lista de legales."""
    s = create_base_state()
    p = s.players["P1"]
    p.room = RoomId("F1_R1")
    
    # Caso 1: Capilla
    s.rooms[p.room].special_card_id = "MONASTERIO_LOCURA"
    s.rooms[p.room].special_revealed = True
    s.rooms[p.room].special_destroyed = False
    
    from engine.legality import get_legal_actions
    legal = get_legal_actions(s, "P1")
    types = [a.type for a in legal]
    assert ActionType.USE_CAPILLA in types
    
    # Caso 2: Salón de Belleza
    s.rooms[p.room].special_card_id = "SALON_BELLEZA"
    s.rooms[p.room].special_revealed = True
    legal = get_legal_actions(s, "P1")
    types = [a.type for a in legal]
    assert ActionType.USE_SALON_BELLEZA in types

def test_capilla_healing_and_risk():
    """B1: Monasterio - Cura d6+2, Riesgo Paranoia si d6=1."""
    s = create_base_state()
    p = s.players["P1"]
    p = s.players["P1"]
    p.room = RoomId("F1_R1")
    s.rooms[RoomId("F1_R1")].special_card_id = "MONASTERIO_LOCURA"
    s.rooms[RoomId("F1_R1")].special_revealed = True
    
    class MockRNG:
        def __init__(self, val): self.val = val
        def randint(self, a, b): return self.val
        def shuffle(self, x): pass

    # Test Cura
    p.sanity = 1
    action = Action(actor="P1", type=ActionType.USE_CAPILLA, data={})
    newState = step(s, action, MockRNG(4), Config())
    assert newState.players["P1"].sanity == min(5, 1 + 4 + 2) # 1+6=7 -> max 5
    assert not has_status(newState.players["P1"], "PARANOIA")

    # Test Riesgo (d6=1)
    p.sanity = 3
    newState = step(s, action, MockRNG(1), Config())
    assert newState.players["P1"].sanity == min(5, 3 + 1 + 2) # 3+3=6 -> max 5
    assert has_status(newState.players["P1"], "PARANOIA")

def test_salon_belleza_vanity():
    """B7: Salón Belleza - Contador, Vanidad al 3er uso, Protección."""
    s = create_base_state()
    p = s.players["P1"]
    p = s.players["P1"]
    p.room = RoomId("F1_R1")
    s.rooms[RoomId("F1_R1")].special_card_id = "SALON_BELLEZA"
    s.rooms[RoomId("F1_R1")].special_revealed = True
    
    # Uso 1
    action = Action(actor="P1", type=ActionType.USE_SALON_BELLEZA, data={})
    s = step(s, action, RNG(0), Config())
    assert s.salon_belleza_uses == 1
    assert s.flags.get("PROTECCION_AMARILLO_P1") is not None
    assert not has_status(s.players["P1"], "VANIDAD")
    
    # Uso 2
    s.remaining_actions["P1"] = 2
    s = step(s, action, RNG(0), Config())
    assert s.salon_belleza_uses == 2
    
    # Uso 3: Vanidad
    s.remaining_actions["P1"] = 2
    s = step(s, action, RNG(0), Config())
    assert s.salon_belleza_uses == 3
    assert has_status(s.players["P1"], "VANIDAD")

def test_armory_take():
    """B6: Armería - Tomar item si existe."""
    s = create_base_state()
    p = s.players["P1"]
    p.room = RoomId("F1_R1")
    s.rooms[RoomId("F1_R1")].special_card_id = "ARMERIA"
    s.rooms[RoomId("F1_R1")].special_revealed = True
    
    # Setup storage
    s.armory_storage[RoomId("F1_R1")] = ["BLUNT"]
    
    action = Action(actor="P1", type=ActionType.USE_ARMORY_TAKE, data={})
    s = step(s, action, RNG(0), Config())
    
    assert "BLUNT" in s.players["P1"].objects
    assert len(s.armory_storage[RoomId("F1_R1")]) == 0

def test_taberna_peek():
    """B5: Taberna - Mirar 2 habitaciones."""
    s = create_base_state()
    p = s.players["P1"]
    p.room = RoomId("F1_R1")
    s.rooms[RoomId("F1_R1")].special_card_id = "TABERNA"
    s.rooms[RoomId("F1_R1")].special_revealed = True
    
    # Validar legalidad
    from engine.legality import get_legal_actions
    legal = get_legal_actions(s, "P1")
    types = [a.type for a in legal]
    assert ActionType.USE_TABERNA_ROOMS in types
    
    # Execute
    action = Action(actor="P1", type=ActionType.USE_TABERNA_ROOMS, data={"room_a": "F1_R2", "room_b": "F1_R3"})
    s = step(s, action, RNG(0), Config())
    
    assert s.taberna_used_this_turn[PlayerId("P1")]
    assert s.players[PlayerId("P1")].sanity == 2  # Costo 1 check (3 -> 2)

def test_puertas_amarillas_teleport():
    """B4: Puertas Amarillas - Teleport a target, target -1 sanity."""
    s = create_base_state()
    # Add P2 in F1_R4
    s.players["P2"] = PlayerState(player_id=PlayerId("P2"), room=RoomId("F1_R4"), sanity=5, sanity_max=5)
    
    p = s.players["P1"]
    p.room = RoomId("F1_R1")
    s.rooms[RoomId("F1_R1")].special_card_id = "PUERTAS_AMARILLO"
    s.rooms[RoomId("F1_R1")].special_revealed = True
    
    action = Action(actor="P1", type=ActionType.USE_YELLOW_DOORS, data={"target_player": "P2"})
    s = step(s, action, RNG(0), Config())
    
    assert s.players["P1"].room == RoomId("F1_R4")
    assert s.players["P2"].sanity == 4 # -1 sanity

def test_motemey_sell():
    """B2: Motemey - Venta de objetos."""
    s = create_base_state()
    p = s.players["P1"]
    p.room = RoomId("F1_R1")
    s.rooms[RoomId("F1_R1")].special_card_id = "MOTEMEY" # Legacy MOTEMEY? Setup says MOTEMEY. ARMERIA checks ARMERIA/ARMERY. MOTEMEY is MOTEMEY.
    s.rooms[RoomId("F1_R1")].special_revealed = True
    
    p.objects.append("BLUNT") # Normal object
    p.objects.append("TREASURE_GEM") # Treasure
    
    # Sell Normal (+1 Sanity)
    p.sanity = 3
    action = Action(actor="P1", type=ActionType.USE_MOTEMEY_SELL, data={"item_name": "BLUNT"})
    s = step(s, action, RNG(0), Config())
    assert s.players["P1"].sanity == 4
    assert "BLUNT" not in s.players["P1"].objects
    
    # Sell Treasure (+3 Sanity)
    # Re-fetch p for clarity or modify s directly
    s.players["P1"].sanity = 1
    action = Action(actor="P1", type=ActionType.USE_MOTEMEY_SELL, data={"item_name": "TREASURE_GEM"})
    s = step(s, action, RNG(0), Config())
    assert s.players["P1"].sanity == 4 # 1+3
    assert "TREASURE_GEM" not in s.players["P1"].objects

def test_camara_letal_ritual():
    """B3: Cámara Letal - Ritual de 2 jugadores."""
    s = create_base_state()
    s.flags["CAMARA_LETAL_PRESENT"] = True # Requisito
    
    # Add P2 in same room
    s.players["P2"] = PlayerState(player_id=PlayerId("P2"), room=RoomId("F1_R1"), sanity=5, sanity_max=5)
    
    p = s.players["P1"]
    p.room = RoomId("F1_R1")
    s.rooms[RoomId("F1_R1")].special_card_id = "CAMARA_LETAL"
    s.rooms[RoomId("F1_R1")].special_revealed = True
    
    # Legal? No require revealed per code in legality?
    # legality.py: "is_camara_letal = (room_state.special_card_id == 'CAMARA_LETAL')"
    # No check revealed (similar to Monasterio). But helpful for consistency.
    
    from engine.legality import get_legal_actions
    legal = get_legal_actions(s, "P1")
    types = [a.type for a in legal]
    assert ActionType.USE_CAMARA_LETAL_RITUAL in types
    
    action = Action(actor="P1", type=ActionType.USE_CAMARA_LETAL_RITUAL, data={})
    
    class MockRNG:
        def __init__(self, val): self.val = val
        def randint(self, a, b): return self.val # d6
        def shuffle(self, x): pass

    # d6=7 (not possible with d6, but let's test logic if it was d6+X).
    # d6=0-7 logic.
    # Logic in transition:
    # d6 = rng.randint(1, 6)
    # ritual_result(d6)
    # 0,1,2 -> -2 sanity active player
    # 3,4 -> -2 sanity active, -1 other
    # 5,6 -> success (key)
    # 7+ -> success + sanity?
    
    # Test Success (6)
    s = step(s, action, MockRNG(6), Config())
    assert s.flags["CAMARA_LETAL_RITUAL_COMPLETED"]
    assert s.players["P1"].keys == 1 # Got key?
    # Check logic in transition:
    # 6: KEY obtained.
    # Player.keys += 1 (respecting cap).
    


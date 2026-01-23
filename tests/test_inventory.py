"""
Tests para el sistema de inventario.
"""
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId
from engine.inventory import (
    get_inventory_limits, get_object_count, can_add_object, can_add_key,
    add_object, remove_object, consume_object, is_tale_of_yellow, attach_tale_to_chambers
)


def create_test_player(role_id: str = "DEFAULT", objects: list = None, keys: int = 0) -> PlayerState:
    """Crea un jugador de prueba."""
    p = PlayerState(
        player_id=PlayerId("P1"),
        sanity=5,
        room=RoomId("F1_R1"),
        sanity_max=10,
        keys=keys,
    )
    p.role_id = role_id
    p.objects = objects or []
    return p


def create_test_state(player: PlayerState) -> GameState:
    """Crea un estado de juego de prueba."""
    rooms = {
        RoomId("F1_R1"): RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=[])),
    }
    return GameState(
        round=1,
        players={player.player_id: player},
        rooms=rooms,
        phase="PLAYER",
        king_floor=3,
    )


class TestInventoryLimits:
    """Tests para límites de inventario por rol."""
    
    def test_healer_limits(self):
        """Healer: 1 llave, 2 objetos"""
        p = create_test_player(role_id="HEALER")
        key_slots, obj_slots = get_inventory_limits(p)
        assert key_slots == 1
        assert obj_slots == 2
    
    def test_tank_limits(self):
        """Tank: 1 llave, 3 objetos"""
        p = create_test_player(role_id="TANK")
        key_slots, obj_slots = get_inventory_limits(p)
        assert key_slots == 1
        assert obj_slots == 3
    
    def test_high_roller_limits(self):
        """High Roller: 2 llaves, 2 objetos"""
        p = create_test_player(role_id="HIGH_ROLLER")
        key_slots, obj_slots = get_inventory_limits(p)
        assert key_slots == 2
        assert obj_slots == 2
    
    def test_scout_limits(self):
        """Scout: 1 llave, 1 objeto"""
        p = create_test_player(role_id="SCOUT")
        key_slots, obj_slots = get_inventory_limits(p)
        assert key_slots == 1
        assert obj_slots == 1


class TestAddObject:
    """Tests para agregar objetos al inventario."""
    
    def test_add_object_when_space(self):
        """Puede agregar objeto si hay espacio"""
        p = create_test_player(role_id="HEALER", objects=[])
        s = create_test_state(p)
        
        result = add_object(s, p.player_id, "COMPASS")
        
        assert result is True
        assert "COMPASS" in s.players[p.player_id].objects
    
    def test_add_object_full_without_discard_fails(self):
        """No puede agregar si está lleno sin especificar descarte"""
        p = create_test_player(role_id="SCOUT", objects=["VIAL"])  # 1/1 lleno
        s = create_test_state(p)
        
        result = add_object(s, p.player_id, "COMPASS")
        
        assert result is False
        assert "COMPASS" not in s.players[p.player_id].objects
    
    def test_add_object_full_discard_new(self):
        """Puede descartar el nuevo objeto si está lleno"""
        p = create_test_player(role_id="SCOUT", objects=["VIAL"])
        s = create_test_state(p)
        
        result = add_object(s, p.player_id, "COMPASS", discard_choice="COMPASS")
        
        assert result is True
        assert "COMPASS" not in s.players[p.player_id].objects
        assert "COMPASS" in s.discard_pile
    
    def test_add_object_full_discard_existing(self):
        """Puede descartar un objeto existente para agregar nuevo"""
        p = create_test_player(role_id="SCOUT", objects=["VIAL"])
        s = create_test_state(p)
        
        result = add_object(s, p.player_id, "COMPASS", discard_choice="VIAL")
        
        assert result is True
        assert "COMPASS" in s.players[p.player_id].objects
        assert "VIAL" in s.discard_pile
    
    def test_soulbound_always_adds(self):
        """Objetos soulbound siempre se pueden agregar"""
        p = create_test_player(role_id="SCOUT", objects=["VIAL"])  # 1/1 lleno
        s = create_test_state(p)
        
        result = add_object(s, p.player_id, "CROWN")
        
        assert result is True
        assert "CROWN" in s.players[p.player_id].objects


class TestChambersBook:
    """Tests para Libro de Chambers y Cuentos de Amarillo."""
    
    def test_chambers_book_registers_holder(self):
        """Al obtener Libro de Chambers, se registra como holder"""
        p = create_test_player(objects=[])
        s = create_test_state(p)
        
        add_object(s, p.player_id, "CHAMBERS_BOOK")
        
        assert s.chambers_book_holder == p.player_id
    
    def test_is_tale_of_yellow(self):
        """Verifica identificación de Cuentos de Amarillo"""
        assert is_tale_of_yellow("TALE_REPAIRER") is True
        assert is_tale_of_yellow("TALE_MASK") is True
        assert is_tale_of_yellow("TALE_DRAGON") is True
        assert is_tale_of_yellow("TALE_SIGN") is True
        assert is_tale_of_yellow("COMPASS") is False
    
    def test_attach_tale_increments_counter(self):
        """Unir cuento incrementa contador"""
        p = create_test_player(objects=["CHAMBERS_BOOK", "TALE_MASK"])
        s = create_test_state(p)
        s.chambers_book_holder = p.player_id
        
        result = attach_tale_to_chambers(s, p.player_id, "TALE_MASK")
        
        assert result is True
        assert s.chambers_tales_attached == 1
        assert "TALE_MASK" not in s.players[p.player_id].objects
    
    def test_attach_tale_applies_vanish(self):
        """Unir cuento aplica vanish al Rey"""
        p = create_test_player(objects=["CHAMBERS_BOOK", "TALE_REPAIRER"])
        s = create_test_state(p)
        s.chambers_book_holder = p.player_id
        
        attach_tale_to_chambers(s, p.player_id, "TALE_REPAIRER")
        
        assert s.king_vanished_turns == 1  # Primer cuento = 1 turno
    
    def test_attach_second_tale_vanish_2_turns(self):
        """Segundo cuento aplica 2 turnos de vanish"""
        p = create_test_player(objects=["CHAMBERS_BOOK", "TALE_REPAIRER", "TALE_MASK"])
        s = create_test_state(p)
        s.chambers_book_holder = p.player_id
        
        attach_tale_to_chambers(s, p.player_id, "TALE_REPAIRER")
        attach_tale_to_chambers(s, p.player_id, "TALE_MASK")
        
        assert s.chambers_tales_attached == 2
        assert s.king_vanished_turns == 2
    
    def test_cannot_attach_without_book(self):
        """No puede unir cuento si no tiene el Libro"""
        p = create_test_player(objects=["TALE_MASK"])
        s = create_test_state(p)
        # No tiene el libro
        
        result = attach_tale_to_chambers(s, p.player_id, "TALE_MASK")
        
        assert result is False

"""
Tests para E) Serialización/replay: verificar que from_dict restaura todos los campos.
"""
import pytest
from engine.state import GameState
from engine.state_factory import make_game_state, make_room
from engine.types import PlayerId, RoomId


def test_gamestate_roundtrip_basic():
    """to_dict() -> from_dict() preserva campos basicos"""
    # Setup estado basico
    original = make_game_state(
        round=10,
        players={
            "P1": {
                "room": "F1_P",
                "sanity": 5,
                "keys": 2,
                "objects": ["COMPASS", "VIAL"],
            }
        },
        rooms={
            "F1_P": {"cards": ["KEY", "MONSTER:SPIDER"]},
        },
        king_floor=2,
    )
    original.seed = 42

    # Serializar y deserializar
    data = original.to_dict()
    restored = GameState.from_dict(data)

    # Verificar campos basicos
    assert restored.round == 10
    assert restored.king_floor == 2
    assert restored.seed == 42
    assert PlayerId("P1") in restored.players
    assert restored.players[PlayerId("P1")].sanity == 5
    assert restored.players[PlayerId("P1")].keys == 2
    assert "COMPASS" in restored.players[PlayerId("P1")].objects


def test_gamestate_roundtrip_motemey_deck():
    """to_dict() -> from_dict() preserva motemey_deck"""
    motemey_deck = make_room("F1_P", cards=["COMPASS", "VIAL", "KEY"]).deck
    motemey_deck.top = 1

    original = make_game_state(
        round=1,
        players={"P1": {"room": "F1_P", "sanity": 3}},
        rooms=["F1_P"],
    )
    original.motemey_deck = motemey_deck
    original.motemey_event_active = True

    data = original.to_dict()
    restored = GameState.from_dict(data)

    assert len(restored.motemey_deck.cards) == 3
    assert restored.motemey_deck.top == 1
    assert restored.motemey_event_active is True
    assert str(restored.motemey_deck.cards[0]) == "COMPASS"


def test_gamestate_roundtrip_peek_used():
    """to_dict() -> from_dict() preserva peek_used_this_turn"""
    original = make_game_state(
        round=1,
        players={
            "P1": {"room": "F1_P", "sanity": 3},
            "P2": {"room": "F2_P", "sanity": 5},
        },
        rooms=["F1_P", "F2_P"],
    )
    original.peek_used_this_turn = {
        PlayerId("P1"): True,
        PlayerId("P2"): False,
    }

    data = original.to_dict()
    restored = GameState.from_dict(data)

    assert restored.peek_used_this_turn[PlayerId("P1")] is True
    assert restored.peek_used_this_turn[PlayerId("P2")] is False


def test_gamestate_roundtrip_armory_storage():
    """to_dict() -> from_dict() preserva armory_storage"""
    original = make_game_state(
        round=1,
        players={"P1": {"room": "F1_R1", "sanity": 3}},
        rooms={"F1_R1": {"cards": []}},
    )
    original.armory_storage = {RoomId("F1_R1"): ["COMPASS", "BLUNT"]}

    data = original.to_dict()
    restored = GameState.from_dict(data)

    assert RoomId("F1_R1") in restored.armory_storage
    assert restored.armory_storage[RoomId("F1_R1")] == ["COMPASS", "BLUNT"]


def test_roomstate_roundtrip_special_fields():
    """to_dict() -> from_dict() preserva campos especiales de RoomState"""
    original = make_game_state(
        round=5,
        players={"P1": {"room": "F2_R3", "sanity": 3}},
        rooms={
            "F2_R3": {
                "cards": ["KEY"],
                "special_card_id": "CAMARA_LETAL",
                "special_revealed": True,
                "special_destroyed": False,
            }
        },
    )
    room = original.rooms[RoomId("F2_R3")]
    room.revealed = 2
    room.special_activation_count = 1

    data = original.to_dict()
    restored = GameState.from_dict(data)

    room = restored.rooms[RoomId("F2_R3")]
    assert room.special_card_id == "CAMARA_LETAL"
    assert room.special_revealed is True
    assert room.special_destroyed is False
    assert room.special_activation_count == 1


def test_gamestate_roundtrip_comprehensive():
    """Roundtrip comprehensivo con todos los campos nuevos"""
    original = make_game_state(
        round=20,
        players={
            "P1": {
                "room": "F1_R2",
                "sanity": 3,
                "keys": 3,
                "objects": ["TREASURE_RING", "VIAL"],
            }
        },
        rooms={
            "F1_R2": {
                "cards": ["KEY"],
                "special_card_id": "PEEK",
                "special_revealed": True,
                "special_destroyed": False,
            }
        },
        king_floor=3,
    )
    room = original.rooms[RoomId("F1_R2")]
    room.revealed = 1
    room.special_activation_count = 2
    motemey_deck = make_room("F1_R2", cards=["COMPASS", "VIAL"]).deck
    motemey_deck.top = 1
    original.motemey_deck = motemey_deck
    original.motemey_event_active = False
    original.peek_used_this_turn = {PlayerId("P1"): True}
    original.armory_storage = {RoomId("F1_R2"): ["BLUNT"]}
    original.seed = 123

    data = original.to_dict()
    restored = GameState.from_dict(data)

    # Verificar todos los campos
    assert restored.round == 20
    assert restored.king_floor == 3
    assert restored.seed == 123

    # Motemey
    assert len(restored.motemey_deck.cards) == 2
    assert restored.motemey_deck.top == 1
    assert restored.motemey_event_active is False

    # Peek
    assert restored.peek_used_this_turn[PlayerId("P1")] is True

    # Armory
    assert restored.armory_storage[RoomId("F1_R2")] == ["BLUNT"]

    # RoomState special fields
    room = restored.rooms[RoomId("F1_R2")]
    assert room.special_card_id == "PEEK"
    assert room.special_revealed is True
    assert room.special_destroyed is False
    assert room.special_activation_count == 2

    # PlayerState
    p = restored.players[PlayerId("P1")]
    assert p.keys == 3
    assert "TREASURE_RING" in p.objects



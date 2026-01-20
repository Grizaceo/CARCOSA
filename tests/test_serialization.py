"""
Tests para E) Serialización/replay: verificar que from_dict restaura todos los campos.
"""
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId, CardId
from engine.config import Config


def test_gamestate_roundtrip_basic():
    """to_dict() -> from_dict() preserva campos básicos"""
    # Setup estado básico
    players = {
        PlayerId("P1"): PlayerState(
            player_id=PlayerId("P1"),
            sanity=5,
            room=RoomId("F1_P"),
            keys=2,
            objects=["COMPASS", "VIAL"]
        ),
    }

    rooms = {
        RoomId("F1_P"): RoomState(
            room_id=RoomId("F1_P"),
            deck=DeckState(cards=[CardId("KEY"), CardId("MONSTER:SPIDER")])
        ),
    }

    original = GameState(
        round=10,
        players=players,
        rooms=rooms,
        king_floor=2,
        seed=42
    )

    # Serializar y deserializar
    data = original.to_dict()
    restored = GameState.from_dict(data)

    # Verificar campos básicos
    assert restored.round == 10
    assert restored.king_floor == 2
    assert restored.seed == 42
    assert PlayerId("P1") in restored.players
    assert restored.players[PlayerId("P1")].sanity == 5
    assert restored.players[PlayerId("P1")].keys == 2
    assert "COMPASS" in restored.players[PlayerId("P1")].objects


def test_gamestate_roundtrip_motemey_deck():
    """to_dict() -> from_dict() preserva motemey_deck"""
    motemey_cards = [CardId("COMPASS"), CardId("VIAL"), CardId("KEY")]
    motemey_deck = DeckState(cards=motemey_cards, top=1)

    original = GameState(
        round=1,
        players={
            PlayerId("P1"): PlayerState(
                player_id=PlayerId("P1"),
                sanity=3,
                room=RoomId("F1_P")
            )
        },
        rooms={},
        motemey_deck=motemey_deck,
        motemey_event_active=True
    )

    data = original.to_dict()
    restored = GameState.from_dict(data)

    assert len(restored.motemey_deck.cards) == 3
    assert restored.motemey_deck.top == 1
    assert restored.motemey_event_active is True
    assert str(restored.motemey_deck.cards[0]) == "COMPASS"


def test_gamestate_roundtrip_peek_used():
    """to_dict() -> from_dict() preserva peek_used_this_turn"""
    original = GameState(
        round=1,
        players={
            PlayerId("P1"): PlayerState(
                player_id=PlayerId("P1"),
                sanity=3,
                room=RoomId("F1_P")
            ),
            PlayerId("P2"): PlayerState(
                player_id=PlayerId("P2"),
                sanity=5,
                room=RoomId("F2_P")
            )
        },
        rooms={},
        peek_used_this_turn={
            PlayerId("P1"): True,
            PlayerId("P2"): False
        }
    )

    data = original.to_dict()
    restored = GameState.from_dict(data)

    assert restored.peek_used_this_turn[PlayerId("P1")] is True
    assert restored.peek_used_this_turn[PlayerId("P2")] is False


def test_gamestate_roundtrip_armory_storage():
    """to_dict() -> from_dict() preserva armory_storage"""
    original = GameState(
        round=1,
        players={
            PlayerId("P1"): PlayerState(
                player_id=PlayerId("P1"),
                sanity=3,
                room=RoomId("F1_R1")
            )
        },
        rooms={
            RoomId("F1_R1"): RoomState(
                room_id=RoomId("F1_R1"),
                deck=DeckState(cards=[])
            )
        },
        armory_storage={
            RoomId("F1_R1"): ["COMPASS", "BLUNT"]
        }
    )

    data = original.to_dict()
    restored = GameState.from_dict(data)

    assert RoomId("F1_R1") in restored.armory_storage
    assert restored.armory_storage[RoomId("F1_R1")] == ["COMPASS", "BLUNT"]


def test_roomstate_roundtrip_special_fields():
    """to_dict() -> from_dict() preserva campos especiales de RoomState"""
    rooms = {
        RoomId("F2_R3"): RoomState(
            room_id=RoomId("F2_R3"),
            deck=DeckState(cards=[CardId("KEY")]),
            revealed=2,
            special_card_id="CAMARA_LETAL",
            special_revealed=True,
            special_destroyed=False,
            special_activation_count=1
        ),
    }

    original = GameState(
        round=5,
        players={
            PlayerId("P1"): PlayerState(
                player_id=PlayerId("P1"),
                sanity=3,
                room=RoomId("F2_R3")
            )
        },
        rooms=rooms
    )

    data = original.to_dict()
    restored = GameState.from_dict(data)

    room = restored.rooms[RoomId("F2_R3")]
    assert room.special_card_id == "CAMARA_LETAL"
    assert room.special_revealed is True
    assert room.special_destroyed is False
    assert room.special_activation_count == 1


def test_gamestate_roundtrip_comprehensive():
    """Roundtrip comprehensivo con todos los campos nuevos"""
    original = GameState(
        round=20,
        players={
            PlayerId("P1"): PlayerState(
                player_id=PlayerId("P1"),
                sanity=3,
                room=RoomId("F1_R2"),
                keys=3,
                objects=["TREASURE_RING", "VIAL"]
            )
        },
        rooms={
            RoomId("F1_R2"): RoomState(
                room_id=RoomId("F1_R2"),
                deck=DeckState(cards=[CardId("KEY")], top=0),
                revealed=1,
                special_card_id="PEEK",
                special_revealed=True,
                special_destroyed=False,
                special_activation_count=2
            )
        },
        motemey_deck=DeckState(
            cards=[CardId("COMPASS"), CardId("VIAL")],
            top=1
        ),
        motemey_event_active=False,
        peek_used_this_turn={PlayerId("P1"): True},
        armory_storage={RoomId("F1_R2"): ["BLUNT"]},
        king_floor=3,
        seed=123
    )

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

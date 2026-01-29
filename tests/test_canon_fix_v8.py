import pytest
from engine.types import PlayerId, RoomId
from engine.config import Config
from engine.board import corridor_id, room_id

# Use local imports in tests to avoid circular dependencies during collection
# if high-level modules import each other.

def test_sacrifice_interrupt():
    """Verifica que al cruzar a -5 se pausa y pide decisión."""
    from engine.state_factory import make_game_state
    from engine.transition import step, _apply_minus5_transitions, apply_sanity_loss
    from engine.actions import Action, ActionType
    from engine.legality import get_legal_actions
    
    s = make_game_state(
        players={"P1": {"room": str(corridor_id(1)), "sanity": -4, "sanity_max": 5, "keys": 2}},
        rooms=[str(corridor_id(1))],
        turn_order=["P1"],
        remaining_actions={"P1": 2},
    )
    p1 = s.players[PlayerId("P1")]
    cfg = Config()

    # Trigger -5 transition logic manually (or via damage)
    # Applying damage to reach -5 (should queue sacrifice BEFORE applying -5)
    apply_sanity_loss(s, p1, 1, source="TEST")
    _apply_minus5_transitions(s, cfg)
    
    # Check flag set
    pending = s.flags.get("PENDING_SACRIFICE_CHECK")
    if isinstance(pending, list):
        assert pending and pending[0] == "P1"
    else:
        assert pending == "P1"
    # Check NOT destroyed yet and sanity unchanged (pre-sacrifice)
    assert p1.keys == 2
    assert p1.sanity == -4
    assert not p1.at_minus5
    
    # Check legality: SACRIFICE options + ACCEPT
    legal = get_legal_actions(s, "P1")
    types = [a.type for a in legal]
    assert ActionType.SACRIFICE in types
    assert ActionType.ACCEPT_SACRIFICE in types
    
    # Execute SACRIFICE (solo opción: SANITY_MAX)
    s2 = step(s, Action(actor="P1", type=ActionType.SACRIFICE, data={"mode": "SANITY_MAX"}), None, cfg)
    assert s2.flags.get("PENDING_SACRIFICE_CHECK") is None
    assert s2.players[PlayerId("P1")].sanity == 0
    assert s2.players[PlayerId("P1")].sanity_max == 4
    assert s2.players[PlayerId("P1")].keys == 2 # Keys saved!


def test_pre_sacrifice_defers_damage():
    from engine.state_factory import make_game_state
    from engine.actions import Action, ActionType
    from engine.transition import step
    from engine.systems.sanity import apply_sanity_loss

    s = make_game_state(
        players={"P1": {"room": str(corridor_id(1)), "sanity": -4, "sanity_max": 5}},
        rooms=[str(corridor_id(1))],
        turn_order=["P1"],
        remaining_actions={"P1": 2},
    )
    p1 = s.players[PlayerId("P1")]
    cfg = Config()

    apply_sanity_loss(s, p1, 1, source="TEST", cfg=cfg)

    pending = s.flags.get("PENDING_SACRIFICE_CHECK")
    if isinstance(pending, list):
        assert pending and pending[0] == "P1"
    else:
        assert pending == "P1"
    assert p1.sanity == -4

    s2 = step(s, Action(actor="P1", type=ActionType.SACRIFICE, data={"mode": "SANITY_MAX"}), None, cfg)
    assert s2.players[PlayerId("P1")].sanity == 0
    assert s2.flags.get("PENDING_SACRIFICE_CHECK") is None


def test_auto_accept_when_no_sacrifice_options():
    from engine.state_factory import make_game_state
    from engine.systems.sanity import apply_sanity_loss

    s = make_game_state(
        players={
            "P1": {
                "room": str(corridor_id(1)),
                "sanity": -4,
                "sanity_max": -1,
                "keys": 2,
            },
            "P2": {"room": str(corridor_id(1)), "sanity": 3},
        },
        rooms=[str(corridor_id(1))],
        turn_order=["P1", "P2"],
        remaining_actions={"P1": 2, "P2": 2},
    )
    p1 = s.players[PlayerId("P1")]
    p1.object_slots_penalty = 99
    p2 = s.players[PlayerId("P2")]
    cfg = Config()

    apply_sanity_loss(s, p1, 1, source="TEST", cfg=cfg)

    assert s.flags.get("PENDING_SACRIFICE_CHECK") is None
    assert p1.sanity == cfg.S_LOSS
    assert p1.at_minus5 is True
    assert p1.keys == 0
    assert s.keys_destroyed == 2
    assert p2.sanity == 2
    

def test_trapped_duration():
    """Verifica que TRAPPED dura 3 turnos."""
    from engine.transition import _resolve_card_minimal
    from engine.state_factory import make_game_state
    from engine.types import CardId
    
    s = make_game_state(
        players={"P1": {"room": str(corridor_id(1)), "sanity": 5}},
        rooms=[str(corridor_id(1))],
        turn_order=["P1"],
        remaining_actions={"P1": 2},
    )
    p1 = s.players[PlayerId("P1")]
    
    # Simulate drawing TRAPPED state
    _resolve_card_minimal(s, PlayerId("P1"), CardId("STATE:TRAPPED"), Config())
    
    assert len(p1.statuses) == 1
    assert p1.statuses[0].status_id == "TRAPPED"
    assert p1.statuses[0].remaining_rounds == 3

def test_minus5_actions():
    """Verifica que estar en -5 mantiene 2 acciones."""
    from engine.transition import _start_new_round
    from engine.state_factory import make_game_state
    s = make_game_state(
        players={"P1": {"room": str(corridor_id(1)), "sanity": -5}},
        rooms=[str(corridor_id(1))],
        turn_order=["P1"],
        remaining_actions={"P1": 2},
    )
    
    _start_new_round(s, Config())
    assert s.remaining_actions[PlayerId("P1")] == 2

def test_frozen_queen_spawn():
    """Verifica que Reina Helada aparece en el pasillo."""
    from engine.transition import _resolve_card_minimal
    from engine.state_factory import make_game_state
    from engine.types import CardId
    
    # Player in F1_R1
    rid = room_id(1, 1)
    s = make_game_state(
        players={"P1": {"room": str(rid), "sanity": 5}},
        rooms=[str(rid)],
        turn_order=["P1"],
        remaining_actions={"P1": 2},
    )
    
    # Reveal Queen
    _resolve_card_minimal(s, PlayerId("P1"), CardId("MONSTER:REINA_HELADA"), Config())
    
    assert len(s.monsters) == 1
    # Should be in corridor F1_P, NOT room F1_R1
    assert str(s.monsters[0].room) == "F1_P"

def test_salon_belleza_threshold():
    """Verifica Vanidad desde 3er uso (>=3)."""
    from engine.state_factory import make_game_state
    from engine.transition import step
    from engine.actions import Action, ActionType
    rid = room_id(1, 1)
    s = make_game_state(
        players={"P1": {"room": str(rid), "sanity": 5}},
        rooms={str(rid): {"special_card_id": "SALON_BELLEZA", "special_revealed": True}},
        turn_order=["P1"],
        remaining_actions={"P1": 2},
        phase="PLAYER",
        king_floor=1,
    )
    
    # Use 1: Count becomes 1. No status.
    # Use 1: Count becomes 1. No status.
    s.remaining_actions[PlayerId("P1")] = 10
    s = step(s, Action(actor="P1", type=ActionType.USE_SALON_BELLEZA, data={}), None, Config())
    assert s.salon_belleza_uses == 1
    p1 = s.players[PlayerId("P1")]
    assert len(p1.statuses) == 0 # Just protection flag? No, statuses list is for StatusInstance. Flag is in s.flags.
    
    # Use 2: Count 2. No status.
    s = step(s, Action(actor="P1", type=ActionType.USE_SALON_BELLEZA, data={}), None, Config())
    assert s.salon_belleza_uses == 2
    p1 = s.players[PlayerId("P1")]
    assert len(p1.statuses) == 0
    
    # Use 3: Count 3. YES Vanidad.
    s = step(s, Action(actor="P1", type=ActionType.USE_SALON_BELLEZA, data={}), None, Config())
    assert s.salon_belleza_uses == 3
    p1 = s.players[PlayerId("P1")]
    assert any(st.status_id == "VANIDAD" for st in p1.statuses)

def test_king_single_action():
    """Verifica que la fase KING solo expone 1 acción."""
    from engine.state_factory import make_game_state
    from engine.legality import get_legal_actions
    from engine.actions import ActionType
    s = make_game_state(players={}, rooms=[], phase="KING", turn_order=[])
    legal = get_legal_actions(s, "KING")
    assert len(legal) == 1
    assert legal[0].type == ActionType.KING_ENDROUND

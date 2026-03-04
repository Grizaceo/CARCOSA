
import pytest
from engine.state_factory import make_game_state
from engine.types import PlayerId, RoomId
from engine.actions import Action, ActionType
from engine.transition import step
from engine.config import Config
from engine.rng import RNG
from engine.objects import OBJECT_CATALOG

def create_base_state():
    return make_game_state(
        players={"P1": {"room": "F1_R1", "sanity": 5, "sanity_max": 5}},
        rooms=["F1_R1"],
        turn_order=["P1"],
        remaining_actions={"P1": 2},
        phase="PLAYER",
        king_floor=1,
    )

def test_attach_tale_logic():
    """Verifica que unir cuentos consume el item e incrementa el contador."""
    s = create_base_state()
    p = s.players["P1"]
    
    # Setup: P1 tiene Cuento 1 y Libro (opcional, pero semántico)
    p.objects.append("TALE_REPAIRER")
    p.objects.append("BOOK_CHAMBERS")
    
    action = Action(actor="P1", type=ActionType.USE_ATTACH_TALE, data={"tale_id": "TALE_REPAIRER"})
    s = step(s, action, RNG(0), Config())
    
    assert "TALE_REPAIRER" not in s.players["P1"].objects
    assert s.chambers_tales_attached == 1
    assert s.flags.get("TALE_ATTACHED_TALE_REPAIRER")

def test_vanish_trigger():
    """Verifica que cada cuento activa Vanish por N rondas (N = número de cuentos unidos)."""
    tales = ["TALE_REPAIRER", "TALE_MASK", "TALE_DRAGON", "TALE_SIGN"]

    for i, tale_id in enumerate(tales):
        s = create_base_state()
        p = s.players["P1"]
        s.chambers_tales_attached = i  # ya tiene i cuentos unidos
        p.objects.append(tale_id)
        p.objects.append("BOOK_CHAMBERS")

        action = Action(actor="P1", type=ActionType.USE_ATTACH_TALE, data={"tale_id": tale_id})
        s = step(s, action, RNG(0), Config())

        expected = i + 1
        assert s.chambers_tales_attached == expected, f"Tale {i+1}: chambers_tales_attached debe ser {expected}"
        assert s.king_vanished_turns == expected, f"Tale {i+1}: king_vanished_turns debe ser {expected}"
        assert any(log.get("event") == "KING_VANISHED" for log in s.action_log), f"Tale {i+1}: debe haber log KING_VANISHED"

def test_king_vanish_skips_phase():
    """Verifica que si king_vanished_turns > 0, se salta la fase del Rey."""
    s = create_base_state()
    s.round = 2 # Ronda > 1 para que haya daño presencia normal
    s.king_floor = 1
    s.players["P1"].room = RoomId("F1_R1") # P1 en piso del Rey
    s.phase = "KING"
    
    # Caso Control: Sin Vanish -> Daño
    s_control = s.clone()
    action_king = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
    s_control = step(s_control, action_king, RNG(0), Config())
    
    # Presencia aplica daño en round 2
    # P1 (Sanity 5) -> sanity < 5 (por presencia)
    assert s_control.players["P1"].sanity < 5
    
    # Caso Test: Con Vanish -> No Daño, decrementa contador
    s.king_vanished_turns = 4
    s.phase = "KING"
    s = step(s, action_king, RNG(0), Config())
    
    assert s.players["P1"].sanity == 4 # Solo daño casa (-1), sin daño presencia
    assert s.king_vanished_turns == 3 # Decrementado

if __name__ == "__main__":
    try:
        test_attach_tale_logic()
        print("test_attach_tale_logic PASSED")
        test_vanish_trigger()
        print("test_vanish_trigger PASSED")
        test_king_vanish_skips_phase()
        print("test_king_vanish_skips_phase PASSED")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"FAILED: {e}")

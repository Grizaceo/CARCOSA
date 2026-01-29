from engine.state_factory import make_game_state
from engine.transition import _resolve_card_minimal
from engine.types import PlayerId, CardId
from engine.config import Config
from engine.board import corridor_id

def test_tue_tue_revelations():
    """
    Verifica la lógica progresiva de Tue-Tue:
    1a rev: -1 cordura
    2a rev: -2 cordura
    3a rev: Fija cordura en -5
    Nunca spawna como monstruo.
    """
    room = str(corridor_id(1))
    s = make_game_state(players={"P1": {"room": room, "sanity": 6}}, rooms=[room])
    p1 = s.players[PlayerId("P1")]
    cfg = Config()

    # Primera revelación
    # Simular carta "MONSTER:TUE_TUE"
    _resolve_card_minimal(s, PlayerId("P1"), CardId("MONSTER:TUE_TUE"), cfg)
    
    # Check 1: No spawna
    assert len(s.monsters) == 0
    # Check 2: Contador incrementa
    assert s.tue_tue_revelations == 1
    # Check 3: Sanity -1
    assert p1.sanity == 5

    # Segunda revelación
    _resolve_card_minimal(s, PlayerId("P1"), CardId("MONSTER:TUE_TUE"), cfg)
    assert s.tue_tue_revelations == 2
    assert p1.sanity == 3  # 5 - 2 = 3

    # Tercera revelación (ofrece sacrificio antes de llegar a -5)
    _resolve_card_minimal(s, PlayerId("P1"), CardId("MONSTER:TUE_TUE"), cfg)
    assert s.tue_tue_revelations == 3
    pending = s.flags.get("PENDING_SACRIFICE_CHECK")
    if isinstance(pending, list):
        assert pending and pending[0] == "P1"
    else:
        assert pending == "P1"
    assert p1.sanity == 3

def test_tue_tue_vanity_interaction():
    """
    Verifica que VANIDAD aplica a las pérdidas de Tue-Tue.
    """
    from engine.state import StatusInstance
    
    room = str(corridor_id(1))
    s = make_game_state(players={"P1": {"room": room, "sanity": 6}}, rooms=[room])
    p1 = s.players[PlayerId("P1")]
    p1.statuses.append(StatusInstance(status_id="VANIDAD", remaining_rounds=2))
    cfg = Config()

    # 1a rev: -1 base + 1 vanidad = -2
    _resolve_card_minimal(s, PlayerId("P1"), CardId("MONSTER:TUE_TUE"), cfg)
    assert p1.sanity == 4  # 6 - 2 = 4

    # 2a rev: -2 base + 1 vanidad = -3
    _resolve_card_minimal(s, PlayerId("P1"), CardId("MONSTER:TUE_TUE"), cfg)
    assert p1.sanity == 1  # 4 - 3 = 1

    # 3a rev: Ofrece sacrificio antes de fijar en -5 (ignora vanidad).
    # Regla: "Fijar ... en -5". Interpretamos que se ofrece sacrificio previo.
    _resolve_card_minimal(s, PlayerId("P1"), CardId("MONSTER:TUE_TUE"), cfg)
    pending = s.flags.get("PENDING_SACRIFICE_CHECK")
    if isinstance(pending, list):
        assert pending and pending[0] == "P1"
    else:
        assert pending == "P1"
    assert p1.sanity == 1

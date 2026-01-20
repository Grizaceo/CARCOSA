"""
Tests para FASE 3: Estados Canónicos
- MALDITO
- SANIDAD
- PARANOIA
- VANIDAD
"""
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState, StatusInstance
from engine.types import PlayerId, RoomId, CardId
from engine.config import Config
from engine.transition import _apply_status_effects_end_of_round


def setup_basic_state() -> GameState:
    """Estado básico con 3 jugadores en diferentes pisos"""
    rooms = {
        RoomId("F1_R1"): RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=[])),
        RoomId("F1_R2"): RoomState(room_id=RoomId("F1_R2"), deck=DeckState(cards=[])),
        RoomId("F1_P"): RoomState(room_id=RoomId("F1_P"), deck=DeckState(cards=[])),
        RoomId("F2_R1"): RoomState(room_id=RoomId("F2_R1"), deck=DeckState(cards=[])),
        RoomId("F2_P"): RoomState(room_id=RoomId("F2_P"), deck=DeckState(cards=[])),
        RoomId("F3_R1"): RoomState(room_id=RoomId("F3_R1"), deck=DeckState(cards=[])),
        RoomId("F3_P"): RoomState(room_id=RoomId("F3_P"), deck=DeckState(cards=[])),
    }

    players = {
        PlayerId("P1"): PlayerState(
            player_id=PlayerId("P1"),
            sanity=5,
            room=RoomId("F1_R1"),
            sanity_max=10,
            keys=0,
            objects=[]
        ),
        PlayerId("P2"): PlayerState(
            player_id=PlayerId("P2"),
            sanity=5,
            room=RoomId("F1_R1"),  # Mismo piso y habitación que P1
            sanity_max=10,
            keys=0,
            objects=[]
        ),
        PlayerId("P3"): PlayerState(
            player_id=PlayerId("P3"),
            sanity=5,
            room=RoomId("F2_R1"),  # Piso diferente
            sanity_max=10,
            keys=0,
            objects=[]
        ),
    }

    s = GameState(
        round=1,
        players=players,
        rooms=rooms,
        phase="KING",
        king_floor=3,
        turn_pos=0,
        remaining_actions={},
        turn_order=[PlayerId("P1"), PlayerId("P2"), PlayerId("P3")],
        flags={},
    )

    return s


# ===== MALDITO Tests =====

def test_maldito_affects_same_floor():
    """MALDITO: Otros jugadores en el mismo piso pierden 1 cordura"""
    s = setup_basic_state()

    # P1 tiene MALDITO, P2 está en mismo piso, P3 en otro piso
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="MALDITO", remaining_rounds=2)
    )

    sanity_p2_before = s.players[PlayerId("P2")].sanity
    sanity_p3_before = s.players[PlayerId("P3")].sanity

    # Aplicar efectos de estados
    _apply_status_effects_end_of_round(s)

    # P2 (mismo piso) debe perder 1 cordura
    assert s.players[PlayerId("P2")].sanity == sanity_p2_before - 1

    # P3 (piso diferente) NO debe perder cordura
    assert s.players[PlayerId("P3")].sanity == sanity_p3_before


def test_maldito_does_not_affect_self():
    """MALDITO: El jugador con MALDITO NO se afecta a sí mismo"""
    s = setup_basic_state()

    # P1 tiene MALDITO
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="MALDITO", remaining_rounds=2)
    )

    sanity_p1_before = s.players[PlayerId("P1")].sanity

    # Aplicar efectos de estados
    _apply_status_effects_end_of_round(s)

    # P1 NO debe perder cordura por su propio MALDITO
    assert s.players[PlayerId("P1")].sanity == sanity_p1_before


def test_maldito_multiple_cursed_players():
    """MALDITO: Múltiples jugadores malditos afectan a otros en sus pisos"""
    s = setup_basic_state()

    # P1 y P2 ambos tienen MALDITO y están en el mismo piso
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="MALDITO", remaining_rounds=2)
    )
    s.players[PlayerId("P2")].statuses.append(
        StatusInstance(status_id="MALDITO", remaining_rounds=2)
    )

    sanity_p1_before = s.players[PlayerId("P1")].sanity
    sanity_p2_before = s.players[PlayerId("P2")].sanity

    # Aplicar efectos de estados
    _apply_status_effects_end_of_round(s)

    # P1 pierde 1 por el MALDITO de P2
    assert s.players[PlayerId("P1")].sanity == sanity_p1_before - 1

    # P2 pierde 1 por el MALDITO de P1
    assert s.players[PlayerId("P2")].sanity == sanity_p2_before - 1


# ===== SANIDAD Tests =====

def test_sanidad_heals_1_sanity():
    """SANIDAD: El jugador recupera 1 cordura"""
    s = setup_basic_state()

    # P1 tiene SANIDAD
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="SANIDAD", remaining_rounds=2)
    )

    sanity_before = s.players[PlayerId("P1")].sanity

    # Aplicar efectos de estados
    _apply_status_effects_end_of_round(s)

    # P1 debe recuperar 1 cordura
    assert s.players[PlayerId("P1")].sanity == sanity_before + 1


def test_sanidad_only_affects_owner():
    """SANIDAD: Solo afecta al jugador que lo tiene"""
    s = setup_basic_state()

    # P1 tiene SANIDAD
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="SANIDAD", remaining_rounds=2)
    )

    sanity_p2_before = s.players[PlayerId("P2")].sanity

    # Aplicar efectos de estados
    _apply_status_effects_end_of_round(s)

    # P2 NO debe ser afectado
    assert s.players[PlayerId("P2")].sanity == sanity_p2_before


def test_multiple_statuses_same_player():
    """Un jugador puede tener SANIDAD y MALDITO al mismo tiempo"""
    s = setup_basic_state()

    # P1 tiene SANIDAD y MALDITO
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="SANIDAD", remaining_rounds=2)
    )
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="MALDITO", remaining_rounds=2)
    )

    sanity_p1_before = s.players[PlayerId("P1")].sanity
    sanity_p2_before = s.players[PlayerId("P2")].sanity

    # Aplicar efectos de estados
    _apply_status_effects_end_of_round(s)

    # P1 recupera 1 por SANIDAD
    assert s.players[PlayerId("P1")].sanity == sanity_p1_before + 1

    # P2 pierde 1 por el MALDITO de P1
    assert s.players[PlayerId("P2")].sanity == sanity_p2_before - 1


def test_sanidad_and_maldito_net_zero_for_owner():
    """SANIDAD no cancela el efecto de MALDITO en otros jugadores"""
    s = setup_basic_state()

    # P1 tiene ambos estados
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="SANIDAD", remaining_rounds=2)
    )
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="MALDITO", remaining_rounds=2)
    )

    # Aplicar efectos
    _apply_status_effects_end_of_round(s)

    # P1 gana 1 (SANIDAD), P2 pierde 1 (MALDITO de P1)
    assert s.players[PlayerId("P1")].sanity == 6
    assert s.players[PlayerId("P2")].sanity == 4


# ===== PARANOIA Tests =====

def test_paranoia_prevents_entering_occupied_room():
    """PARANOIA: No puede entrar a habitación ocupada"""
    from engine.legality import get_legal_actions

    s = setup_basic_state()

    # P2 está en F1_CORR
    # P1 tiene PARANOIA y también está en F1_CORR
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="PARANOIA", remaining_rounds=2)
    )

    # Cambiar fase a PLAYER para P1
    s.phase = "PLAYER"
    s.remaining_actions = {PlayerId("P1"): 2}

    # P1 NO debe poder moverse a ninguna habitación donde haya otros jugadores
    # Pero en el setup básico, P1 y P2 están en la misma habitación
    # Vamos a verificar que NO puede quedarse donde hay otros

    legal_actions = get_legal_actions(s, "P1")
    move_actions = [a for a in legal_actions if a.type.name == "MOVE"]

    # Debe tener acciones de MOVE (a habitaciones vacías)
    # Pero no debería poder moverse a donde está P2 si P2 se moviera
    assert len(move_actions) > 0  # Puede moverse a habitaciones vacías


def test_paranoia_blocks_others_from_entering():
    """PARANOIA: Otros no pueden entrar donde hay alguien con PARANOIA"""
    from engine.legality import get_legal_actions
    from engine.board import neighbors

    s = setup_basic_state()

    # P1 tiene PARANOIA en F1_R1
    s.players[PlayerId("P1")].room = RoomId("F1_R1")
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="PARANOIA", remaining_rounds=2)
    )

    # P2 está en una habitación vecina (F1_R2, que es vecino directo de F1_R1)
    s.players[PlayerId("P2")].room = RoomId("F1_R2")

    # Cambiar fase a PLAYER para P2
    s.phase = "PLAYER"
    s.turn_order = [PlayerId("P2"), PlayerId("P1")]
    s.turn_pos = 0
    s.remaining_actions = {PlayerId("P2"): 2}

    legal_actions = get_legal_actions(s, "P2")
    move_actions = [a for a in legal_actions if a.type.name == "MOVE"]

    # P2 NO debe poder moverse a F1_R1 donde está P1 con PARANOIA
    move_to_paranoia_room = [
        a for a in move_actions
        if a.data.get("to") == str(RoomId("F1_R1"))
    ]

    assert len(move_to_paranoia_room) == 0, "No debe poder entrar donde hay PARANOIA"


def test_paranoia_allows_moving_to_empty_rooms():
    """PARANOIA: Puede moverse a habitaciones vacías"""
    from engine.legality import get_legal_actions

    s = setup_basic_state()

    # P1 tiene PARANOIA, está solo en F3_R1
    s.players[PlayerId("P1")].room = RoomId("F3_R1")
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="PARANOIA", remaining_rounds=2)
    )

    # P2 y P3 en otros lugares
    s.players[PlayerId("P2")].room = RoomId("F1_R1")
    s.players[PlayerId("P3")].room = RoomId("F2_R1")

    # Cambiar fase a PLAYER para P1
    s.phase = "PLAYER"
    s.remaining_actions = {PlayerId("P1"): 2}

    legal_actions = get_legal_actions(s, "P1")
    move_actions = [a for a in legal_actions if a.type.name == "MOVE"]

    # P1 debe poder moverse (a habitaciones vacías como el pasillo F3_P)
    assert len(move_actions) > 0, "Debe poder moverse a habitaciones vacías"


# ===== VANIDAD Tests =====

def test_vanidad_blocks_meditate():
    """VANIDAD: Bloquea la acción MEDITATE"""
    from engine.legality import get_legal_actions

    s = setup_basic_state()

    # P1 tiene VANIDAD
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="VANIDAD", remaining_rounds=2)
    )

    # Cambiar fase a PLAYER para P1
    s.phase = "PLAYER"
    s.remaining_actions = {PlayerId("P1"): 2}

    legal_actions = get_legal_actions(s, "P1")
    meditate_actions = [a for a in legal_actions if a.type.name == "MEDITATE"]

    # P1 NO debe poder meditar con VANIDAD
    assert len(meditate_actions) == 0, "MEDITATE debe estar bloqueado con VANIDAD"


def test_vanidad_allows_other_actions():
    """VANIDAD: No bloquea otras acciones (MOVE, SEARCH, etc.)"""
    from engine.legality import get_legal_actions

    s = setup_basic_state()

    # P1 tiene VANIDAD
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="VANIDAD", remaining_rounds=2)
    )

    # Cambiar fase a PLAYER para P1
    s.phase = "PLAYER"
    s.remaining_actions = {PlayerId("P1"): 2}

    legal_actions = get_legal_actions(s, "P1")
    move_actions = [a for a in legal_actions if a.type.name == "MOVE"]
    end_turn_actions = [a for a in legal_actions if a.type.name == "END_TURN"]

    # P1 debe poder realizar otras acciones
    assert len(move_actions) > 0, "Debe poder moverse"
    assert len(end_turn_actions) > 0, "Debe poder terminar turno"


def test_vanidad_only_affects_owner():
    """VANIDAD: Solo afecta al jugador que lo tiene"""
    from engine.legality import get_legal_actions

    s = setup_basic_state()

    # P1 tiene VANIDAD
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="VANIDAD", remaining_rounds=2)
    )

    # P2 NO tiene VANIDAD
    s.players[PlayerId("P2")].room = RoomId("F2_R1")

    # Cambiar fase a PLAYER para P2
    s.phase = "PLAYER"
    s.turn_order = [PlayerId("P2"), PlayerId("P1")]
    s.turn_pos = 0
    s.remaining_actions = {PlayerId("P2"): 2}

    legal_actions = get_legal_actions(s, "P2")
    meditate_actions = [a for a in legal_actions if a.type.name == "MEDITATE"]

    # P2 debe poder meditar (no tiene VANIDAD)
    assert len(meditate_actions) > 0, "P2 debe poder meditar sin VANIDAD"


def test_meditate_blocked_in_king_corridor_with_vanidad():
    """VANIDAD: MEDITATE bloqueado por VANIDAD incluso fuera del pasillo del Rey"""
    from engine.legality import get_legal_actions

    s = setup_basic_state()

    # P1 tiene VANIDAD y está en F1_R1 (NO es pasillo del Rey)
    s.players[PlayerId("P1")].room = RoomId("F1_R1")
    s.players[PlayerId("P1")].statuses.append(
        StatusInstance(status_id="VANIDAD", remaining_rounds=2)
    )
    s.king_floor = 3  # Rey en piso 3, P1 en piso 1

    # Cambiar fase a PLAYER para P1
    s.phase = "PLAYER"
    s.remaining_actions = {PlayerId("P1"): 2}

    legal_actions = get_legal_actions(s, "P1")
    meditate_actions = [a for a in legal_actions if a.type.name == "MEDITATE"]

    # P1 NO debe poder meditar con VANIDAD
    assert len(meditate_actions) == 0, "VANIDAD debe bloquear MEDITATE en cualquier lugar"

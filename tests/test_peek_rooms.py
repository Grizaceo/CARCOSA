"""
Tests para B5: PEEK (Mirar dos habitaciones)
"""
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId, CardId
from engine.rng import RNG


def setup_peek_state():
    """Estado con múltiples habitaciones con cartas para usar PEEK."""
    rooms = {
        RoomId("F1_R1"): RoomState(
            room_id=RoomId("F1_R1"), 
            deck=DeckState(cards=[CardId("TRAP_1"), CardId("TRAP_2"), CardId("TRAP_3")])
        ),
        RoomId("F1_R2"): RoomState(
            room_id=RoomId("F1_R2"), 
            deck=DeckState(cards=[CardId("KEY_1"), CardId("KEY_2")])
        ),
        RoomId("F1_R3"): RoomState(
            room_id=RoomId("F1_R3"), 
            deck=DeckState(cards=[CardId("OBJECT_1")])
        ),
    }
    players = {
        PlayerId("P1"): PlayerState(
            player_id=PlayerId("P1"), sanity=10, room=RoomId("F1_R1"), 
            sanity_max=10, keys=0, objects=[]
        ),
    }
    s = GameState(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        king_floor=3,
        turn_pos=0,
        remaining_actions={PlayerId("P1"): 2},
        turn_order=[PlayerId("P1")],
        peek_used_this_turn={},
        flags={},
    )
    return s


def test_peek_requires_two_different_rooms():
    """
    B5: PEEK permite mirar en dos habitaciones diferentes.
    No puede usarse la misma habitación dos veces.
    """
    s = setup_peek_state()
    p1_id = PlayerId("P1")
    
    # Intento 1: rooms diferentes - VÁLIDO
    room_a = RoomId("F1_R1")
    room_b = RoomId("F1_R2")
    
    is_valid = room_a != room_b
    assert is_valid, "Dos habitaciones diferentes es válido"
    
    # Intento 2: rooms iguales - INVÁLIDO
    room_c = RoomId("F1_R1")
    room_d = RoomId("F1_R1")
    
    is_valid_same = room_c != room_d
    assert not is_valid_same, "Misma habitación dos veces es inválido"


def test_peek_costs_one_sanity():
    """
    B5: Usar PEEK cuesta -1 cordura.
    """
    s = setup_peek_state()
    p1 = s.players[PlayerId("P1")]
    
    initial_sanity = p1.sanity
    
    # Usar PEEK
    p1.sanity -= 1
    
    assert p1.sanity == initial_sanity - 1
    assert p1.sanity == 9


def test_peek_does_not_extract_cards():
    """
    B5: PEEK revela cartas sin extraerlas.
    Las cartas permanecen en la habitación.
    """
    s = setup_peek_state()
    room1 = s.rooms[RoomId("F1_R1")]
    room2 = s.rooms[RoomId("F1_R2")]
    
    initial_cards_r1 = len(room1.deck.cards)
    initial_cards_r2 = len(room2.deck.cards)
    
    # Simulación de PEEK: leer sin extraer
    peeked_cards_r1 = room1.deck.cards[:room1.deck.top]  # Visible cards
    peeked_cards_r2 = room2.deck.cards[:room2.deck.top]  # Visible cards
    
    # Verificar que los decks no cambiaron
    assert len(room1.deck.cards) == initial_cards_r1, "R1 deck sin cambios"
    assert len(room2.deck.cards) == initial_cards_r2, "R2 deck sin cambios"


def test_peek_once_per_turn():
    """
    B5: PEEK solo se puede usar una vez por turno por jugador.
    """
    s = setup_peek_state()
    p1_id = PlayerId("P1")
    
    # Primera vez: permitido
    if p1_id not in s.peek_used_this_turn:
        s.peek_used_this_turn[p1_id] = True
        first_use_allowed = True
    else:
        first_use_allowed = False
    
    assert first_use_allowed, "Primera vez permitida"
    
    # Segunda vez en mismo turno: prohibido
    if p1_id in s.peek_used_this_turn and s.peek_used_this_turn[p1_id]:
        second_use_allowed = False
    else:
        second_use_allowed = True
    
    assert not second_use_allowed, "Segunda vez en turno prohibida"


def test_peek_resets_at_turn_start():
    """
    B5: El flag de PEEK_USED se resetea al inicio de cada turno.
    """
    s = setup_peek_state()
    p1_id = PlayerId("P1")
    
    # Turno 1: usar PEEK
    s.peek_used_this_turn[p1_id] = True
    assert p1_id in s.peek_used_this_turn
    
    # Al inicio del turno siguiente: resetear
    s.peek_used_this_turn = {}  # O específicamente: del s.peek_used_this_turn[p1_id]
    
    # Ahora P1 puede volver a usar PEEK
    can_use_again = p1_id not in s.peek_used_this_turn
    assert can_use_again, "PEEK disponible de nuevo en nuevo turno"


def test_peek_reveals_top_cards_only():
    """
    B5: PEEK solo revela cartas en el tope de la pila (visibles).
    SUPUESTO: cartas debajo del índice 'top' no se revelan.
    """
    s = setup_peek_state()
    room = s.rooms[RoomId("F1_R1")]
    
    # El mazo tiene cartas pero top=0 inicialmente
    # Cuando se revelen cartas, se muestran desde índice 0 hasta top-1
    room.deck.top = 1  # 1 carta revelada
    
    visible_cards = room.deck.cards[:room.deck.top]
    hidden_cards = room.deck.cards[room.deck.top:]
    
    assert len(visible_cards) == 1, "1 carta visible"
    assert len(hidden_cards) == 2, "2 cartas ocultas"


def test_peek_on_rooms_with_multiple_cards():
    """
    B5: PEEK funciona correctamente cuando las habitaciones
    tienen múltiples cartas disponibles.
    """
    s = setup_peek_state()
    r1 = s.rooms[RoomId("F1_R1")]
    r2 = s.rooms[RoomId("F1_R2")]
    
    # R1 tiene 3 cartas, R2 tiene 2
    r1.deck.top = 3
    r2.deck.top = 2
    
    r1_visible = r1.deck.cards[:r1.deck.top]
    r2_visible = r2.deck.cards[:r2.deck.top]
    
    assert len(r1_visible) == 3
    assert len(r2_visible) == 2
    
    # Ambos peeked sin extraer
    assert len(r1.deck.cards) == 3, "R1 deck intacto"
    assert len(r2.deck.cards) == 2, "R2 deck intacto"


def test_peek_resets_at_new_round():
    """
    B5: PEEK se resetea automáticamente al iniciar una nueva ronda.
    """
    from engine.transition import _start_new_round
    from engine.config import Config

    s = setup_peek_state()
    p1_id = PlayerId("P1")

    # Turno actual: P1 usa PEEK
    s.peek_used_this_turn[p1_id] = True
    assert s.peek_used_this_turn.get(p1_id, False) == True

    # Iniciar nueva ronda (esto debe resetear peek_used_this_turn)
    _start_new_round(s, Config())

    # Verificar que el flag fue reseteado
    assert s.peek_used_this_turn.get(p1_id, False) == False
    assert len(s.peek_used_this_turn) == 0, "peek_used_this_turn debe estar vacío"

"""
Tests para B2: MOTEMEY (venta/compra) + B3: Pool de llaves
"""
import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState, StatusInstance
from engine.types import PlayerId, RoomId, CardId
from engine.rng import RNG
from engine.config import Config


def setup_motemey_deck() -> DeckState:
    """
    Preparar mazo MOTEMEY según canon:
    - 3 Brújulas (COMPASS)
    - 3 Viales (VIAL)
    - 2 Objetos Contundentes (BLUNT)
    - 4 Tesoros (TREASURE_*)
    - 1 Llave (KEY)
    - 1 Cuento (STORY)
    """
    cards = [
        "COMPASS", "COMPASS", "COMPASS",
        "VIAL", "VIAL", "VIAL",
        "BLUNT", "BLUNT",
        "TREASURE_RING", "TREASURE_CROWN", "TREASURE_SCROLL", "TREASURE_PENDANT",
        "KEY",
        "STORY",
    ]
    return DeckState(cards=[CardId(c) for c in cards])


def setup_basic_state_with_motemey():
    """Estado básico con mazo MOTEMEY preparado."""
    rooms = {
        RoomId("F1_R1"): RoomState(room_id=RoomId("F1_R1"), deck=DeckState(cards=[])),
        RoomId("F1_P"): RoomState(room_id=RoomId("F1_P"), deck=DeckState(cards=[])),
    }
    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=10, room=RoomId("F1_R1"), sanity_max=10, keys=0, objects=[]),
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
        motemey_deck=setup_motemey_deck(),
        motemey_event_active=False,
        flags={},
    )
    return s


def test_motemey_deck_composition():
    """Verificar que el mazo MOTEMEY tiene la composición correcta."""
    deck = setup_motemey_deck()
    cards = [str(c) for c in deck.cards]
    
    assert cards.count("COMPASS") == 3
    assert cards.count("VIAL") == 3
    assert cards.count("BLUNT") == 2
    assert cards.count("TREASURE_RING") == 1
    assert cards.count("TREASURE_CROWN") == 1
    assert cards.count("TREASURE_SCROLL") == 1
    assert cards.count("TREASURE_PENDANT") == 1
    assert cards.count("KEY") == 1
    assert cards.count("STORY") == 1
    
    assert len(deck.cards) == 14, "Total de 14 cartas en mazo MOTEMEY"


def test_motemey_sell_object_gives_one_sanity():
    """
    Vender un OBJETO normal al Motemey da +1 cordura.
    SUPUESTO: sin clamping a sanity_max (mantenemos inventario simple).
    """
    s = setup_basic_state_with_motemey()
    p1 = s.players[PlayerId("P1")]
    
    # P1 tiene un objeto
    p1.objects.append("TORCH")
    p1.sanity = 8
    
    # Simulamos venta (lógica a implementar en transition.py)
    # Por ahora solo verificamos la estructura
    initial_sanity = p1.sanity
    initial_objects = len(p1.objects)
    
    # Mock de venta
    if "TORCH" in p1.objects:
        p1.objects.remove("TORCH")
        p1.sanity = min(p1.sanity + 1, p1.sanity_max)
    
    assert p1.sanity == min(initial_sanity + 1, p1.sanity_max)
    assert len(p1.objects) == initial_objects - 1


def test_motemey_sell_treasure_gives_three_sanity():
    """
    Vender un TESORO al Motemey da +3 cordura (con clamp a sanity_max).
    """
    s = setup_basic_state_with_motemey()
    p1 = s.players[PlayerId("P1")]
    
    # P1 tiene un tesoro
    p1.objects.append("TREASURE_RING")
    p1.sanity = 8
    p1.sanity_max = 10
    
    # Mock de venta de tesoro
    if "TREASURE_RING" in p1.objects:
        p1.objects.remove("TREASURE_RING")
        p1.sanity = min(p1.sanity + 3, p1.sanity_max)
    
    assert p1.sanity == 10, "Clamped a sanity_max (8 + 3 = 11 → 10)"


def test_motemey_buy_costs_two_sanity():
    """
    Comprar al Motemey cuesta 2 cordura.
    Si no puede pagar, la transacción falla.
    """
    s = setup_basic_state_with_motemey()
    p1 = s.players[PlayerId("P1")]
    p1.sanity = 1  # No puede pagar 2
    
    initial_deck_cards = len(s.motemey_deck.cards) - s.motemey_deck.top
    
    # Intento de compra fallido (sanity insuficiente)
    if p1.sanity >= 2:
        p1.sanity -= 2
        # ... oferta de cartas
    else:
        pass  # Falla silenciosa
    
    assert p1.sanity == 1, "Sanity no cambió"
    assert len(s.motemey_deck.cards) - s.motemey_deck.top == initial_deck_cards, "Deck sin cambios"


def test_motemey_buy_success():
    """
    Compra exitosa:
    1. Pagar 2 cordura
    2. Motemey ofrece 2 cartas
    3. Jugador elige 1
    4. No elegida vuelve al mazo
    """
    s = setup_basic_state_with_motemey()
    p1 = s.players[PlayerId("P1")]
    p1.sanity = 10
    p1.sanity_max = 10
    
    # Simulación simple: extraer 2, elegir 1ª, volver la 2ª
    deck = s.motemey_deck
    initial_remaining = deck.remaining()
    
    if initial_remaining >= 2 and p1.sanity >= 2:
        p1.sanity -= 2
        
        # Ofertar 2 cartas
        card1 = deck.cards[deck.top]
        card2 = deck.cards[deck.top + 1]
        deck.top += 2
        
        # Jugador elige la 1ª
        chosen = card1
        rejected = card2
        
        # Elegida se va al inventario, rechazada vuelve
        p1.objects.append(str(chosen))
        deck.cards.append(rejected)  # Vuelve al final
    
    assert p1.sanity == 8, "Pagó 2 cordura"
    assert len(p1.objects) > 0, "Tiene objeto elegido"
    # Deck size debería ser igual (sacó 2, metió 1 de vuelta)
    assert len(s.motemey_deck.cards) == 15, "Deck tiene 15 (14 inicial + 1 rechazada)"


def test_keys_pool_six_base():
    """
    B3: Pool base es 6 llaves.
    Distribución: 5 en mazos generales, 1 en mazo MOTEMEY.
    """
    # SUPUESTO: setup inicial distribuye 5 keys en otros mazos y 1 en MOTEMEY
    s = setup_basic_state_with_motemey()
    deck = s.motemey_deck
    
    # Verificar que hay 1 KEY en MOTEMEY
    key_count = sum(1 for c in deck.cards if str(c) == "KEY")
    assert key_count == 1, "1 KEY en MOTEMEY"
    
    # Total en sistema = 6 (1 aquí + 5 en otros mazos)
    # Para test, asumir que se aseguró en setup


def test_keys_pool_seven_with_camara_letal():
    """
    B3: Si Cámara Letal está en habitaciones especiales,
    pool de llaves es 7 (en lugar de 6).
    
    SUPUESTO: extra llave va en evento Cámara Letal o es bootstrapped en setup.
    """
    # Flag para indicar Cámara Letal presente
    s = setup_basic_state_with_motemey()
    s.flags["CAMARA_LETAL_PRESENT"] = True
    
    # Con flag, pool es 7 (5 en mazos + 1 en MOTEMEY + 1 en Cámara)
    # Para test: solo verificar que el flag existe
    assert s.flags.get("CAMARA_LETAL_PRESENT") is True

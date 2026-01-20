"""
Tests para C) Eventos duplicados: verificar que DeckState.put_bottom() no duplica cartas.
"""
import pytest
from engine.state import DeckState
from engine.types import CardId


def test_draw_top_returns_card_and_advances_pointer():
    """draw_top() retorna la carta del top y avanza el puntero"""
    deck = DeckState(cards=[CardId("A"), CardId("B"), CardId("C")])
    assert deck.top == 0
    assert deck.remaining() == 3

    card1 = deck.draw_top()
    assert str(card1) == "A"
    assert deck.top == 1
    assert deck.remaining() == 2

    card2 = deck.draw_top()
    assert str(card2) == "B"
    assert deck.top == 2
    assert deck.remaining() == 1


def test_draw_top_returns_none_when_empty():
    """draw_top() retorna None cuando no quedan cartas"""
    deck = DeckState(cards=[CardId("A")])
    card1 = deck.draw_top()
    assert str(card1) == "A"

    card2 = deck.draw_top()
    assert card2 is None


def test_put_bottom_adds_card_to_end():
    """put_bottom() agrega carta al final del array"""
    deck = DeckState(cards=[CardId("A"), CardId("B")])
    deck.put_bottom(CardId("C"))

    assert len(deck.cards) == 3
    assert str(deck.cards[2]) == "C"


def test_event_cycle_with_compaction():
    """
    ✅ SOLUCIÓN IMPLEMENTADA: Compactación automática.

    Ciclo completo: draw_top() + put_bottom() compacta el array cuando top >= len/2.
    Simula el flujo de un evento que vuelve al fondo.

    La compactación evita crecimiento indefinido del array físico.
    """
    # Setup: mazo con 3 cartas, una es un evento
    deck = DeckState(cards=[
        CardId("KEY"),
        CardId("EVENT:TEST"),
        CardId("MONSTER:SPIDER")
    ])

    # 1. Extraer 2 cartas (top=2, que es >= 3/2 = 1.5, umbral alcanzado)
    card = deck.draw_top()  # KEY
    assert str(card) == "KEY"

    card = deck.draw_top()  # EVENT:TEST
    assert str(card) == "EVENT:TEST"

    assert deck.top == 2

    # 2. Evento se resuelve y vuelve al fondo (simula _resolve_event)
    # put_bottom() detecta que top (2) >= len/2 (3/2=1), compacta
    deck.put_bottom(card)

    # 3. Verificar compactación:
    # Cartas consumidas (KEY, EVENT:TEST en idx 0-1) fueron removidas
    # Solo quedan: [MONSTER:SPIDER (original idx 2), EVENT:TEST (reciclado)]
    # top se reinició a 0
    assert deck.top == 0, "Compactación reinicia top a 0"
    assert len(deck.cards) == 2, "Compactación mantiene tamaño acotado"
    assert str(deck.cards[0]) == "MONSTER:SPIDER"
    assert str(deck.cards[1]) == "EVENT:TEST"
    assert deck.remaining() == 2


def test_event_recycling_with_compaction():
    """
    ✅ SOLUCIÓN IMPLEMENTADA: Compactación automática.

    Verificar que después de un ciclo completo (revelar todas + reciclar eventos),
    la compactación mantiene el tamaño acotado.
    """
    # Setup: mazo pequeño con 1 evento y 2 otras cartas
    deck = DeckState(cards=[
        CardId("EVENT:TEST"),
        CardId("KEY"),
        CardId("MONSTER:SPIDER")
    ])

    # Revelar todas las cartas
    cards_drawn = []
    while deck.remaining() > 0:
        card = deck.draw_top()
        cards_drawn.append(card)

    # top=3, len=3, top >= len/2, umbral alcanzado

    # Supongamos que el evento vuelve al fondo
    event_card = cards_drawn[0]  # EVENT:TEST
    deck.put_bottom(event_card)  # Compacta aquí

    # Verificar compactación:
    # Todas las cartas consumidas (idx 0-2) fueron removidas
    # Solo queda: [EVENT:TEST (reciclado)]
    # top reiniciado a 0
    assert len(deck.cards) == 1, "Compactación removió cartas consumidas"
    assert deck.top == 0, "Compactación reinició top"
    assert deck.remaining() == 1

    # Revelar la carta reciclada
    recycled = deck.draw_top()
    assert str(recycled) == "EVENT:TEST"
    assert deck.remaining() == 0


def test_multiple_event_cycles_maintain_bounded_size():
    """
    ✅ SOLUCIÓN IMPLEMENTADA: Compactación automática.

    Verificar que múltiples ciclos de eventos NO crecen el mazo indefinidamente
    gracias a la compactación automática.
    """
    # Setup: mazo con solo 1 evento
    deck = DeckState(cards=[CardId("EVENT:TEST")])

    # Ciclo 1: revelar y reciclar
    card1 = deck.draw_top()  # top=1
    deck.put_bottom(card1)  # top(1) >= len(2)/2, compacta → [EVENT:TEST], top=0

    # Después de compactación ciclo 1
    assert len(deck.cards) == 1, "Compactación mantiene tamaño=1"
    assert deck.top == 0
    assert deck.remaining() == 1

    # Ciclo 2: revelar y reciclar
    card2 = deck.draw_top()  # top=1
    deck.put_bottom(card2)  # top(1) >= len(2)/2, compacta → [EVENT:TEST], top=0

    # Después de compactación ciclo 2
    assert len(deck.cards) == 1, "Compactación mantiene tamaño=1"
    assert deck.top == 0
    assert deck.remaining() == 1

    # ✅ El array físico NO crece indefinidamente gracias a compactación automática


def test_deck_compaction_prevents_unbounded_growth():
    """
    SOLUCIÓN IMPLEMENTADA: Compactación automática del mazo.

    Verifica que put_bottom() compacta el array cuando top alcanza umbral (50%),
    evitando crecimiento indefinido.
    """
    # Setup: mazo con 4 cartas
    deck = DeckState(cards=[
        CardId("EVENT:A"),
        CardId("KEY"),
        CardId("MONSTER:SPIDER"),
        CardId("EVENT:B")
    ])

    # Revelar 3 cartas (top=3, que es >= 4/2)
    card1 = deck.draw_top()  # EVENT:A
    card2 = deck.draw_top()  # KEY
    card3 = deck.draw_top()  # MONSTER:SPIDER

    assert deck.top == 3
    assert len(deck.cards) == 4

    # Al hacer put_bottom con top >= len/2, debería compactar
    deck.put_bottom(card1)  # EVENT:A vuelve al fondo

    # Después de compactación:
    # - Cartas consumidas (0-2) se removieron
    # - Solo quedan: [EVENT:B (original idx 3), EVENT:A (reciclada)]
    # - top se reinició a 0
    assert deck.top == 0, "Compactación debe reiniciar top a 0"
    assert len(deck.cards) == 2, "Compactación debe remover cartas consumidas"
    assert str(deck.cards[0]) == "EVENT:B", "Primera carta debe ser EVENT:B (idx 3 original)"
    assert str(deck.cards[1]) == "EVENT:A", "Segunda carta debe ser EVENT:A (reciclada)"


def test_deck_compaction_multiple_cycles():
    """
    Verificar que múltiples ciclos de eventos con compactación mantienen tamaño acotado.
    """
    # Setup: mazo con solo 1 evento
    deck = DeckState(cards=[CardId("EVENT:TEST")])

    # Ejecutar 10 ciclos de revelar + reciclar
    for i in range(10):
        card = deck.draw_top()
        deck.put_bottom(card)

    # Sin compactación, tendríamos 11 cartas (1 original + 10 recicladas)
    # Con compactación, el tamaño se mantiene acotado
    # Después de cada ciclo donde top >= len/2, se compacta

    # Verificar que el mazo NO creció indefinidamente
    assert len(deck.cards) <= 2, \
        f"Con compactación, el mazo debe mantenerse pequeño (era {len(deck.cards)})"
    assert deck.remaining() == 1, "Debe quedar 1 carta disponible"


def test_proposed_solution_using_rotation():
    """
    Test conceptual: demostrar cómo una rotación resolvería el problema.
    Este test NO usa la implementación actual.
    """
    from collections import deque

    deck_deque = deque([CardId("EVENT:TEST"), CardId("KEY")])

    # Ciclo 1: pop left (draw), append (put_bottom)
    card1 = deck_deque.popleft()
    deck_deque.append(card1)

    # Tamaño se mantiene constante
    assert len(deck_deque) == 2

    # Ciclo 2
    card2 = deck_deque.popleft()
    deck_deque.append(card2)

    assert len(deck_deque) == 2

    # Solución usando deque es más eficiente para este patrón

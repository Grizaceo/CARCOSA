"""
Tests para CORRECCIÓN D: Motemey - Sistema de Elección Integral

Verifica el sistema de elección de 2 pasos:
- BUY_START: Cobra -2 cordura, extrae 2 cartas, guarda pending_choice
- BUY_CHOOSE: Jugador elige carta (0 o 1), rechazada vuelve al fondo
- Replay determinista
- No duplicación de cartas
"""

import pytest
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId, CardId
from engine.actions import ActionType, Action
from engine.transition import step
from engine.legality import get_legal_actions
from engine.config import Config
from engine.rng import RNG


def make_motemey_state() -> GameState:
    """
    Setup para tests de Motemey: jugador en habitación MOTEMEY con deck.
    """
    motemey_room = RoomId("F1_R1")

    # Deck de Motemey con 4 cartas conocidas
    motemey_deck = DeckState(
        cards=[
            CardId("COMPASS"),
            CardId("VIAL"),
            CardId("BLUNT"),
            CardId("ROPE")
        ],
        top=0
    )

    s = GameState(
        round=1,
        players={
            PlayerId("P1"): PlayerState(
                player_id=PlayerId("P1"),
                sanity=5,
                room=motemey_room,
                sanity_max=5,
                keys=0,
                objects=[],
                soulbound_items=[],
                statuses=[]
            )
        },
        motemey_deck=motemey_deck,
        rooms={
            motemey_room: RoomState(
                room_id=motemey_room,
                deck=DeckState(cards=[]),
                special_card_id="MOTEMEY",
                special_revealed=True
            )
        },
        phase="PLAYER",
        turn_order=[PlayerId("P1")],
        remaining_actions={PlayerId("P1"): 2}
    )

    return s


def test_motemey_buy_start_creates_pending_choice():
    """
    BUY_START debe cobrar -2 cordura y crear pending_choice con 2 cartas.
    """
    s = make_motemey_state()
    p1 = s.players[PlayerId("P1")]

    # Verificar estado inicial
    assert p1.sanity == 5
    assert s.pending_motemey_choice is None
    assert s.motemey_deck.remaining() == 4

    # Ejecutar BUY_START
    action = Action(actor="P1", type=ActionType.USE_MOTEMEY_BUY_START, data={})
    s_new = step(s, action, RNG(1), Config())

    p1_new = s_new.players[PlayerId("P1")]

    # Verificar que cobró -2 cordura
    assert p1_new.sanity == 3

    # Verificar que creó pending_choice
    assert s_new.pending_motemey_choice is not None
    assert "P1" in s_new.pending_motemey_choice
    cards = s_new.pending_motemey_choice["P1"]
    assert len(cards) == 2
    assert cards[0] == CardId("COMPASS")
    assert cards[1] == CardId("VIAL")

    # Verificar que el deck avanzó 2 posiciones
    assert s_new.motemey_deck.top == 2
    assert s_new.motemey_deck.remaining() == 2


def test_motemey_buy_choose_gives_chosen_card():
    """
    BUY_CHOOSE debe dar la carta elegida y devolver la rechazada al fondo.
    """
    s = make_motemey_state()

    # Ejecutar BUY_START
    action_start = Action(actor="P1", type=ActionType.USE_MOTEMEY_BUY_START, data={})
    s = step(s, action_start, RNG(1), Config())

    # Verificar pending_choice
    assert s.pending_motemey_choice["P1"] == [CardId("COMPASS"), CardId("VIAL")]

    # Ejecutar BUY_CHOOSE eligiendo index 0 (COMPASS)
    action_choose = Action(actor="P1", type=ActionType.USE_MOTEMEY_BUY_CHOOSE, data={"chosen_index": 0})
    s_new = step(s, action_choose, RNG(1), Config())

    p1_new = s_new.players[PlayerId("P1")]

    # Verificar que recibió COMPASS
    assert "COMPASS" in p1_new.objects

    # Verificar que pending_choice se limpió
    assert s_new.pending_motemey_choice is None

    # Verificar que VIAL volvió al fondo del mazo
    # Deck original: [COMPASS, VIAL, BLUNT, ROPE], top=2 después de BUY_START
    # CORRECCIÓN C: La compactación automática se activa (top >= len/2)
    # Después de compactación + put_bottom: [BLUNT, ROPE, VIAL], top=0
    assert s_new.motemey_deck.cards[-1] == CardId("VIAL")
    assert len(s_new.motemey_deck.cards) == 3  # Compactado
    assert s_new.motemey_deck.top == 0  # Resetead por compactación


def test_motemey_buy_choose_alternate_choice():
    """
    BUY_CHOOSE con index 1 debe dar la segunda carta y devolver la primera al fondo.
    """
    s = make_motemey_state()

    # BUY_START
    s = step(s, Action(actor="P1", type=ActionType.USE_MOTEMEY_BUY_START, data={}), RNG(1), Config())

    # BUY_CHOOSE eligiendo index 1 (VIAL)
    s = step(s, Action(actor="P1", type=ActionType.USE_MOTEMEY_BUY_CHOOSE, data={"chosen_index": 1}), RNG(1), Config())

    p1 = s.players[PlayerId("P1")]

    # Verificar que recibió VIAL
    assert "VIAL" in p1.objects

    # Verificar que COMPASS volvió al fondo
    assert s.motemey_deck.cards[-1] == CardId("COMPASS")


def test_motemey_legality_only_choose_when_pending():
    """
    Cuando hay pending_choice, solo BUY_CHOOSE debe ser legal (no BUY_START).
    """
    s = make_motemey_state()

    # Estado inicial: BUY_START es legal
    acts_before = get_legal_actions(s, "P1")
    motemey_actions_before = [a for a in acts_before if "MOTEMEY" in a.type.value]

    # Debe tener BUY_START disponible
    assert any(a.type == ActionType.USE_MOTEMEY_BUY_START for a in motemey_actions_before)
    assert not any(a.type == ActionType.USE_MOTEMEY_BUY_CHOOSE for a in motemey_actions_before)

    # Ejecutar BUY_START
    s = step(s, Action(actor="P1", type=ActionType.USE_MOTEMEY_BUY_START, data={}), RNG(1), Config())

    # Estado con pending_choice: solo BUY_CHOOSE debe ser legal
    acts_after = get_legal_actions(s, "P1")
    motemey_actions_after = [a for a in acts_after if "MOTEMEY" in a.type.value]

    # NO debe tener BUY_START disponible
    assert not any(a.type == ActionType.USE_MOTEMEY_BUY_START for a in motemey_actions_after)

    # Debe tener 2 opciones de BUY_CHOOSE (index 0 y 1)
    choose_actions = [a for a in motemey_actions_after if a.type == ActionType.USE_MOTEMEY_BUY_CHOOSE]
    assert len(choose_actions) == 2
    assert any(a.data.get("chosen_index") == 0 for a in choose_actions)
    assert any(a.data.get("chosen_index") == 1 for a in choose_actions)


def test_motemey_replay_deterministic():
    """
    Mismo seed + mismas acciones deben producir mismo resultado.
    """
    def run_motemey_sequence(seed: int, chosen_index: int):
        s = make_motemey_state()
        rng = RNG(seed)

        # BUY_START
        s = step(s, Action(actor="P1", type=ActionType.USE_MOTEMEY_BUY_START, data={}), rng, Config())

        # BUY_CHOOSE
        s = step(s, Action(actor="P1", type=ActionType.USE_MOTEMEY_BUY_CHOOSE, data={"chosen_index": chosen_index}), rng, Config())

        return s

    # Misma secuencia, mismo seed
    s1 = run_motemey_sequence(seed=42, chosen_index=0)
    s2 = run_motemey_sequence(seed=42, chosen_index=0)

    # Deben tener mismo resultado
    assert s1.players[PlayerId("P1")].objects == s2.players[PlayerId("P1")].objects
    assert s1.motemey_deck.cards == s2.motemey_deck.cards
    assert s1.motemey_deck.top == s2.motemey_deck.top


def test_motemey_no_card_duplication():
    """
    Las cartas no deben duplicarse: carta elegida va al inventario, rechazada al fondo.
    """
    s = make_motemey_state()

    # Contar cartas iniciales
    total_cards_before = len(s.motemey_deck.cards)

    # BUY_START
    s = step(s, Action(actor="P1", type=ActionType.USE_MOTEMEY_BUY_START, data={}), RNG(1), Config())

    # BUY_CHOOSE
    s = step(s, Action(actor="P1", type=ActionType.USE_MOTEMEY_BUY_CHOOSE, data={"chosen_index": 0}), RNG(1), Config())

    # Contar cartas después
    cards_in_deck = len(s.motemey_deck.cards)
    cards_in_player = len(s.players[PlayerId("P1")].objects)

    # Total debe ser: deck (original + rejected) + player inventory
    # 4 cartas originales -> 2 en deck, 1 en pending (COMPASS), 1 rechazada (VIAL)
    # Después: 3 en deck (BLUNT, ROPE, VIAL), 1 en player (COMPASS)
    # Total: 3 + 1 = 4 (sin duplicación)
    assert cards_in_deck + cards_in_player == total_cards_before


def test_motemey_insufficient_sanity():
    """
    BUY_START no debe ser legal si el jugador tiene menos de 2 cordura.
    """
    s = make_motemey_state()
    p1 = s.players[PlayerId("P1")]
    p1.sanity = 1  # Insuficiente

    # Verificar que BUY_START NO es legal
    acts = get_legal_actions(s, "P1")
    assert not any(a.type == ActionType.USE_MOTEMEY_BUY_START for a in acts)


def test_motemey_insufficient_cards_in_deck():
    """
    BUY_START no debe ser legal si el mazo tiene menos de 2 cartas.
    """
    s = make_motemey_state()
    # Dejar solo 1 carta en el deck
    s.motemey_deck.top = 3  # Solo queda 1 carta (ROPE)

    # Verificar que BUY_START NO es legal
    acts = get_legal_actions(s, "P1")
    assert not any(a.type == ActionType.USE_MOTEMEY_BUY_START for a in acts)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

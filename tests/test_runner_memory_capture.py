from engine.actions import Action, ActionType
from engine.board import corridor_id, room_id
from engine.state_factory import make_game_state
from sim.runner import _capture_observed_cards


def _build_state():
    rooms = {
        str(room_id(1, 1)): {"cards": ["KEY"]},
        str(room_id(1, 2)): {"cards": ["MONSTER:SPIDER"]},
        str(room_id(1, 3)): {"cards": ["EVENT:SAFE"]},
        str(corridor_id(1)): {},
    }
    players = {"P1": {"room": str(room_id(1, 1)), "sanity": 5}}
    return make_game_state(
        round=1,
        players=players,
        rooms=rooms,
        phase="PLAYER",
        turn_order=["P1"],
        remaining_actions={"P1": 2},
    )


def test_capture_observed_cards_includes_hallway_peek():
    state = _build_state()
    action = Action(
        actor="P1",
        type=ActionType.PEEK_ROOM_DECK,
        data={"room_id": str(room_id(1, 2))},
    )

    observed = _capture_observed_cards(state, action, "P1", step_idx=10)

    assert len(observed) == 1
    assert observed[0].card_id == "MONSTER:SPIDER"
    assert observed[0].source_player == "P1"
    assert observed[0].seen_step == 10
    assert observed[0].observation_type == ActionType.PEEK_ROOM_DECK.value


def test_capture_observed_cards_includes_taberna_peeks():
    state = _build_state()
    action = Action(
        actor="P1",
        type=ActionType.USE_TABERNA_ROOMS,
        data={"room_a": str(room_id(1, 1)), "room_b": str(room_id(1, 3))},
    )

    observed = _capture_observed_cards(state, action, "P1", step_idx=11)

    cards = {entry.card_id for entry in observed}
    assert len(observed) == 2
    assert cards == {"KEY", "EVENT:SAFE"}


def test_capture_observed_cards_search_keeps_previous_behavior():
    state = _build_state()
    action = Action(actor="P1", type=ActionType.SEARCH, data={})

    observed = _capture_observed_cards(state, action, "P1", step_idx=3)

    assert len(observed) == 1
    assert observed[0].card_id == "KEY"
    assert observed[0].observation_type == ActionType.SEARCH.value

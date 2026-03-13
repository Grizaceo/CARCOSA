from engine.actions import ActionType
from engine.board import corridor_id, room_id
from engine.rng import RNG
from engine.state_factory import make_game_state
from train.carcosa_env import CarcosaEnv


def _make_env_with_state(state, seed: int = 123) -> CarcosaEnv:
    env = CarcosaEnv(seed=seed)
    env.reset(seed=seed)
    env.state = state
    env.rng = RNG(seed)
    env.step_count = 0
    env.shared_info_memory = {}
    env._reset_action_debug()
    return env


def test_requested_peek_illegal_reports_executed_fallback_action():
    state = make_game_state(
        players={"P1": {"room": str(room_id(1, 1)), "sanity": 5}},
        rooms={
            str(room_id(1, 1)): {"cards": ["KEY"]},
            str(corridor_id(1)): {},
        },
        phase="PLAYER",
        turn_order=["P1"],
        remaining_actions={"P1": 1},
    )
    env = _make_env_with_state(state)

    peek_action_id = CarcosaEnv.ACTION_TYPES.index(ActionType.PEEK_ROOM_DECK)
    _, _, _, _, info = env.step(peek_action_id)

    assert info["requested_action_type"] == ActionType.PEEK_ROOM_DECK.value
    assert info["requested_action_legal"] is False
    assert info["illegal_action_intent"] is True
    assert info["executed_action_type"] != ActionType.PEEK_ROOM_DECK.value
    assert info["requested_action_matched_executed"] is False
    assert info["action_selection_source"] in {"GUIDED_FALLBACK", "DETERMINISTIC_FALLBACK", "DEFAULT_END_TURN"}
    assert info["masked_out_action"] is True
    assert info["fallback_substitution"] is True

    env.close()


def test_requested_peek_legal_executes_peek_without_fallback():
    state = make_game_state(
        players={"P1": {"room": str(corridor_id(1)), "sanity": 5}},
        rooms={
            str(room_id(1, 1)): {"cards": ["EVENT:SAFE"]},
            str(room_id(1, 2)): {"cards": ["KEY"]},
            str(corridor_id(1)): {},
        },
        phase="PLAYER",
        turn_order=["P1"],
        remaining_actions={"P1": 1},
    )
    state.flags["PENDING_HALLWAY_PEEK"] = "P1"

    env = _make_env_with_state(state)

    peek_action_id = CarcosaEnv.ACTION_TYPES.index(ActionType.PEEK_ROOM_DECK)
    _, _, _, _, info = env.step(peek_action_id)

    assert info["requested_action_type"] == ActionType.PEEK_ROOM_DECK.value
    assert info["requested_action_legal"] is True
    assert info["illegal_action_intent"] is False
    assert info["executed_action_type"] == ActionType.PEEK_ROOM_DECK.value
    assert info["requested_action_matched_executed"] is True
    assert info["action_selection_source"] == "DIRECT_MATCH"
    assert info["peek_available"] is True
    assert info["masked_out_action"] is False
    assert info["fallback_substitution"] is False

    env.close()

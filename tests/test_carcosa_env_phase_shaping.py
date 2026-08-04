from engine.actions import Action, ActionType
from engine.board import room_id, corridor_id
from engine.state_factory import make_game_state
from train.carcosa_env import CarcosaEnv


def _make_state(keys_p1: int, keys_p2: int, room_p1: str, room_p2: str, umbral_node: str = "F2_P"):
    state = make_game_state(
        players={
            "P1": {"room": room_p1, "sanity": 5, "keys": keys_p1},
            "P2": {"room": room_p2, "sanity": 5, "keys": keys_p2},
        },
        rooms={
            str(room_id(1, 1)): {"cards": []},
            str(room_id(1, 2)): {"cards": []},
            str(room_id(2, 1)): {"cards": []},
            str(corridor_id(1)): {},
            str(corridor_id(2)): {},
        },
        phase="PLAYER",
        turn_order=["P1", "P2"],
        remaining_actions={"P1": 1, "P2": 1},
    )

    for player in state.players.values():
        player.at_umbral = str(player.room) == umbral_node
    return state


def test_phase2_reward_increases_when_team_gets_closer_to_umbral():
    env = CarcosaEnv(
        reward_key=0.0,
        reward_key_lost=0.0,
        reward_sanity_loss=0.0,
        reward_info_gain=0.0,
        reward_info_use=0.0,
        reward_info_realize=0.0,
        penalty_skip_info=0.0,
        penalty_miss_info=0.0,
        penalty_illegal_intent=0.0,
        penalty_critical_sanity=0.0,
        reward_phase2_umbral_progress=0.5,
        penalty_phase2_umbral_regress=-0.5,
        reward_phase2_sync_step=0.0,
        reward_phase2_sync_all=0.0,
    )

    prev_state = _make_state(2, 2, str(room_id(1, 2)), str(room_id(1, 1)))
    next_state = _make_state(2, 2, str(room_id(2, 1)), str(corridor_id(2)))

    reward = env._calculate_reward(
        prev_state=prev_state,
        next_state=next_state,
        action=Action(actor="P1", type=ActionType.MOVE, data={"to": str(room_id(2, 1))}),
        actor="P1",
        legal_actions=[],
        observations=[],
        illegal_action_intent=False,
    )

    assert reward > 0


def test_umbral_shaping_active_before_key_goal():
    """Línea [092]: el shaping de umbral es SIEMPRE activo (no solo phase2),
    para dar gradiente de victoria en cada paso."""
    env = CarcosaEnv(
        reward_key=0.0,
        reward_key_lost=0.0,
        reward_sanity_loss=0.0,
        reward_info_gain=0.0,
        reward_info_use=0.0,
        reward_info_realize=0.0,
        penalty_skip_info=0.0,
        penalty_miss_info=0.0,
        penalty_illegal_intent=0.0,
        penalty_critical_sanity=0.0,
        reward_phase2_umbral_progress=0.5,
        penalty_phase2_umbral_regress=-0.5,
        reward_phase2_sync_step=0.0,
        reward_phase2_sync_all=0.0,
    )

    prev_state = _make_state(1, 1, str(room_id(1, 2)), str(room_id(1, 1)))
    next_state = _make_state(1, 1, str(room_id(2, 1)), str(corridor_id(2)))

    reward = env._calculate_reward(
        prev_state=prev_state,
        next_state=next_state,
        action=Action(actor="P1", type=ActionType.MOVE, data={"to": str(room_id(2, 1))}),
        actor="P1",
        legal_actions=[],
        observations=[],
        illegal_action_intent=False,
    )

    assert reward > 0


def test_phase2_sync_bonus_applies_when_all_players_reach_umbral():
    env = CarcosaEnv(
        reward_key=0.0,
        reward_key_lost=0.0,
        reward_sanity_loss=0.0,
        reward_info_gain=0.0,
        reward_info_use=0.0,
        reward_info_realize=0.0,
        penalty_skip_info=0.0,
        penalty_miss_info=0.0,
        penalty_illegal_intent=0.0,
        penalty_critical_sanity=0.0,
        reward_phase2_umbral_progress=0.0,
        penalty_phase2_umbral_regress=0.0,
        reward_phase2_sync_step=0.0,
        reward_phase2_sync_all=1.5,
    )

    prev_state = _make_state(2, 2, str(room_id(2, 1)), str(room_id(2, 1)))
    next_state = _make_state(2, 2, str(corridor_id(2)), str(corridor_id(2)))

    reward = env._calculate_reward(
        prev_state=prev_state,
        next_state=next_state,
        action=Action(actor="P1", type=ActionType.MOVE, data={"to": str(corridor_id(2))}),
        actor="P1",
        legal_actions=[],
        observations=[],
        illegal_action_intent=False,
    )

    assert reward >= 1.5


def test_phase2_penalizes_exploration_actions_after_key_goal():
    env = CarcosaEnv(
        reward_key=0.0,
        reward_key_lost=0.0,
        reward_sanity_loss=0.0,
        reward_info_gain=0.0,
        reward_info_use=0.0,
        reward_info_realize=0.0,
        penalty_skip_info=0.0,
        penalty_miss_info=0.0,
        penalty_illegal_intent=0.0,
        penalty_critical_sanity=0.0,
        reward_phase2_umbral_progress=0.0,
        penalty_phase2_umbral_regress=0.0,
        reward_phase2_sync_step=0.0,
        reward_phase2_sync_all=0.0,
        penalty_phase2_explore=-0.2,
    )

    prev_state = _make_state(2, 2, str(room_id(2, 1)), str(room_id(2, 1)))
    next_state = _make_state(2, 2, str(room_id(2, 1)), str(room_id(2, 1)))

    reward = env._calculate_reward(
        prev_state=prev_state,
        next_state=next_state,
        action=Action(actor="P1", type=ActionType.SEARCH, data={}),
        actor="P1",
        legal_actions=[],
        observations=[],
        illegal_action_intent=False,
    )

    assert reward <= -0.2

from train.adaptive_finetune import (
    _classify_keys_goal_loss_reason,
    _classify_keys_goal_post_reach_reason,
)
from engine.actions import ActionType


def test_classify_keys_goal_loss_reason_minus5_priority():
    reason = _classify_keys_goal_loss_reason(
        entered_minus5_with_keys=True,
        executed_action_type=ActionType.ACCEPT_SACRIFICE.value,
    )
    assert reason == "minus5_with_keys"


def test_classify_keys_goal_loss_reason_accept_sacrifice():
    reason = _classify_keys_goal_loss_reason(
        entered_minus5_with_keys=False,
        executed_action_type=ActionType.ACCEPT_SACRIFICE.value,
    )
    assert reason == "accept_sacrifice"


def test_classify_keys_goal_loss_reason_fallback_action_label():
    reason = _classify_keys_goal_loss_reason(
        entered_minus5_with_keys=False,
        executed_action_type=ActionType.SEARCH.value,
    )
    assert reason == "action_SEARCH"


def test_classify_post_reach_reason_win():
    reason = _classify_keys_goal_post_reach_reason(
        outcome="WIN",
        outcome_raw="WIN",
        had_keys_and_all_at_umbral=True,
        keys_goal_lost_reason=None,
    )
    assert reason == "win"


def test_classify_post_reach_reason_lost_key_has_priority():
    reason = _classify_keys_goal_post_reach_reason(
        outcome="LOSE",
        outcome_raw="LOSE_KEYS_DESTROYED",
        had_keys_and_all_at_umbral=False,
        keys_goal_lost_reason="minus5_with_keys",
    )
    assert reason == "lost_4th_key::minus5_with_keys"


def test_classify_post_reach_reason_nonwin_despite_umbral():
    reason = _classify_keys_goal_post_reach_reason(
        outcome="LOSE",
        outcome_raw="LOSE_DECK",
        had_keys_and_all_at_umbral=True,
        keys_goal_lost_reason=None,
    )
    assert reason == "nonwin_despite_keys_and_umbral"


def test_classify_post_reach_reason_minus5_before_umbral():
    reason = _classify_keys_goal_post_reach_reason(
        outcome="LOSE",
        outcome_raw="LOSE_ALL_MINUS5 (HOUSE_LOSS)",
        had_keys_and_all_at_umbral=False,
        keys_goal_lost_reason=None,
    )
    assert reason == "lose_minus5_before_umbral"


def test_classify_post_reach_reason_timeout_before_umbral():
    reason = _classify_keys_goal_post_reach_reason(
        outcome="TIMEOUT",
        outcome_raw="",
        had_keys_and_all_at_umbral=False,
        keys_goal_lost_reason=None,
    )
    assert reason == "timeout_before_umbral"

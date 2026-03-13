from types import SimpleNamespace

from train.adaptive_finetune import compare_metrics_lexicographic


def _args(selector_profile: str = "default"):
    return SimpleNamespace(
        selector_profile=selector_profile,
        lex_eps_rate=0.0,
        lex_eps_reward=0.0,
        min_improvement=0.01,
        min_match_rate=0.0,
        max_fallback_substitution_rate=1.0,
        max_minus5_with_keys_rate=1.0,
    )


def _metrics(**kwargs):
    base = {
        "win_rate": 0.0,
        "win_given_reached_keys_goal": 0.0,
        "rate_reached_3_keys": 0.0,
        "rate_reached_4_keys": 0.0,
        "rate_reached_keys_goal": 0.0,
        "rate_all_near_umbral": 0.0,
        "key_destroyed_rate": 0.5,
        "minus5_rate": 0.5,
        "avg_reward": -10.0,
        "requested_executed_match_rate": 1.0,
        "fallback_substitution_rate": 0.0,
        "minus5_entry_with_keys_rate": 0.0,
        "score": 0.0,
    }
    base.update(kwargs)
    return base


def test_lexicographic_prefers_higher_win_rate_first():
    incumbent = _metrics(win_rate=0.00, avg_reward=-5.0, score=0.10)
    candidate = _metrics(win_rate=0.05, avg_reward=-20.0, score=0.02)

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, _args())

    assert accepted is True
    assert metric == "win_rate"
    assert delta > 0


def test_lexicographic_uses_keys_goal_when_win_rate_tied():
    incumbent = _metrics(rate_reached_keys_goal=0.10)
    candidate = _metrics(rate_reached_keys_goal=0.25)

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, _args())

    assert accepted is True
    assert metric == "rate_reached_keys_goal"
    assert delta > 0


def test_lexicographic_uses_win_given_keys_before_keys_goal_rate():
    incumbent = _metrics(win_rate=0.0, win_given_reached_keys_goal=0.10, rate_reached_keys_goal=0.50)
    candidate = _metrics(win_rate=0.0, win_given_reached_keys_goal=0.25, rate_reached_keys_goal=0.40)

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, _args())

    assert accepted is True
    assert metric == "win_given_reached_keys_goal"
    assert delta > 0


def test_lexicographic_prefers_lower_key_destroyed_rate():
    incumbent = _metrics(
        win_rate=0.0,
        rate_reached_keys_goal=0.4,
        rate_all_near_umbral=0.4,
        key_destroyed_rate=0.35,
    )
    candidate = _metrics(
        win_rate=0.0,
        rate_reached_keys_goal=0.4,
        rate_all_near_umbral=0.4,
        key_destroyed_rate=0.20,
    )

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, _args())

    assert accepted is True
    assert metric == "key_destroyed_rate"
    assert delta < 0


def test_lexicographic_falls_back_to_score_when_primary_metrics_tie():
    incumbent = _metrics(score=0.10)
    candidate = _metrics(score=0.13)

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, _args())

    assert accepted is True
    assert metric == "score_tiebreak"
    assert delta > 0


def test_action_gate_rejects_candidate_with_low_match_rate():
    args = _args()
    args.min_match_rate = 0.85

    incumbent = _metrics(requested_executed_match_rate=0.90, fallback_substitution_rate=0.10)
    candidate = _metrics(
        requested_executed_match_rate=0.70,
        fallback_substitution_rate=0.05,
        win_rate=0.5,
    )

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, args)

    assert accepted is False
    assert metric == "action_gate_match"
    assert delta < 0


def test_action_gate_rejects_candidate_with_high_fallback_substitution():
    args = _args()
    args.max_fallback_substitution_rate = 0.15

    incumbent = _metrics(requested_executed_match_rate=0.90, fallback_substitution_rate=0.10)
    candidate = _metrics(
        requested_executed_match_rate=0.95,
        fallback_substitution_rate=0.40,
        win_rate=0.5,
    )

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, args)

    assert accepted is False
    assert metric == "action_gate_fallback"
    assert delta > 0


def test_risk_gate_rejects_candidate_with_high_minus5_with_keys_rate():
    args = _args()
    args.max_minus5_with_keys_rate = 0.20

    incumbent = _metrics(minus5_entry_with_keys_rate=0.10)
    candidate = _metrics(minus5_entry_with_keys_rate=0.35, win_rate=0.5)

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, args)

    assert accepted is False
    assert metric == "risk_gate_minus5_with_keys"
    assert delta > 0


def test_funnel_profile_prioritizes_rate_reached_3_keys_first():
    args = _args(selector_profile="funnel")
    incumbent = _metrics(rate_reached_3_keys=0.10, rate_reached_4_keys=0.02, win_given_reached_keys_goal=0.50)
    candidate = _metrics(rate_reached_3_keys=0.30, rate_reached_4_keys=0.01, win_given_reached_keys_goal=0.10)

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, args)

    assert accepted is True
    assert metric == "rate_reached_3_keys"
    assert delta > 0


def test_funnel_profile_checks_rate_reached_4_keys_before_win_given_keys():
    args = _args(selector_profile="funnel")
    incumbent = _metrics(rate_reached_3_keys=0.20, rate_reached_4_keys=0.12, win_given_reached_keys_goal=0.10)
    candidate = _metrics(rate_reached_3_keys=0.20, rate_reached_4_keys=0.05, win_given_reached_keys_goal=0.80)

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, args)

    assert accepted is False
    assert metric == "rate_reached_4_keys"
    assert delta < 0


def test_funnel_profile_prioritizes_minus5_with_keys_before_win_given_keys():
    args = _args(selector_profile="funnel")
    incumbent = _metrics(
        rate_reached_3_keys=0.2,
        rate_reached_4_keys=0.1,
        minus5_entry_with_keys_rate=0.10,
        win_given_reached_keys_goal=0.10,
    )
    candidate = _metrics(
        rate_reached_3_keys=0.2,
        rate_reached_4_keys=0.1,
        minus5_entry_with_keys_rate=0.30,
        win_given_reached_keys_goal=0.80,
    )

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, args)

    assert accepted is False
    assert metric == "minus5_entry_with_keys_rate"
    assert delta > 0


def test_funnel_k4_profile_prioritizes_rate_reached_4_keys_before_rate_reached_3_keys():
    args = _args(selector_profile="funnel_k4")
    incumbent = _metrics(rate_reached_3_keys=0.20, rate_reached_4_keys=0.00)
    candidate = _metrics(rate_reached_3_keys=0.10, rate_reached_4_keys=0.05)

    accepted, metric, delta = compare_metrics_lexicographic(candidate, incumbent, args)

    assert accepted is True
    assert metric == "rate_reached_4_keys"
    assert delta > 0

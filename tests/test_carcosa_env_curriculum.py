from train.carcosa_env import CarcosaEnv


def test_closing_curriculum_assigns_keys_goal_and_flag():
    env = CarcosaEnv(
        seed=123,
        curriculum_closing_prob=1.0,
        curriculum_keys_start=4,
        curriculum_far_player_prob=0.0,
    )

    env.reset(seed=123)

    total_keys = sum(player.keys for player in env.state.players.values())
    assert total_keys >= env.cfg.KEYS_TO_WIN
    assert env.state.flags.get("CURRICULUM_CLOSING_ACTIVE") is True

    env.close()


def test_closing_curriculum_can_force_one_far_player_from_umbral():
    env = CarcosaEnv(
        seed=456,
        curriculum_closing_prob=1.0,
        curriculum_keys_start=4,
        curriculum_far_player_prob=1.0,
    )

    env.reset(seed=456)

    distances = [env._distance_to_umbral(env.state, player.room) for player in env.state.players.values()]
    assert max(distances) > 0

    env.close()


def test_keys34_curriculum_sets_midgame_keys_and_flag():
    env = CarcosaEnv(
        seed=789,
        curriculum_keys34_prob=1.0,
        curriculum_keys34_min_keys=2,
        curriculum_keys34_max_keys=3,
        curriculum_closing_prob=0.0,
    )

    env.reset(seed=789)

    total_keys = sum(player.keys for player in env.state.players.values())
    assert 2 <= total_keys <= 3
    assert env.state.flags.get("CURRICULUM_KEYS34_ACTIVE") is True
    assert env.state.flags.get("CURRICULUM_CLOSING_ACTIVE") is None

    env.close()


def test_keys34_curriculum_assigns_fragile_carriers():
    env = CarcosaEnv(
        seed=790,
        curriculum_keys34_prob=1.0,
        curriculum_keys34_min_keys=2,
        curriculum_keys34_max_keys=2,
        curriculum_keys34_fragile_sanity_min=-4,
        curriculum_keys34_fragile_sanity_max=-3,
        curriculum_keys34_fragile_carriers=1,
        curriculum_closing_prob=0.0,
    )

    env.reset(seed=790)

    carriers = [player for player in env.state.players.values() if player.keys > 0]
    assert carriers
    assert any(-4 <= player.sanity <= -3 for player in carriers)

    env.close()

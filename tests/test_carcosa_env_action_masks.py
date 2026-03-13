import numpy as np

from train.carcosa_env import CarcosaEnv


def test_action_masks_returns_boolean_vector_matching_legal_actions():
    env = CarcosaEnv(seed=101)
    _, info = env.reset(seed=101)

    mask_bool = env.action_masks()
    mask_float = info["legal_actions"]

    assert mask_bool.dtype == np.bool_
    assert mask_bool.shape == mask_float.shape
    assert np.array_equal(mask_bool.astype(np.float32), mask_float)

    env.close()


def test_action_masks_all_true_during_king_phase():
    env = CarcosaEnv(seed=202)
    env.reset(seed=202)
    env.state.phase = "KING"

    mask_bool = env.action_masks()

    assert mask_bool.dtype == np.bool_
    assert mask_bool.all()

    env.close()


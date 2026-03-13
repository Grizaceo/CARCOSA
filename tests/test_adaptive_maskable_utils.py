from train.adaptive_finetune import _normalize_algorithm_name


def test_normalize_algorithm_name_accepts_maskable_aliases():
    assert _normalize_algorithm_name("maskable") == "maskable_ppo"
    assert _normalize_algorithm_name("maskableppo") == "maskable_ppo"
    assert _normalize_algorithm_name("maskable_ppo") == "maskable_ppo"


def test_normalize_algorithm_name_defaults_to_ppo():
    assert _normalize_algorithm_name(None) == "ppo"
    assert _normalize_algorithm_name("") == "ppo"
    assert _normalize_algorithm_name("ppo") == "ppo"


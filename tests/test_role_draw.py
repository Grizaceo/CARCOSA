import pytest

from engine.roles import draw_roles
from engine.rng import RNG


def test_role_draw_random_unique_snapshot():
    player_ids = ["P1", "P2", "P3", "P4"]
    role_pool = ["HEALER", "TANK", "HIGH_ROLLER", "SCOUT", "BRAWLER", "PSYCHIC"]
    roles = draw_roles(player_ids, "RANDOM_UNIQUE", role_pool, RNG(42))

    assert roles == {
        "P1": "PSYCHIC",
        "P2": "HEALER",
        "P3": "BRAWLER",
        "P4": "HIGH_ROLLER",
    }


def test_role_draw_random_unique_pool_insufficient():
    with pytest.raises(ValueError):
        draw_roles(["P1", "P2"], "RANDOM_UNIQUE", ["HEALER"], RNG(1))

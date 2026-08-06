"""Tests for spawn randomization (domain randomization, Pezza AI Gladiators).

Verifica que _apply_spawn_randomization:
- No baje sanity por debajo de 1.
- No altere sanity_max (preserva identidad del rol).
- Position shuffle use solo corridors válidos.
- Key distribution no supere KEYS_TOTAL.
- Con jitter=0 (default), el estado canónico no se altera.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from train.carcosa_env import CarcosaEnv
from sim.runner import make_smoke_state
from engine.config import Config


def test_spawn_off_does_not_mutate():
    """Con jitter=0 y positions=False, el estado debe ser canónico."""
    env = CarcosaEnv(king_enabled=False)
    obs, info = env.reset(seed=42)
    for p in env.state.players.values():
        # sanity debe ser igual a sanity_max canónico
        from engine.roles import get_sanity_max
        assert p.sanity == get_sanity_max(p.role_id), (
            f"Sanity {p.sanity} != canonical {get_sanity_max(p.role_id)} for {p.role_id}"
        )
        assert p.keys == 0
    env.close()


def test_spawn_sanity_jitter_floor():
    """sanity nunca baja de 1 con jitter alto."""
    env = CarcosaEnv(spawn_sanity_jitter=10, king_enabled=False)
    for seed in range(50):
        env.reset(seed=seed)
        for p in env.state.players.values():
            assert p.sanity >= 1, f"sanity={p.sanity} < 1 for {p.role_id} seed={seed}"
    env.close()


def test_spawn_sanity_max_preserved():
    """sanity_max NO se altera por la jitter (preserva identidad del rol)."""
    env = CarcosaEnv(spawn_sanity_jitter=5, king_enabled=False)
    for seed in range(30):
        env.reset(seed=seed)
        for p in env.state.players.values():
            from engine.roles import get_sanity_max
            canonical = get_sanity_max(p.role_id)
            assert p.sanity_max == canonical, (
                f"sanity_max={p.sanity_max} != canonical {canonical} for {p.role_id}"
            )
    env.close()


def test_spawn_positions_in_corridors():
    """Posiciones iniciales son siempre corridors válidos."""
    env = CarcosaEnv(spawn_randomize_positions=True, king_enabled=False)
    from engine.board import is_corridor
    for seed in range(50):
        env.reset(seed=seed)
        for p in env.state.players.values():
            assert is_corridor(p.room), f"Room {p.room} is not a corridor seed={seed}"
    env.close()


def test_spawn_key_jitter_bound():
    """Keys_totales en spawn no superan KEYS_TOTAL."""
    env = CarcosaEnv(spawn_key_distribution_jitter=1.0, king_enabled=False)
    for seed in range(50):
        env.reset(seed=seed)
        total = sum(p.keys for p in env.state.players.values())
        assert total <= env.cfg.KEYS_TOTAL, f"total keys={total} > KEYS_TOTAL={env.cfg.KEYS_TOTAL}"
    env.close()


def test_spawn_reproducible_with_same_seed():
    """Mismo seed produce mismo estado perturbado (determinismo)."""
    env1 = CarcosaEnv(spawn_sanity_jitter=3, spawn_randomize_positions=True, king_enabled=False)
    env2 = CarcosaEnv(spawn_sanity_jitter=3, spawn_randomize_positions=True, king_enabled=False)
    env1.reset(seed=123)
    env2.reset(seed=123)
    for pid in env1.state.players:
        p1 = env1.state.players[pid]
        p2 = env2.state.players[pid]
        assert p1.sanity == p2.sanity, f"sanity differs: {p1.sanity} vs {p2.sanity}"
        assert p1.room == p2.room, f"room differs: {p1.room} vs {p2.room}"
    env1.close()
    env2.close()


def test_obs_shape_invariant():
    """Observation shape es 167 siempre, sin importar jitter."""
    import numpy as np
    for jitter in [0, 1, 2, 5]:
        env = CarcosaEnv(spawn_sanity_jitter=jitter, spawn_randomize_positions=True, king_enabled=False)
        obs, _ = env.reset(seed=7)
        assert obs.shape == (167,), f"jitter={jitter}: obs.shape={obs.shape}"
        assert not np.any(np.isnan(obs))
        env.close()


if __name__ == "__main__":
    test_spawn_off_does_not_mutate()
    test_spawn_sanity_jitter_floor()
    test_spawn_sanity_max_preserved()
    test_spawn_positions_in_corridors()
    test_spawn_key_jitter_bound()
    test_spawn_reproducible_with_same_seed()
    test_obs_shape_invariant()
    print("--- ALL SPAWN RANDOMIZATION TESTS PASSED ---")

from engine.rng import RNG


def test_rng_reproducible():
    r1 = RNG(123)
    r2 = RNG(123)

    seq1 = [r1.randint(1, 6) for _ in range(20)]
    seq2 = [r2.randint(1, 6) for _ in range(20)]
    assert seq1 == seq2


def test_rng_fork_deterministic():
    base = RNG(999)
    a = base.fork("rollout-A")
    b = base.fork("rollout-A")
    c = base.fork("rollout-C")

    assert [a.randint(1, 100) for _ in range(10)] == [b.randint(1, 100) for _ in range(10)]
    assert [a.randint(1, 100) for _ in range(3)] != [c.randint(1, 100) for _ in range(3)]

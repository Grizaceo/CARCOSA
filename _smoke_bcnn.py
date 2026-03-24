"""Quick smoke test for BCNNPlayerPolicy."""
import sys
try:
    from sim.policies import BCNNPlayerPolicy
    p = BCNNPlayerPolicy()
    print("BCNNPlayerPolicy: checkpoint loaded OK")
    print(f"Action mapping (index→type): {p._index_to_action_type}")
    print(f"Model: {p._model}")

    # Run one full episode to verify choose() works end-to-end
    from sim.runner import make_smoke_state
    from engine.rng import RNG
    from engine.legality import get_legal_actions
    rng = RNG(42)
    state = make_smoke_state(seed=42)
    action = p.choose(state, rng)
    print(f"First action chosen: {action.type} (actor={action.actor})")
    print("SMOKE TEST PASSED")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)

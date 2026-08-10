"""
P0 ORACULO: techo de ganabilidad con MCTS barato (rollout random).

MIDE: cuantas seeds de N son ganables EN PRINCIPIO por un MCTS con
rollout policy RANDOM (busca por fuerza bruta, sin heurística).

POR QUE random y no GoalDirected: el rollout GoalDirected cuesta ~10x
más (cada simulación corre la heurística completa). Con random, 200
rollouts = 2.7s/turno; un episodio ~60 turnos => ~3min/partida.
Con 8 workers y 30 seeds => ~12-15 min.

USO:
  python3 train/oracle_mcts.py --seeds 30 --rollouts 300 --depth 30 --workers 8

INTERPRETACION:
  - win-rate alto (>25%) => hay techo, el 30% es alcanzable con mejor policy
  - win-rate ~21% => el techo está cerca del committee actual (saturación)
  - win-rate <15% => el juego es casi inganable; re-pensar diseño
"""

import sys
import time
import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def _oracle_episode(seed, rollouts, depth, cfg):
    from sim.runner import make_smoke_state
    from engine.rng import RNG
    from engine.transition import step
    from sim.mcts import mcts_search
    from sim.policies import RandomPolicy, RandomKingPolicy
    from engine.actions import Action, ActionType
    from engine.legality import get_legal_actions

    rp = RandomPolicy(cfg)
    kp = RandomKingPolicy(cfg)

    def roll(st, rng):
        active = st.turn_order[st.turn_pos] if st.phase == "PLAYER" else "KING"
        if active == "KING":
            return kp.choose(st, rng) or Action(
                actor="KING", type=ActionType.KING_ENDROUND, data={}
            )
        act = rp.choose(st, rng)
        return act or Action(actor=str(active), type=ActionType.END_TURN, data={})

    st = make_smoke_state(seed=seed, cfg=cfg)
    rng = RNG(seed)
    max_steps = 4000
    for _ in range(max_steps):
        if st.game_over:
            break
        # Sacrifice Interrupt (igual que runner.py): solo el pendiente actúa
        pending = st.flags.get("PENDING_SACRIFICE_CHECK")
        if isinstance(pending, list):
            pending = pending[0] if pending else None
        if pending:
            legal = get_legal_actions(st, str(pending))
            action = (
                legal[0]
                if legal
                else Action(actor=str(pending), type=ActionType.END_TURN, data={})
            )
        elif st.phase == "PLAYER":
            actor = str(st.turn_order[st.turn_pos])
            legal = get_legal_actions(st, actor)
            best = mcts_search(
                st, cfg, rng, actor, roll, roll, num_rollouts=rollouts, max_depth=depth
            )
            # Guard de legalidad: si MCTS devolvió algo no legal, usar el
            # primero legal (nunca END_TURN ciego — el engine lo rechaza).
            if best is not None and best in legal:
                action = best
            elif legal:
                action = legal[0]
            else:
                action = Action(actor=actor, type=ActionType.END_TURN, data={})
        else:
            action = roll(st, rng)
        st = step(st, action, rng)
    return {"win": st.outcome == "WIN", "outcome": st.outcome, "round": st.round}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--rollouts", type=int, default=300)
    ap.add_argument("--depth", type=int, default=30)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    import multiprocessing as mp
    from functools import partial
    from engine.config import Config

    cfg = Config()
    ctx = mp.get_context("spawn")
    fn = partial(_oracle_episode, rollouts=args.rollouts, depth=args.depth, cfg=cfg)
    seeds = list(range(args.seeds))

    t0 = time.time()
    print(
        f"ORACLE MCTS: {args.seeds} seeds, {args.rollouts} rollouts, depth {args.depth}, {args.workers} workers",
        flush=True,
    )
    with ctx.Pool(args.workers) as pool:
        results = pool.map(fn, seeds)
    dt = time.time() - t0

    wins = sum(1 for r in results if r["win"])
    wr = wins / len(seeds)
    print("\n=== ORACLE MCTS RESULT ===")
    print(f"win-rate: {wr * 100:.1f}% ({wins}/{len(seeds)})")
    print(f"tiempo: {dt:.0f}s ({dt / 60:.1f} min)")
    print(f"outcomes: { {r['outcome'].split(' ')[0] for r in results} }")
    # detalle por seed
    print("\npor seed:")
    for s, r in zip(seeds, results):
        print(
            f"  seed {s:3d}: {'WIN' if r['win'] else r['outcome'].split(' ')[0]:<20} round {r['round']}"
        )

    out = (
        REPO
        / "reports"
        / f"oracle_mcts_{args.seeds}seeds_{args.rollouts}ro_{args.depth}d.json"
    )
    import json

    json.dump(
        {
            "seeds": seeds,
            "rollouts": args.rollouts,
            "depth": args.depth,
            "results": results,
            "win_rate": wr,
            "n_wins": wins,
        },
        open(out, "w"),
        indent=2,
    )
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()

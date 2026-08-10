"""
Barrido de configuraciones de King para CARCOSA (línea [092]).

MOTIVACIÓN (diagnóstico 2026-08-04, 1501 runs GOAL con outcome real):
  - 65% LOSE_ALL_MINUS5 (sanity a -5, avg ronda 33), 27% LOSE_KEYS_DESTROYED
    (avg ronda 29, ~2.8 keys destruidas), 8.6% WIN (avg ronda 15).
  - Las victorias son RÁPIDAS (ronda ~15); las derrotas se arrastran (ronda 29-33).
  - El King empieza en ronda 2 y destruye llaves acumulativamente (2.8 en
    derrotas vs 0.1 en victorias). La presión es demasiado temprana y fuerte.

HIPÓTESIS del barrido (qué cambia y por qué):
  A) KING_PRESENCE_START_ROUND: 2 -> 6/8. Si el King entra más tarde, los bots
     tienen más rondas para acumular keys antes de la sangría de sanidad.
  B) KEYS_TOTAL 6 -> 7: más llaves en juego aminora el LOSE_KEYS_DESTROYED
     (se necesitan destruir más para llegar al umbral).
  C) MAX_ROUNDS 60 -> 90: más tiempo para completar victorias lentas; hoy el
     TIMEOUT (~59/60) corta antes de que la victoria emerja.
  Hay que PROBAR las hipótesis con el benchmark multi-seed (mismo seed set)
  sobre GOAL (heurística, no requiere reentrenar) y ver si el win-rate sube.

USO:
  python3 train/sweep_king.py --policy GOAL --seeds 100 --workers 8 \
      --configs-tag baseline,king6,keys7,rounds90,comb1,comb2
  Cada config en el tag list se evalua como un benchmark separado de --seeds.

  Configs fijas internamente (dict de override sobre Config defaults):
    baseline: {} (sin cambios)
    king6:    {"KING_PRESENCE_START_ROUND": 6}
    king8:    {"KING_PRESENCE_START_ROUND": 8}
    keys7:    {"KEYS_TOTAL": 7}
    rounds90: {"MAX_ROUNDS": 90}
    comb1:    {"KING_PRESENCE_START_ROUND": 6, "KEYS_TOTAL": 7}
    comb2:    {"KING_PRESENCE_START_ROUND": 6, "KEYS_TOTAL": 7, "MAX_ROUNDS": 90}
"""

import sys
import json
import time
import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CONFIGS = {
    "baseline": {},
    "king6": {"KING_PRESENCE_START_ROUND": 6},
    "king8": {"KING_PRESENCE_START_ROUND": 8},
    "keys7": {"KEYS_TOTAL": 7},
    "rounds90": {"MAX_ROUNDS": 90},
    "comb1": {"KING_PRESENCE_START_ROUND": 6, "KEYS_TOTAL": 7},
    "comb2": {"KING_PRESENCE_START_ROUND": 6, "KEYS_TOTAL": 7, "MAX_ROUNDS": 90},
}


def _eval_seed_goal_cfg(seed, cfg_overrides):
    from engine.config import Config
    from sim.runner import run_episode

    cfg = Config(**cfg_overrides)
    st = run_episode(max_steps=2000, seed=seed, policy_name="GOAL", cfg=cfg)
    return {"win": st.outcome == "WIN", "round": st.round, "outcome": st.outcome}


def _eval_seed_class_cfg(policy, model_path, seed, cfg_overrides):
    from engine.config import Config
    from sim.runner import run_episode

    cfg = Config(**cfg_overrides)
    st = run_episode(
        max_steps=2000, seed=seed, policy_name=policy, cfg=cfg, model_path=model_path
    )
    return {"win": st.outcome == "WIN", "round": st.round, "outcome": st.outcome}


def sweep(policy, model_path, seeds, workers, configs, tag_prefix):
    import multiprocessing as mp
    from functools import partial

    ctx = mp.get_context("spawn")
    print(
        f"\n=== SWEEP {policy} | {len(seeds)} seeds | {workers} workers ===", flush=True
    )
    results = {}
    for cname, overrides in configs:
        t0 = time.time()
        if policy == "GOAL":
            fn = partial(_eval_seed_goal_cfg, cfg_overrides=overrides)
        else:
            fn = partial(
                _eval_seed_class_cfg, policy, model_path, cfg_overrides=overrides
            )
        with ctx.Pool(workers) as pool:
            outs = pool.map(fn, seeds)
        wins = sum(1 for r in outs if r["win"])
        wr = wins / len(seeds)
        avg_round = sum(r["round"] for r in outs) / len(seeds)
        print(
            f"  [{cname}] win-rate {wr * 100:5.1f}%  ({wins}/{len(seeds)})  "
            f"avg_round {avg_round:.0f}  overrides={overrides or '{}'}  [{time.time() - t0:.0f}s]",
            flush=True,
        )
        results[cname] = {
            "win_rate": wr,
            "n_wins": wins,
            "n_seeds": len(seeds),
            "avg_round": avg_round,
            "overrides": overrides,
        }

    out = REPO / "reports" / f"sweep_{tag_prefix}_{policy}.json"
    json.dump(
        {"policy": policy, "seeds": seeds, "configs": CONFIGS, "results": results},
        open(out, "w"),
        indent=2,
    )
    print(f"Sweep -> {out}", flush=True)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--policy", default="GOAL", help="GOAL, o COMMITTEE (requiere --model)"
    )
    ap.add_argument("--model", default=None, help="ruta .zip para COMMITTEE/ENSEMBLE")
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument(
        "--configs-tag", default="baseline,king6,keys7,rounds90,comb1,comb2"
    )
    args = ap.parse_args()

    seeds = list(range(args.seeds))
    chosen = [c.strip() for c in args.configs_tag.split(",") if c.strip()]
    configs = [(c, CONFIGS.get(c, {})) for c in chosen]
    if any(c[1] is None for c in configs):
        bad = [c[0] for c in configs if c[1] is None]
        raise SystemExit(f"Configs no definidas: {bad}. Opciones: {list(CONFIGS)}")

    sweep(
        args.policy,
        args.model,
        seeds,
        args.workers,
        configs,
        args.configs_tag.replace(",", "_"),
    )


if __name__ == "__main__":
    main()

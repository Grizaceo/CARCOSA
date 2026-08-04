"""
Benchmark multi-seed reproducible para CARCOSA (línea [092]).

POR QUÉ EXISTE (hallazgo 2026-08-04, 194 summaries):
  - El win-rate GOAL es EXTREMADAMENTE sensible a la seed: 10.1% global (19/188)
    pero las victorias se concentran en "lucky seeds" (4,15,22,28 = 3/3 cada una).
  - 30 seeds dan 0-13% según cuáles elijas. Un win-rate de ~30 runs es ruleta.
  - Cualquier afirmación "modelo X supera a GOAL" sin varianza + análisis de seeds
    es espuria: 4 lucky seeds mueven la métrica ±10pp.

QUÉ HACE:
  1. Evalúa TODOS los modelos sobre las MISMAS seeds (0..N-1), determinista.
  2. Por modelo reporta: win-rate + IC95 (bootstrap percentil) + media/mediana
     rounds y steps de las victorias.
  3. KEY: análisis de coincidencia de seeds — ¿las wins del modelo ocurren en
     seeds donde GOAL TAMBIÉN gana (replica lucky seeds = ruido) o en seeds donde
     GOAL PIERDE (mejora real)? Esa es la métrica que decide.
  4. Matriz seed x modelo + resumen JSON reproducible en reports/.

USO:
  python3 train/bench_multi_seed.py --seeds 100 --workers 8 --models GOAL \
      --model models/ppo_carcosa_final_20260803_224539.zip \
      --model models/best_evolved.zip
  (--models GOAL siempre es el baseline; después añade --model para cada .zip)
"""
import sys, os, json, time, argparse, random
from pathlib import Path
from datetime import datetime
from collections import defaultdict

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

REPORT_DIR = REPO / "reports"
EXPORTABLE_KEYS = ["policy","seed","steps","round","game_over","outcome",
                   "keys_in_hand","keys_destroyed_total"]


def _eval_seed_goal(seed):
    from sim.runner import run_episode
    st = run_episode(max_steps=2000, seed=seed, policy_name="GOAL")
    return {"win": st.outcome == "WIN", "round": st.round,
            "steps": None, "outcome": st.outcome}


def _eval_seed_ppo(zip_path, seed, device="cpu"):
    import torch
    from stable_baselines3 import PPO
    from train.carcosa_env import CarcosaEnv

    torch.set_num_threads(1)
    env = CarcosaEnv()
    model = PPO.load(str(zip_path), env=env, device=device)
    obs, info = env.reset(seed=seed)
    done = False
    steps = 0
    while not done and steps < 2000:
        a, _ = model.predict(obs, deterministic=True)
        obs, r, term, trunc, info = env.step(a)
        done = term or trunc
        steps += 1
    win = "WIN" in str(info.get("outcome", ""))
    rounds = int(info.get("round", -1)) if "round" in info else None
    env.close()
    return {"win": win, "round": rounds, "steps": steps,
            "outcome": info.get("outcome")}


def _model_eval(model_key, zip_path, seeds, workers, device):
    """Evalúa UN modelo sobre todas las seeds, en paralelo."""
    import multiprocessing as mp
    from functools import partial

    ctx = mp.get_context("spawn")
    if zip_path is None:  # GOAL
        fn = partial(_eval_seed_goal)
    else:
        fn = partial(_eval_seed_ppo, zip_path, device=device)

    results = {}
    with ctx.Pool(workers) as pool:
        outs = pool.map(fn, seeds)
        for seed, r in zip(seeds, outs):
            r["seed"] = seed
            r["model"] = model_key
            results[seed] = r
    return results


def _bootstrap_ci(wins, n_iter=2000, seed=42):
    """IC95 percentil bootstrap de la proporcion de wins."""
    rng = random.Random(seed)
    n = len(wins)
    samples = []
    for _ in range(n_iter):
        k = sum(rng.choice(wins) for _ in range(n))
        samples.append(k / n)
    samples.sort()
    lo, hi = samples[int(0.025*n_iter)], samples[int(0.975*n_iter)]
    return lo, hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--device", default="cpu",
                    help="cpu (recommended: cuda es mas lento para este env)")
    ap.add_argument("--tag", default="")
    ap.add_argument("--model", dest="models", action="append",
                    help="ruta a un .zip PPO a evaluar (repetible). GOAL siempre incluido.")
    args = ap.parse_args()

    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    # GOAL siempre presente como baseline; luego los .zip
    entries = [("GOAL", None)] + [(f"PPO:{Path(m).stem[:28]}", m) for m in (args.models or [])]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = args.tag or "bench"
    out_dir = REPORT_DIR / f"{ts}_{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Benchmark: {len(seeds)} seeds (0..{seeds[-1]}), {len(entries)} modelos, "
          f"{args.workers} workers", flush=True)

    all_results = {}   # model_key -> {seed: result}
    t0 = time.time()
    for key, zpath in entries:
        t_m = time.time()
        r = _model_eval(key, zpath, seeds, args.workers, args.device)
        all_results[key] = r
        nwin = sum(1 for x in r.values() if x["win"])
        print(f"  [{key}] {nwin}/{len(seeds)} = {nwin/len(seeds)*100:.1f}% "
              f"({time.time()-t_m:.0f}s)", flush=True)

    # ===== ANÁLISIS =====
    print("\n=== RESULTADOS ===", flush=True)
    goal_wins = set(s for s,r in all_results.get("GOAL", {}).items() if r["win"])
    summary = {}

    for key in all_results:
        wins_seeds = set(s for s,r in all_results[key].items() if r["win"])
        win_flags = [1 if s in wins_seeds else 0 for s in seeds]
        lo, hi = _bootstrap_ci(win_flags)
        wins = sorted(wins_seeds)
        # Analisis de coincidencia vs GOAL
        if key == "GOAL":
            novel = new_only = "—"
            overlap_txt = f"seeds_criticas={sorted(goal_wins)}"
        else:
            overlap = wins_seeds & goal_wins
            novel = wins_seeds - goal_wins  # seeds donde el modelo gana y GOAL pierde
            overlap_txt = f"overlap_GOAL={len(overlap)} (replica lucky={len(overlap)}), " \
                          f"novelas_sobre_GOAL={len(novel)}: {sorted(novel)[:10]}"
        avg_round_win = [all_results[key][s]["round"] for s in wins
                         if all_results[key][s].get("round")]
        med_round = sorted(avg_round_win)[len(avg_round_win)//2] if avg_round_win else None

        summary[key] = {
            "win_rate": len(wins_seeds)/len(seeds),
            "ci95_low": lo, "ci95_high": hi,
            "n_wins": len(wins_seeds), "n_seeds": len(seeds),
            "win_seeds": list(wins_seeds),
            "goal_wins": sorted(goal_wins),
            "novel_wins_over_GOAL": sorted(novel) if isinstance(novel, set) else [],
            "overlap_with_GOAL": len(overlap) if key!="GOAL" else None,
            "median_round_of_wins": med_round,
        }
        print(f"\n[{key}]", flush=True)
        print(f"  win-rate = {len(wins_seeds)}/{len(seeds)} = {len(wins_seeds)/len(seeds)*100:.1f}%  "
              f"(IC95: {lo*100:.1f}%–{hi*100:.1f}%)", flush=True)
        print(f"  {overlap_txt}", flush=True)
        print(f"  seeds con win: {wins}", flush=True)

    with open(out_dir / "benchmark_summary.json", "w") as f:
        json.dump({"meta": {"seeds": seeds, "models": [k for k in all_results],
                            "created": datetime.now().isoformat(), "device": args.device},
                   "summary": summary,
                   "detail": all_results}, f, indent=2, default=str)
    print(f"\nResultado completo -> {out_dir}/benchmark_summary.json", flush=True)
    print(f"Tiempo total: {(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
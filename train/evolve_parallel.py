"""
Evolución PBT paralela CARCOSA (línea [092]) — versión multiprocessing.

MIDE ANTES DE SUPONER (benchmark 2026-08-04, RTX 4060 8GB + 12 cores):
  - device=cpu 1 env:  ~299 steps/s
  - device=cuda 1 env: ~126 steps/s  (¡CUDA es MÁS LENTO! el cuello es el step
    del env, Python puro; la red es diminuta. NO usar cuda para entrenar.)
  - workers en paralelo (cpu): 1→142, 2→262, 4→516, 6→559 steps/s combinados
    (speedup ~3.8x con 6 workers; no lineal por contienda de CPU/mem del sistema)

Diseño:
  - multiprocessing Pool(W): cada worker muta + entrena + evalúa UN mutante.
  - La madre ancla se re-evalúa en paralelo (mismo pool, tarea extra).
  - Regla de negocio (Cristóbal, 2026-08-04): un mutante sólo se promueve si
    SUPERA el win-rate de la madre; si no, la madre se conserva (elitismo ancla).
  - FALLBACK: si tras --fallback-gen no hay NINGUNA victoria en la historia,
    volver a --original-base (la red que al menos ganó 1/30).
  - Log persistente a train/logs/ (NO /tmp — se limpia; el log de la corrida
    anterior se perdió por eso).

Uso:
  python3 train/evolve_parallel.py \
      --base-model models/ppo_carcosa_final_20260803_224539.zip \
      --original-base models/ppo_carcosa_final_20260803_224539.zip \
      --generations 4 --mutants 6 --workers 6 \
      --mutate-steps 100000 --sigma 0.02 --eval-episodes 30 --fallback-gen 2
"""
import sys
import os
import time
import json
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

LOG_DIR = REPO / "train" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

EVAL_SEEDS = list(range(30))  # fijas, comparación justa entre generaciones


def _setup_logging(tag: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = str(LOG_DIR / f"evolve_parallel_{ts}_{tag}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stdout)],
    )
    return log_path


def _evaluate(model, episodes=30, seeds=None):
    """Win-rate determinista sobre seeds fijas. Recibe modelo ya cargado."""
    from train.carcosa_env import CarcosaEnv

    env = CarcosaEnv()
    wins = 0
    for ep in (seeds or EVAL_SEEDS)[:episodes]:
        obs, info = env.reset(seed=ep)
        done = False
        while not done:
            a, _ = model.predict(obs, deterministic=True)
            obs, r, term, trunc, info = env.step(a)
            done = term or trunc
        if "WIN" in str(info.get("outcome", "")):
            wins += 1
    env.close()
    return wins / episodes


def _eval_path(zip_path, episodes=30, seeds=None):
    """Carga un .zip y lo evalúa (para el worker de la madre ancla)."""
    import torch
    from stable_baselines3 import PPO
    from train.carcosa_env import CarcosaEnv

    torch.set_num_threads(2)
    env = CarcosaEnv()
    model = PPO.load(str(zip_path), env=env, device="cpu")
    wr = _evaluate(model, episodes, seeds)
    env.close()
    return wr


def worker_mutate_train_eval(args):
    """Top-level (pickleable). Muta madre -> entrena -> evalúa. Devuelve dict."""
    mother_zip, sigma, mutate_steps, eval_episodes, device = args
    import uuid
    import torch
    from stable_baselines3 import PPO
    from train.carcosa_env import CarcosaEnv

    torch.set_num_threads(2)

    # 1) mutar
    tmp_env = CarcosaEnv()
    model = PPO.load(str(mother_zip), env=tmp_env, device=device)
    with torch.no_grad():
        for p in model.policy.parameters():
            if p.requires_grad:
                p.add_(torch.randn_like(p) * sigma)
    stem = Path(mother_zip).stem
    uid = uuid.uuid4().hex[:8]
    mpath = str(Path(mother_zip).parent / f"{stem}_mut_{uid}.zip")
    model.save(mpath)
    tmp_env.close()

    # 2) entrenar continuando
    tmp_env2 = CarcosaEnv()
    model2 = PPO.load(mpath, env=tmp_env2, device=device, learning_rate=1e-4)
    model2.learn(total_timesteps=mutate_steps, progress_bar=False)
    tpath = str(Path(mpath).parent / f"{Path(mpath).stem}_trained.zip")
    model2.save(tpath)
    tmp_env2.close()
    try:
        os.remove(mpath)
    except OSError:
        pass

    # 3) evaluar
    wr = _eval_path(tpath, eval_episodes)
    return {"wr": wr, "path": tpath, "kind": "MUTANTE"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-model", required=True)
    ap.add_argument("--original-base", required=True)
    ap.add_argument("--generations", type=int, default=4)
    ap.add_argument("--mutants", type=int, default=6)
    ap.add_argument("--workers", type=int, default=6, help="procesos en paralelo")
    ap.add_argument("--mutate-steps", type=int, default=100000)
    ap.add_argument("--sigma", type=float, default=0.02)
    ap.add_argument("--eval-episodes", type=int, default=30)
    ap.add_argument("--objective-wr", type=float, default=0.10)
    ap.add_argument("--fallback-gen", type=int, default=2)
    ap.add_argument("--device", default="cpu",
                    help="cpu (recomendado, ~2.4x más rápido que cuda para este env)")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    log_path = _setup_logging(args.tag or Path(args.base_model).stem[:24])
    logging.info(f"LOG -> {log_path}")
    logging.info(f"cfg: gens={args.generations} mutants={args.mutants} "
                 f"workers={args.workers} steps={args.mutate_steps} "
                 f"sigma={args.sigma} episodes={args.eval_episodes} device={args.device}")

    import multiprocessing as mp
    ctx = mp.get_context("spawn")

    mother = args.base_model
    original_base = args.original_base
    history = []
    best_overall_wr = 0.0
    best_overall_path = mother
    t_run = time.time()

    for gen in range(1, args.generations + 1):
        t_gen = time.time()
        logging.info(f"===== GENERACIÓN {gen} (madre: {Path(mother).name}) =====")

        # Tareas del pool: 1) re-evaluar madre ancla, 2) M mutantes
        tasks = [("mother", mother, args.eval_episodes)]
        tasks += [("mut", (mother, args.sigma, args.mutate_steps,
                           args.eval_episodes, args.device)) for _ in range(args.mutants)]

        results = {}
        with ctx.Pool(args.workers) as pool:
            # madre ancla primero (rápida), mutantes después
            f_mother = pool.apply_async(_eval_path, (mother, args.eval_episodes))
            f_muts = [pool.apply_async(worker_mutate_train_eval, (t[1],))
                      for t in tasks if t[0] == "mut"]

            mother_wr = f_mother.get()
            logging.info(f"  [ANCLA] madre: {Path(mother).name} -> {mother_wr*100:.1f}%")

            for i, f in enumerate(f_muts, 1):
                res = f.get()
                results[res["path"]] = res
                logging.info(f"  mutante {i}/{len(f_muts)} -> {res['wr']*100:.1f}% "
                             f"({Path(res['path']).name})")

        pool_entries = [(mother_wr, mother, "MADRE")]
        pool_entries += [(r["wr"], r["path"], r["kind"]) for r in results.values()]

        # Selección con ancla: sólo se promueve quien SUPERA a la madre
        pool_entries.sort(key=lambda x: -x[0])
        best_wr, best_path, best_kind = pool_entries[0]
        history.append({
            "gen": gen,
            "best_win_rate": best_wr,
            "best_model": best_path,
            "best_kind": best_kind,
            "mother_win_rate": mother_wr,
            "surpassed_mother": best_wr > mother_wr,
        })
        logging.info(f"  >> MEJOR GEN {gen}: {best_wr*100:.1f}% ({best_kind})")
        logging.info(f"  >> madre ancla: {mother_wr*100:.1f}% -> "
                     f"{'SUPERADA' if best_wr > mother_wr else 'CONSERVADA (elitismo)'}")

        if best_wr > best_overall_wr:
            best_overall_wr = best_wr
            best_overall_path = best_path

        if best_wr >= args.objective_wr:
            logging.info(f"  >> OBJETIVO {args.objective_wr*100:.0f}% ALCANZADO en gen {gen}")
            break

        if gen >= args.fallback_gen:
            any_win = any(h["best_win_rate"] > 0.0 for h in history)
            if not any_win:
                logging.info(f"  >> FALLBACK: tras gen {gen} sigue 0% victorias. "
                             f"Volviendo a red base original: {Path(original_base).name}")
                mother = original_base
                continue

        mother = best_path
        logging.info(f"  gen {gen} en {time.time()-t_gen:.0f}s")

    logging.info("\n=== HISTORIAL DE EVOLUCIÓN (madre ancla, paralela) ===")
    for h in history:
        logging.info(f"  Gen {h['gen']}: mejor {h['best_win_rate']*100:.1f}% "
                     f"({h['best_kind']}) | madre {h['mother_win_rate']*100:.1f}% | "
                     f"{'superó' if h['surpassed_mother'] else 'no superó'}")

    final = str(REPO / "models" / "best_evolved_parallel.zip")
    shutil.copy(best_overall_path, final)
    logging.info(f"Mejor modelo -> {final}")
    logging.info(f"Tiempo total: {(time.time()-t_run)/60:.1f} min")
    logging.info(f"Resultado JSON: {json.dumps(history)}")


if __name__ == "__main__":
    main()

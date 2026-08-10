"""
Evolución de la red CARCOSA (línea [092]) — PBT manual local en la 4060.

Cada generación:
  1. base = mejor modelo de la gen anterior (arranca en --base-model)
  2. clonar base -> M mutantes (perturbación gaussiana de pesos, sigma)
  3. entrenar cada mutante --mutate-steps ts continuando desde sus pesos
  4. evaluar win-rate en 30 partidas fijas (seeds 0..29)
  5. el mutante con mayor win-rate es la base de la siguiente generación

Uso:
  python train/evolve.py --base-model models/ppo_carcosa_final_20260803_224539.zip \
      --generations 4 --mutants 4 --mutate-steps 100000 --sigma 0.02
"""

import sys
import os
import argparse
from pathlib import Path
import torch
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent))
from train.carcosa_env import CarcosaEnv
from stable_baselines3 import PPO

EVAL_SEEDS = list(range(30))  # fijo para comparación justa entre generaciones


def evaluate(model, episodes=30):
    env = CarcosaEnv()
    wins = 0
    for ep in EVAL_SEEDS[:episodes]:
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


def mutate_model(src_zip, sigma):
    """Carga pesos de un modelo SB3, perturba, devuelve ruta a un .zip mutado."""
    tmp_env = CarcosaEnv()
    model = PPO.load(src_zip, env=tmp_env)
    # perturbar pesos de la policy net
    with torch.no_grad():
        for p in model.policy.parameters():
            if p.requires_grad:
                noise = torch.randn_like(p) * sigma
                p.add_(noise)
    stem = Path(
        src_zip
    ).stem  # sin .zip (defensa: evita doble .zip en generaciones recursivas)
    uid = uuid.uuid4().hex[:8]
    out = str(Path(src_zip).parent / f"{stem}_mut_{uid}.zip")
    model.save(out)
    tmp_env.close()
    return out


def train_continue(model_zip, steps, lr=1e-4):
    tmp_env = CarcosaEnv()
    model = PPO.load(model_zip, env=tmp_env, learning_rate=lr)
    model.learn(total_timesteps=steps, progress_bar=False)
    stem = Path(model_zip).stem  # sin .zip
    out = str(Path(model_zip).parent / f"{stem}_trained.zip")
    model.save(out)
    tmp_env.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-model", required=True)
    ap.add_argument("--generations", type=int, default=4)
    ap.add_argument("--mutants", type=int, default=4)
    ap.add_argument("--mutate-steps", type=int, default=100000)
    ap.add_argument("--sigma", type=float, default=0.02)
    ap.add_argument("--eval-episodes", type=int, default=30)
    args = ap.parse_args()

    base = args.base_model
    history = []
    for gen in range(1, args.generations + 1):
        print(f"\n===== GENERACIÓN {gen} (base: {Path(base).name}) =====")
        mutants = []
        for m in range(args.mutants):
            mpath = mutate_model(base, args.sigma)
            print(f"  mutante {m + 1}/{args.mutants}: {Path(mpath).name}")
            mutants.append(mpath)
        results = []
        for mpath in mutants:
            tpath = train_continue(mpath, args.mutate_steps)
            model = PPO.load(tpath, env=CarcosaEnv())
            wr = evaluate(model, args.eval_episodes)
            results.append((wr, tpath))
            print(f"    mutante {Path(mpath).name} -> win-rate {wr * 100:.1f}%")
            try:
                os.remove(mpath)
            except OSError:
                pass
        results.sort(key=lambda x: -x[0])
        best_wr, best_path = results[0]
        history.append({"gen": gen, "best_win_rate": best_wr, "best_model": best_path})
        print(
            f"  >> MEJOR GEN {gen}: win-rate {best_wr * 100:.1f}%  ({Path(best_path).name})"
        )
        if best_wr >= 0.10:
            print(f"  >> OBJETIVO 10% ALCANZADO en gen {gen}")
            break
        base = best_path  # la mejor mutante es la nueva base

    print("\n=== HISTORIAL DE EVOLUCIÓN ===")
    for h in history:
        print(
            f"  Gen {h['gen']}: {h['best_win_rate'] * 100:.1f}%  ({Path(h['best_model']).name})"
        )
    # guardar mejor modelo como 'best_evolved'
    best = max(history, key=lambda h: h["best_win_rate"])
    import shutil

    final = "models/best_evolved.zip"
    shutil.copy(best["best_model"], final)
    print(f"\nMejor modelo evolucionado guardado en: {final}")


if __name__ == "__main__":
    main()

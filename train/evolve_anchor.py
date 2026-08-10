"""
Evolución de la red CARCOSA (línea [092]) — PBT manual local en la 4060.

VERSIÓN CON MADRE ANCLA (corrige regresión de evolve.py original).

Regla de negocio (Cristóbal, 2026-08-04):
  - La red "madre" de cada generación SIEMPRE compite contra sus mutantes.
  - Un mutante sólo se vuelve la nueva madre si SUPERA el win-rate de la madre
    previa. Si ningún mutante la supera, la madre se conserva (elitismo ancla).
  - Esto evita el bug original: promover una mutante de 0% sobre una madre
    que ganaba 1/30.
  - FALLBACK: si al terminar la GENERACIÓN 2 (o cualquiera configurada vía
    --fallback-gen) no hay NINGUNA victoria en toda la historia, se vuelve a la
    red base original que al menos ganó 1/30 (--original-base).

Cada generación:
  1. mother = mejor modelo de la gen anterior (arranca en --base-model)
  2. clonar mother -> M mutantes (perturbación gaussiana de pesos, sigma)
  3. entrenar cada mutante --mutate-steps ts continuando desde sus pesos
  4. evaluar win-rate en --eval-episodes partidas fijas (seeds 0..N-1)
  5. la madre original también se re-evalúa (ancla) y compite en el mismo pool
  6. el modelo con mayor win-rate es la madre de la siguiente generación

Uso:
  python train/evolve_anchor.py --base-model models/ppo_carcosa_final_20260803_224539.zip \
      --original-base models/ppo_carcosa_final_20260803_224539.zip \
      --generations 4 --mutants 4 --mutate-steps 100000 --sigma 0.02 \
      --eval-episodes 30 --fallback-gen 2
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
    with torch.no_grad():
        for p in model.policy.parameters():
            if p.requires_grad:
                noise = torch.randn_like(p) * sigma
                p.add_(noise)
    stem = Path(src_zip).stem  # sin .zip (defensa: evita doble .zip en generaciones recursivas)
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


def eval_model_path(path, episodes):
    """Carga y evalúa un .zip ya entrenado sin re-entrenar."""
    env = CarcosaEnv()
    model = PPO.load(path, env=env)
    wr = evaluate(model, episodes)
    env.close()
    return wr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-model", required=True,
                    help="Modelo madre inicial (mejor de la gen anterior o red base).")
    ap.add_argument("--original-base", required=True,
                    help="Red base ORIGINAL que ganó >=1/30. Usada por el fallback.")
    ap.add_argument("--generations", type=int, default=4)
    ap.add_argument("--mutants", type=int, default=4)
    ap.add_argument("--mutate-steps", type=int, default=100000)
    ap.add_argument("--sigma", type=float, default=0.02)
    ap.add_argument("--eval-episodes", type=int, default=30)
    ap.add_argument("--objective-wr", type=float, default=0.10,
                    help="Win-rate para considerar objetivo alcanzado y detenerse.")
    ap.add_argument("--fallback-gen", type=int, default=2,
                    help="Si tras esta generación no hay victorias en toda la historia, "
                         "volver a --original-base.")
    args = ap.parse_args()

    mother = args.base_model
    original_base = args.original_base
    history = []
    best_overall_wr = 0.0
    best_overall_path = mother

    for gen in range(1, args.generations + 1):
        print(f"\n===== GENERACIÓN {gen} (madre: {Path(mother).name}) =====")

        # 1) La madre ancla compite en el mismo pool (re-evaluada para justeza)
        print(f"  [ANCLA] madre actual: {Path(mother).name}")
        # Si la madre ya es un _trained, la reusamos; si no, la evaluamos directo.
        mother_wr = eval_model_path(mother, args.eval_episodes)
        pool = [(mother_wr, mother, "MADRE")]
        print(f"    madre -> win-rate {mother_wr*100:.1f}%")

        # 2) Mutantes
        mutants = []
        for m in range(args.mutants):
            mpath = mutate_model(mother, args.sigma)
            print(f"  mutante {m+1}/{args.mutants}: {Path(mpath).name}")
            mutants.append(mpath)

        for mpath in mutants:
            tpath = train_continue(mpath, args.mutate_steps)
            model = PPO.load(tpath, env=CarcosaEnv())
            wr = evaluate(model, args.eval_episodes)
            pool.append((wr, tpath, "MUTANTE"))
            print(f"    mutante {Path(mpath).name} -> win-rate {wr*100:.1f}%")
            try:
                os.remove(mpath)
            except OSError:
                pass

        # 3) Selección con madre ancla: sólo se promueve quien SUPERA a la madre
        pool.sort(key=lambda x: -x[0])
        best_wr, best_path, best_kind = pool[0]
        mother_wr_actual = pool[0][0] if pool[0][2] == "MADRE" else mother_wr

        history.append({
            "gen": gen,
            "best_win_rate": best_wr,
            "best_model": best_path,
            "best_kind": best_kind,
            "mother_win_rate": mother_wr,
            "surpassed_mother": best_wr > mother_wr,
        })
        print(f"  >> MEJOR GEN {gen}: win-rate {best_wr*100:.1f}%  "
              f"({best_kind}: {Path(best_path).name})")
        print(f"  >> madre ancla: {mother_wr*100:.1f}%  "
              f"-> {'SUPERADA' if best_wr > mother_wr else 'CONSERVADA (elitismo)'}")

        # 4) Actualizar melhor global
        if best_wr > best_overall_wr:
            best_overall_wr = best_wr
            best_overall_path = best_path

        # 5) Objetivo alcanzado -> detener
        if best_wr >= args.objective_wr:
            print(f"  >> OBJETIVO {args.objective_wr*100:.0f}% ALCANZADO en gen {gen}")
            break

        # 6) FALLBACK: si tras --fallback-gen no hay ninguna victoria en toda la
        #    historia, volver a la red base original (la que ganó 1/30).
        if gen >= args.fallback_gen:
            any_win = any(h["best_win_rate"] > 0.0 for h in history)
            if not any_win:
                print(f"\n  >> FALLBACK: tras gen {gen} sigue 0% victorias en toda la "
                      f"historia. Volviendo a red base original: {Path(original_base).name}")
                mother = original_base
                # no break: dejamos correr las generaciones restantes desde la base original
                continue

        # 7) Madre de la siguiente gen = la que ganó el pool (respetando ancla)
        mother = best_path

    # Historial
    print("\n=== HISTORIAL DE EVOLUCIÓN (madre ancla) ===")
    for h in history:
        print(f"  Gen {h['gen']}: mejor {h['best_win_rate']*100:.1f}% "
              f"({h['best_kind']}) | madre {h['mother_win_rate']*100:.1f}% "
              f"| {'superó' if h['surpassed_mother'] else 'no superó'}")

    # Guardar mejor modelo como 'best_evolved_anchor'
    import shutil
    final = "models/best_evolved_anchor.zip"
    shutil.copy(best_overall_path, final)
    print(f"\nMejor modelo evolucionado (ancla) guardado en: {final}")
    print(f"  win-rate global: {best_overall_wr*100:.1f}%  ({Path(best_overall_path).name})")


if __name__ == "__main__":
    main()

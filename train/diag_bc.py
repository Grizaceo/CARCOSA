"""Diagnóstico de progreso del agente RL PPO (línea [092]).
Carga modelo SB3 (.zip) y mide llaves promedio, % toca Umbral, ronda de muerte, outcomes.
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from train.carcosa_env import CarcosaEnv
from stable_baselines3 import PPO


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--episodes", type=int, default=30)
    args = ap.parse_args()

    model = PPO.load(args.model)
    env = CarcosaEnv()
    keys_at_end, touch_umbral, rounds_death, outcomes = [], [], [], {}
    for ep in range(args.episodes):
        obs, info = env.reset(seed=ep * 313)
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, r, term, trunc, info = env.step(action)
            done = term or trunc
        st = env.state
        tot_keys = sum(p.keys for p in st.players.values())
        keys_at_end.append(tot_keys)
        touch_umbral.append(
            any(str(p.room) == str(env.cfg.UMBRAL_NODE) for p in st.players.values())
        )
        rounds_death.append(st.round)
        oc = info.get("outcome", "TIMEOUT")
        outcomes[oc] = outcomes.get(oc, 0) + 1

    print(f"Episodios: {args.episodes}")
    print(
        f"Llaves promedio al final: {np.mean(keys_at_end):.2f}  (max visto: {max(keys_at_end)})"
    )
    print(f"% que tocó el Umbral: {100 * np.mean(touch_umbral):.0f}%")
    print(f"Ronda promedio de muerte: {np.mean(rounds_death):.1f}")
    print(f"Outcomes: {outcomes}")


if __name__ == "__main__":
    main()

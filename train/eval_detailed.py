import sys
from pathlib import Path
import numpy as np

from sb3_contrib import MaskablePPO

sys.path.insert(0, str(Path(__file__).parent.parent))
from train.carcosa_env import CarcosaEnv


def evaluate_detailed(model_path, episodes=50):
    print(f"Cargando modelo {model_path}...")
    model = MaskablePPO.load(model_path)
    env = CarcosaEnv()

    outcomes = {"WIN": 0, "LOSE": 0, "TIMEOUT": 0}
    reasons = []
    keys_collected = []
    steps_survived = []

    for ep in range(episodes):
        obs, info = env.reset(seed=ep * 777)
        done = False
        steps = 0

        while not done:
            action_masks = env.action_masks()
            action, _ = model.predict(
                obs, action_masks=action_masks, deterministic=True
            )
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            steps += 1

        outcome_raw = info.get("outcome")
        if outcome_raw is None:
            outcome_raw = "TIMEOUT"

        if outcome_raw == "WIN":
            outcomes["WIN"] += 1
        elif "LOSE" in outcome_raw:
            outcomes["LOSE"] += 1
        else:
            outcomes["TIMEOUT"] += 1

        state = env.state
        total_keys = sum(p.keys for p in state.players.values())
        keys_collected.append(total_keys)
        steps_survived.append(steps)
        reasons.append(outcome_raw)

    print("\n=== RESULTADOS DETALLADOS ===")
    print(f"Episodios evaluados: {episodes}")
    print(
        f"Wins: {outcomes['WIN']} | Losses: {outcomes['LOSE']} | Timeouts: {outcomes['TIMEOUT']}"
    )
    print(f"Promedio de llaves recolectadas: {np.mean(keys_collected):.2f}")
    print(f"Episodios con al menos 1 llave: {sum(1 for k in keys_collected if k > 0)}")
    print(f"Episodios con 4 llaves: {sum(1 for k in keys_collected if k >= 4)}")
    print(f"Pasos promedio sobrevivientes: {np.mean(steps_survived):.1f}")

    loss_reasons = {}
    for r in reasons:
        if r not in loss_reasons:
            loss_reasons[r] = 0
        loss_reasons[r] += 1

    print("\nRazones de finalización detalladas:")
    for r, count in loss_reasons.items():
        print(f" - {r}: {count}")


if __name__ == "__main__":
    evaluate_detailed("models/maskable_ppo_30pct_20260425_195958.zip", episodes=20)

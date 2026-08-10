import sys
from pathlib import Path
from datetime import datetime

from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv

sys.path.insert(0, str(Path(__file__).parent.parent))
from train.carcosa_env import CarcosaEnv


def evaluate_win_rate(model, episodes=30):
    env = CarcosaEnv()
    wins = 0
    for ep in range(episodes):
        obs, info = env.reset(seed=ep * 1337)
        done = False
        while not done:
            action_masks = env.action_masks()
            action, _ = model.predict(
                obs, action_masks=action_masks, deterministic=True
            )
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated

        outcome = info.get("outcome", "TIMEOUT")
        if outcome == "WIN":
            wins += 1
    env.close()
    return wins / episodes


def make_env(seed, rank):
    def _init():
        return CarcosaEnv(seed=seed + rank)

    return _init


def main():
    print(
        "Iniciando entrenamiento iterativo de MaskablePPO hasta alcanzar 30% win rate"
    )
    n_envs = 4
    env = DummyVecEnv([make_env(42, i) for i in range(n_envs)])

    model = MaskablePPO(
        "MlpPolicy",
        env,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        verbose=1,
    )

    target_win_rate = 0.30
    chunk_timesteps = 50_000

    for i in range(20):  # max 1M timesteps
        print(f"--- Entrenando chunk {i + 1} ({chunk_timesteps} timesteps) ---")
        model.learn(total_timesteps=chunk_timesteps, reset_num_timesteps=False)

        print("--- Evaluando win rate ---")
        win_rate = evaluate_win_rate(model, episodes=30)
        print(f"Win rate actual: {win_rate * 100:.1f}%")

        if win_rate >= target_win_rate:
            print("Objetivo de 30% alcanzado!")
            break

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    Path("models").mkdir(exist_ok=True)
    save_path = f"models/maskable_ppo_30pct_{timestamp}.zip"
    model.save(save_path)
    print(f"Modelo guardado en {save_path}")


if __name__ == "__main__":
    main()

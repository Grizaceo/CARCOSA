"""
Entrenamiento RL con StableBaselines3 para CARCOSA
===================================================
Entrena agentes usando PPO, A2C u otros algoritmos.

Pre-requisitos:
    pip install stable-baselines3 gymnasium

Uso:
    python train/train_rl.py --algo ppo --timesteps 500000
    python train/train_rl.py --algo a2c --timesteps 1000000 --n-envs 8
"""

import argparse
import os
from pathlib import Path
from datetime import datetime

import numpy as np

try:
    from stable_baselines3 import PPO, A2C, DQN
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.callbacks import (
        EvalCallback, 
        CheckpointCallback,
        CallbackList
    )
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
    from stable_baselines3.common.monitor import Monitor
    HAS_SB3 = True
except ImportError:
    HAS_SB3 = False
    print("WARNING: stable-baselines3 no instalado. Instalar con: pip install stable-baselines3")

# Importar entorno
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from train.carcosa_env import CarcosaEnv


def make_env(seed: int, rank: int):
    """Factory function para crear entornos."""
    def _init():
        env = CarcosaEnv(seed=seed + rank)
        return env
    return _init


def train_rl(
    algo: str = "ppo",
    total_timesteps: int = 500_000,
    n_envs: int = 4,
    seed: int = 42,
    learning_rate: float = 3e-4,
    batch_size: int = 64,
    n_steps: int = 2048,
    save_dir: str = "models",
    log_dir: str = "runs/rl_training",
    eval_freq: int = 10_000,
    use_subproc: bool = False,
):
    """
    Entrena agente RL.
    
    Args:
        algo: Algoritmo ("ppo", "a2c", "dqn")
        total_timesteps: Pasos totales de entrenamiento
        n_envs: Número de entornos paralelos
        seed: Semilla random
        learning_rate: Learning rate
        batch_size: Tamaño del batch
        n_steps: Pasos por update
        save_dir: Directorio para guardar modelos
        log_dir: Directorio para TensorBoard
        eval_freq: Frecuencia de evaluación
        use_subproc: Usar SubprocVecEnv (más rápido, puede dar problemas en Windows)
    """
    if not HAS_SB3:
        print("ERROR: stable-baselines3 no está instalado.")
        print("Instalar con: pip install stable-baselines3")
        return
    
    print(f"="*60)
    print(f"CARCOSA RL Training con {algo.upper()}")
    print(f"="*60)
    
    # Crear entornos vectorizados
    print(f"Creando {n_envs} entornos paralelos...")
    
    if use_subproc and n_envs > 1:
        env = SubprocVecEnv([make_env(seed, i) for i in range(n_envs)])
    else:
        env = DummyVecEnv([make_env(seed, i) for i in range(n_envs)])
    
    # Entorno de evaluación
    eval_env = DummyVecEnv([make_env(seed + 1000, 0)])
    
    # Configurar modelo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{algo}_{timestamp}"
    tensorboard_log = f"{log_dir}/{run_name}"
    
    print(f"Algoritmo: {algo.upper()}")
    print(f"Timesteps: {total_timesteps:,}")
    print(f"Envs paralelos: {n_envs}")
    print(f"TensorBoard: tensorboard --logdir={log_dir}")
    
    # Crear modelo según algoritmo
    common_kwargs = {
        "policy": "MlpPolicy",
        "env": env,
        "learning_rate": learning_rate,
        "verbose": 1,
        "tensorboard_log": tensorboard_log,
        "seed": seed,
    }
    
    if algo.lower() == "ppo":
        model = PPO(
            **common_kwargs,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
        )
    elif algo.lower() == "a2c":
        model = A2C(
            **common_kwargs,
            n_steps=5,
            gamma=0.99,
            gae_lambda=1.0,
            ent_coef=0.01,
        )
    elif algo.lower() == "dqn":
        # DQN no soporta vectorized envs de la misma manera
        single_env = CarcosaEnv(seed=seed)
        model = DQN(
            policy="MlpPolicy",
            env=single_env,
            learning_rate=learning_rate,
            verbose=1,
            tensorboard_log=tensorboard_log,
            seed=seed,
            buffer_size=100_000,
            learning_starts=1000,
            batch_size=batch_size,
        )
    else:
        raise ValueError(f"Algoritmo no soportado: {algo}")
    
    print(f"Modelo creado con {sum(p.numel() for p in model.policy.parameters()):,} parámetros")
    
    # Callbacks
    Path(save_dir).mkdir(exist_ok=True, parents=True)
    
    callbacks = [
        # Guardar checkpoints periódicos
        CheckpointCallback(
            save_freq=50_000 // n_envs,
            save_path=f"{save_dir}/checkpoints_{run_name}",
            name_prefix="rl_model"
        ),
        # Evaluar y guardar mejor modelo
        EvalCallback(
            eval_env,
            best_model_save_path=f"{save_dir}/best_{run_name}",
            log_path=f"{log_dir}/eval_{run_name}",
            eval_freq=eval_freq // n_envs,
            n_eval_episodes=10,
            deterministic=True,
        ),
    ]
    
    # Entrenar
    print(f"\nIniciando entrenamiento...")
    print(f"-"*60)
    
    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=CallbackList(callbacks),
            progress_bar=True,
        )
    except KeyboardInterrupt:
        print("\nEntrenamiento interrumpido por usuario")
    
    # Guardar modelo final
    final_path = f"{save_dir}/{algo}_carcosa_final_{timestamp}"
    model.save(final_path)
    print(f"\nModelo final guardado en: {final_path}.zip")
    
    # Cleanup
    env.close()
    eval_env.close()
    
    print(f"\n{'='*60}")
    print("Entrenamiento completado!")
    print(f"{'='*60}")
    
    return model


def evaluate_model(model_path: str, episodes: int = 10, render: bool = False):
    """
    Evalúa un modelo entrenado.
    
    Args:
        model_path: Ruta al modelo .zip
        episodes: Número de episodios a evaluar
        render: Mostrar render
    """
    if not HAS_SB3:
        print("ERROR: stable-baselines3 no instalado")
        return
    
    print(f"Cargando modelo: {model_path}")
    
    # Detectar algoritmo del nombre
    if "ppo" in model_path.lower():
        model = PPO.load(model_path)
    elif "a2c" in model_path.lower():
        model = A2C.load(model_path)
    elif "dqn" in model_path.lower():
        model = DQN.load(model_path)
    else:
        # Default a PPO
        model = PPO.load(model_path)
    
    env = CarcosaEnv(render_mode="human" if render else None)
    
    wins = 0
    losses = 0
    timeouts = 0
    total_rewards = []
    episode_lengths = []
    
    for ep in range(episodes):
        obs, info = env.reset(seed=ep * 100)
        done = False
        total_reward = 0
        steps = 0
        
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            total_reward += reward
            steps += 1
        
        total_rewards.append(total_reward)
        episode_lengths.append(steps)
        
        outcome = info.get("outcome", "TIMEOUT")
        if outcome == "WIN":
            wins += 1
        elif outcome == "LOSE":
            losses += 1
        else:
            timeouts += 1
        
        print(f"Episode {ep+1}: {outcome}, Reward={total_reward:.1f}, Steps={steps}")
    
    env.close()
    
    print(f"\n{'='*40}")
    print(f"Resultados ({episodes} episodios):")
    print(f"  Wins: {wins} ({100*wins/episodes:.1f}%)")
    print(f"  Losses: {losses} ({100*losses/episodes:.1f}%)")
    print(f"  Timeouts: {timeouts} ({100*timeouts/episodes:.1f}%)")
    print(f"  Avg Reward: {np.mean(total_rewards):.2f} ± {np.std(total_rewards):.2f}")
    print(f"  Avg Steps: {np.mean(episode_lengths):.1f}")
    print(f"{'='*40}")


def main():
    parser = argparse.ArgumentParser(description="Train RL agents for CARCOSA")
    
    subparsers = parser.add_subparsers(dest="command", help="Comando")
    
    # Train subcommand
    train_parser = subparsers.add_parser("train", help="Entrenar agente")
    train_parser.add_argument("--algo", type=str, default="ppo",
                              choices=["ppo", "a2c", "dqn"])
    train_parser.add_argument("--timesteps", type=int, default=500_000)
    train_parser.add_argument("--n-envs", type=int, default=4)
    train_parser.add_argument("--lr", type=float, default=3e-4)
    train_parser.add_argument("--batch-size", type=int, default=64)
    train_parser.add_argument("--seed", type=int, default=42)
    train_parser.add_argument("--save-dir", type=str, default="models")
    train_parser.add_argument("--log-dir", type=str, default="runs/rl_training")
    train_parser.add_argument("--eval-freq", type=int, default=10_000)
    train_parser.add_argument("--subproc", action="store_true",
                              help="Usar SubprocVecEnv (más rápido)")
    
    # Eval subcommand
    eval_parser = subparsers.add_parser("eval", help="Evaluar modelo")
    eval_parser.add_argument("--model", type=str, required=True,
                             help="Ruta al modelo .zip")
    eval_parser.add_argument("--episodes", type=int, default=10)
    eval_parser.add_argument("--render", action="store_true")
    
    args = parser.parse_args()
    
    if args.command == "train":
        train_rl(
            algo=args.algo,
            total_timesteps=args.timesteps,
            n_envs=args.n_envs,
            learning_rate=args.lr,
            batch_size=args.batch_size,
            seed=args.seed,
            save_dir=args.save_dir,
            log_dir=args.log_dir,
            eval_freq=args.eval_freq,
            use_subproc=args.subproc,
        )
    elif args.command == "eval":
        evaluate_model(
            model_path=args.model,
            episodes=args.episodes,
            render=args.render,
        )
    else:
        # Default: entrenar con PPO
        print("Uso: python train/train_rl.py train --algo ppo --timesteps 500000")
        print("     python train/train_rl.py eval --model models/ppo_carcosa_final.zip")


if __name__ == "__main__":
    main()

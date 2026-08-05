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

try:
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.callbacks import EvalCallback as MaskableEvalCallback
    HAS_SB3_CONTRIB = True
except ImportError:
    HAS_SB3_CONTRIB = False

# Importar entorno
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from train.carcosa_env import CarcosaEnv


def make_env(seed: int, rank: int, reward_params: dict = None,
             king_enabled: bool = True, king_presence_start_round: int = None,
             use_action_mask: bool = False):
    """Factory function para crear entornos."""
    def _init():
        kwargs = dict(reward_params or {})
        kwargs.setdefault("king_enabled", king_enabled)
        if king_presence_start_round is not None:
            kwargs["king_presence_start_round"] = king_presence_start_round
        env = CarcosaEnv(seed=seed + rank, **kwargs)
        if use_action_mask:
            # CRITICO [092]: el env implementa action_masks() pero nunca se
            # envolvía con ActionMasker => PPO normal exploraba 81% ilegales
            # (penalty -0.02 ahogaba la señal). Con máscara, 4% ilegales.
            from sb3_contrib.common.wrappers import ActionMasker
            env = ActionMasker(env, lambda e: e.action_masks())
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
    load_model: str = None,
    reward_params: dict = None,
    king_enabled: bool = True,
    king_presence_start_round: int = None,
    use_action_mask: bool = False,
):
    """
    Entrena agente RL.
    """
    if not HAS_SB3:
        print("ERROR: stable-baselines3 no está instalado.")
        return
    
    print(f"="*60)
    print(f"CARCOSA RL Training con {algo.upper()}")
    if load_model:
        print(f"Cargando modelo base: {load_model}")
    print(f"="*60)
    
    # Crear entornos vectorizados
    print(f"Creando {n_envs} entornos paralelos...")
    
    if use_subproc and n_envs > 1:
        env = SubprocVecEnv([make_env(seed, i, reward_params, king_enabled, king_presence_start_round, use_action_mask) for i in range(n_envs)])
    else:
        env = DummyVecEnv([make_env(seed, i, reward_params, king_enabled, king_presence_start_round, use_action_mask) for i in range(n_envs)])
    
    # Entorno de evaluación
    eval_env = DummyVecEnv([make_env(seed + 1000, 0, reward_params, king_enabled, king_presence_start_round, use_action_mask)])
    
    # Configurar modelo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{algo}_{timestamp}"
    tensorboard_log = f"{log_dir}/{run_name}"
    
    # Crear o cargar modelo
    if load_model:
        if algo.lower() == "maskable_ppo":
            model = MaskablePPO.load(load_model, env=env, tensorboard_log=tensorboard_log, learning_rate=learning_rate)
        else:
            model = PPO.load(load_model, env=env, tensorboard_log=tensorboard_log, learning_rate=learning_rate)
        print(f"Modelo cargado desde {load_model}")
    else:
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
                ent_coef=0.01,
            )
        elif algo.lower() == "maskable_ppo":
            model = MaskablePPO(
                **common_kwargs,
                n_steps=n_steps,
                batch_size=batch_size,
                n_epochs=10,
                gamma=0.99,
                ent_coef=0.01,
            )
        else:
            raise ValueError(f"Algoritmo no soportado para carga/entrenamiento: {algo}")
    
    # Callbacks
    Path(save_dir).mkdir(exist_ok=True, parents=True)
    
    # Para MaskablePPO usar el EvalCallback de sb3_contrib (maneja action_masks)
    EvalCls = MaskableEvalCallback if (algo.lower() == "maskable_ppo" and HAS_SB3_CONTRIB) else EvalCallback
    
    callbacks = [
        CheckpointCallback(
            save_freq=50_000 // n_envs,
            save_path=f"{save_dir}/checkpoints_{run_name}",
            name_prefix="rl_model"
        ),
        EvalCls(
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
    model.learn(
        total_timesteps=total_timesteps,
        callback=CallbackList(callbacks),
        progress_bar=True,
    )
    
    # Guardar modelo final
    final_path = f"{save_dir}/{algo}_carcosa_final_{timestamp}"
    model.save(final_path)
    print(f"\nModelo final guardado en: {final_path}.zip")
    
    env.close()
    eval_env.close()
    return model


def evaluate_model(model_path: str, episodes: int = 10, render: bool = False):
    """
    Evalúa un modelo entrenado.
    """
    print(f"Cargando modelo: {model_path}")
    
    if "maskable" in model_path.lower():
        model = MaskablePPO.load(model_path)
    else:
        model = PPO.load(model_path)
    
    env = CarcosaEnv(render_mode="human" if render else None)
    
    wins = 0
    total_rewards = []
    
    for ep in range(episodes):
        obs, info = env.reset(seed=ep * 100)
        done = False
        total_reward = 0
        steps = 0
        
        while not done:
            if "maskable" in model_path.lower():
                action_masks = env.action_masks()
                action, _ = model.predict(obs, action_masks=action_masks, deterministic=True)
            else:
                action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            total_reward += reward
            steps += 1
        
        total_rewards.append(total_reward)
        outcome = info.get("outcome", "TIMEOUT")
        if outcome == "WIN":
            wins += 1
        print(f"Episode {ep+1}: {outcome}, Reward={total_reward:.1f}, Steps={steps}")
    
    env.close()
    print(f"\nResultados: Wins: {wins}/{episodes} ({100*wins/episodes:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Train RL agents for CARCOSA")
    subparsers = parser.add_subparsers(dest="command")
    
    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("--algo", type=str, default="maskable_ppo")
    train_parser.add_argument("--timesteps", type=int, default=500_000)
    train_parser.add_argument("--n-envs", type=int, default=4)
    train_parser.add_argument("--lr", type=float, default=3e-4)
    train_parser.add_argument("--load-model", type=str, default=None)
    # Curriculum de dificultad [092]
    train_parser.add_argument("--king-enabled", type=lambda x: x.lower() in ("true","1","yes"), default=True,
                              help="King activo en el env (False = fase 1 del curriculum)")
    train_parser.add_argument("--king-presence-round", type=int, default=None,
                              help="Overrides KING_PRESENCE_START_ROUND (None = default)")
    train_parser.add_argument("--action-mask", type=lambda x: x.lower() in ("true","1","yes"), default=False,
                              help="Envolver env con ActionMasker (CRITICO: sin el, PPO explora 81% ilegales)")
    
    # Reward params
    train_parser.add_argument("--reward-win", type=float, default=100.0)
    train_parser.add_argument("--reward-lose", type=float, default=-10.0)
    train_parser.add_argument("--reward-key", type=float, default=10.0)  # Aumentado
    train_parser.add_argument("--penalty-empty-search", type=float, default=-2.0)
    train_parser.add_argument("--reward-key-hold", type=float, default=0.0,
                              help="[092] Reward por paso por MANTENER keys (posesión)")
    
    eval_parser = subparsers.add_parser("eval")
    eval_parser.add_argument("--model", type=str, required=True)
    eval_parser.add_argument("--episodes", type=int, default=20)
    
    args = parser.parse_args()
    
    if args.command == "train":
        reward_params = {
            "reward_win": args.reward_win,
            "reward_lose": args.reward_lose,
            "reward_key": args.reward_key,
            "penalty_empty_search": args.penalty_empty_search,
            "reward_key_hold_per_step": args.reward_key_hold,
        }
        train_rl(
            algo=args.algo,
            total_timesteps=args.timesteps,
            n_envs=args.n_envs,
            learning_rate=args.lr,
            load_model=args.load_model,
            reward_params=reward_params,
            king_enabled=args.king_enabled,
            king_presence_start_round=args.king_presence_round,
            use_action_mask=args.action_mask,
        )
    elif args.command == "eval":
        evaluate_model(args.model, episodes=args.episodes)


if __name__ == "__main__":
    main()

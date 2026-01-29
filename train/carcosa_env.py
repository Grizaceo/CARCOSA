"""
Entorno Gymnasium para CARCOSA
==============================
Wrapper que permite entrenar agentes RL con StableBaselines3.

Uso con StableBaselines3:
    from stable_baselines3 import PPO
    from train.carcosa_env import CarcosaEnv
    
    env = CarcosaEnv()
    model = PPO("MlpPolicy", env, verbose=1)
    model.learn(total_timesteps=100_000)
"""

from typing import Tuple, Dict, Any, Optional, List
import numpy as np

import gymnasium as gym
from gymnasium import spaces

# Imports del motor CARCOSA
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.config import Config
from engine.rng import RNG
from engine.transition import step
from engine.legality import get_legal_actions
from engine.actions import Action, ActionType
from engine.tension import compute_features, tension_T
from sim.runner import make_smoke_state


class CarcosaEnv(gym.Env):
    """
    Entorno Gymnasium para CARCOSA.
    
    Observation: Vector de 10 features normalizados [0, 1]
    Action: ID de acción (0 a N-1), mapeado a acciones legales
    Reward: +100 WIN, -10 LOSE, rewards intermedios por progreso
    
    Info dict contains:
        - legal_actions: Máscara binaria de acciones legales
        - round: Número de ronda actual
        - outcome: Resultado si terminó ("WIN", "LOSE", "TIMEOUT")
    """
    
    metadata = {"render_modes": ["human", "ansi"]}
    
    # Mapeo fijo de action_id a ActionType
    ACTION_TYPES = [
        ActionType.MOVE,
        ActionType.SEARCH,
        ActionType.MEDITATE,
        ActionType.END_TURN,
        ActionType.SACRIFICE,
        ActionType.ACCEPT_SACRIFICE,
        ActionType.USE_MOTEMEY_BUY_START,
        ActionType.USE_MOTEMEY_BUY_CHOOSE,
        ActionType.USE_MOTEMEY_SELL,
        ActionType.USE_ARMORY_TAKE,
        ActionType.USE_ARMORY_DROP,
        ActionType.USE_YELLOW_DOORS,
        ActionType.USE_CAPILLA,
        ActionType.USE_BLUNT,
        ActionType.USE_PORTABLE_STAIRS,
        ActionType.USE_ATTACH_TALE,
        ActionType.USE_READ_YELLOW_SIGN,
        ActionType.USE_CAMARA_LETAL_RITUAL,
        ActionType.USE_TABERNA_ROOMS,
        ActionType.USE_SALON_BELLEZA,
    ]
    
    def __init__(
        self, 
        seed: int = None, 
        render_mode: str = None,
        max_steps: int = 500,
        reward_win: float = 100.0,
        reward_lose: float = -10.0,
        reward_key: float = 1.0,
        reward_sanity_loss: float = -0.1,
    ):
        """
        Args:
            seed: Semilla para reproducibilidad
            render_mode: "human" para imprimir estado
            max_steps: Máximo de pasos antes de truncar
            reward_*: Configuración de rewards
        """
        super().__init__()
        
        self.cfg = Config()
        self.seed_value = seed
        self.render_mode = render_mode
        self.max_steps = max_steps
        
        # Reward config
        self.reward_win = reward_win
        self.reward_lose = reward_lose
        self.reward_key = reward_key
        self.reward_sanity_loss = reward_sanity_loss
        
        # Observation space: 10 features [0, 1]
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(10,), dtype=np.float32
        )
        
        # Action space: Discrete con número fijo de acciones
        self.action_space = spaces.Discrete(len(self.ACTION_TYPES))
        
        # Estado interno
        self.state = None
        self.rng = None
        self.step_count = 0
        
    def _get_obs(self) -> np.ndarray:
        """Extrae observación del estado actual."""
        features = compute_features(self.state, self.cfg)
        tension = tension_T(self.state, self.cfg, features=features)
        
        obs = np.array([
            features.get("P_sanity", 0.0),
            features.get("P_keys", 0.0),
            features.get("P_mon", 0.0),
            features.get("P_umbral", 0.0),
            features.get("P_debuff", 0.0),
            features.get("P_king_risk", 0.0),
            features.get("P_crown", 0.0),
            features.get("P_round", 0.0),
            tension,
            self.state.king_floor / 3.0,
        ], dtype=np.float32)
        
        return np.clip(obs, 0.0, 1.0)
    
    def _get_legal_action_mask(self) -> np.ndarray:
        """Retorna máscara binaria de acciones legales."""
        # Determinar actor actual
        if self.state.phase == "KING":
            return np.ones(self.action_space.n, dtype=np.float32)  # King siempre puede actuar
            
        actor = str(self.state.turn_order[self.state.turn_pos])
        legal = get_legal_actions(self.state, actor)
        
        mask = np.zeros(self.action_space.n, dtype=np.float32)
        for action in legal:
            try:
                action_id = self.ACTION_TYPES.index(action.type)
                mask[action_id] = 1.0
            except ValueError:
                pass  # Acción no en nuestro mapeo
        
        # Asegurar que al menos una acción es legal
        if mask.sum() == 0:
            mask[3] = 1.0  # END_TURN siempre debería ser legal
            
        return mask
    
    def _get_info(self) -> Dict[str, Any]:
        """Construye el dict de info."""
        return {
            "legal_actions": self._get_legal_action_mask(),
            "round": self.state.round,
            "outcome": self.state.outcome,
            "step": self.step_count,
            "keys_in_hand": sum(p.keys for p in self.state.players.values()),
            "min_sanity": min(p.sanity for p in self.state.players.values()),
        }
    
    def reset(
        self, 
        seed: int = None, 
        options: Dict[str, Any] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reinicia el entorno.
        
        Returns:
            observation, info
        """
        super().reset(seed=seed)
        
        if seed is not None:
            self.seed_value = seed
        elif self.seed_value is None:
            self.seed_value = self.np_random.integers(0, 100000)
        
        self.rng = RNG(self.seed_value)
        self.state = make_smoke_state(seed=self.seed_value, cfg=self.cfg)
        self.step_count = 0
        
        return self._get_obs(), self._get_info()
    
    def step(
        self, 
        action_id: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Ejecuta una acción en el entorno.
        
        Args:
            action_id: Índice de la acción a ejecutar
            
        Returns:
            observation, reward, terminated, truncated, info
        """
        self.step_count += 1
        
        # Determinar actor
        if self.state.phase == "KING":
            # Turno del Rey - usar política simple (random d6)
            from sim.policies import RandomKingPolicy
            king_pol = RandomKingPolicy(self.cfg)
            action = king_pol.choose(self.state, self.rng)
        else:
            actor = str(self.state.turn_order[self.state.turn_pos])
            legal = get_legal_actions(self.state, actor)
            
            # Mapear action_id a Action
            target_type = self.ACTION_TYPES[action_id] if action_id < len(self.ACTION_TYPES) else None
            
            action = None
            if target_type:
                for a in legal:
                    if a.type == target_type:
                        action = a
                        break
            
            # Si la acción no es legal, elegir una random legal
            if action is None and legal:
                action = self.rng.choice(legal)
            elif action is None:
                # Forzar END_TURN
                action = Action(actor=actor, type=ActionType.END_TURN, data={})
        
        # Estado previo para calcular reward
        prev_keys = sum(p.keys for p in self.state.players.values())
        prev_sanity = sum(p.sanity for p in self.state.players.values())
        
        # Ejecutar transición
        next_state = step(self.state, action, self.rng, self.cfg)
        
        # Calcular reward
        reward = self._calculate_reward(prev_keys, prev_sanity, next_state)
        
        self.state = next_state
        
        # Terminación
        terminated = self.state.game_over
        truncated = self.step_count >= self.max_steps
        
        obs = self._get_obs()
        info = self._get_info()
        
        if self.render_mode == "human":
            self.render()
        
        return obs, reward, terminated, truncated, info
    
    def _calculate_reward(
        self, 
        prev_keys: int, 
        prev_sanity: int, 
        next_state
    ) -> float:
        """Calcula reward para RL."""
        # Terminación
        if next_state.game_over:
            if next_state.outcome == "WIN":
                return self.reward_win
            else:
                return self.reward_lose
        
        reward = 0.0
        
        # Progreso de llaves
        curr_keys = sum(p.keys for p in next_state.players.values())
        if curr_keys > prev_keys:
            reward += self.reward_key * (curr_keys - prev_keys)
        
        # Pérdida de sanity
        curr_sanity = sum(p.sanity for p in next_state.players.values())
        if curr_sanity < prev_sanity:
            reward += self.reward_sanity_loss * (prev_sanity - curr_sanity)
        
        return reward
    
    def render(self):
        """Renderiza el estado actual."""
        if self.render_mode == "human" or self.render_mode == "ansi":
            output = [
                f"\n--- Step {self.step_count} ---",
                f"Round {self.state.round}, Phase: {self.state.phase}",
                f"King Floor: {self.state.king_floor}",
            ]
            for pid, p in self.state.players.items():
                output.append(f"  {pid}: Room={p.room}, Sanity={p.sanity}, Keys={p.keys}")
            
            if self.state.game_over:
                output.append(f"GAME OVER: {self.state.outcome}")
            
            print("\n".join(output))
            
            if self.render_mode == "ansi":
                return "\n".join(output)
    
    def close(self):
        """Limpieza."""
        pass


# Registrar entorno si gymnasium está disponible
try:
    from gymnasium.envs.registration import register
    register(
        id="Carcosa-v0",
        entry_point="train.carcosa_env:CarcosaEnv",
        max_episode_steps=500,
    )
except Exception:
    pass  # Ya registrado o error de import


if __name__ == "__main__":
    # Test del entorno
    print("Testing CarcosaEnv...")
    
    env = CarcosaEnv(seed=42, render_mode="human")
    obs, info = env.reset()
    
    print(f"\nObservation shape: {obs.shape}")
    print(f"Observation: {obs}")
    print(f"Legal actions: {info['legal_actions']}")
    
    # Ejecutar algunos pasos random
    total_reward = 0
    for i in range(20):
        # Elegir acción random de las legales
        legal_mask = info["legal_actions"]
        legal_ids = np.where(legal_mask > 0)[0]
        action = np.random.choice(legal_ids)
        
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        
        if terminated or truncated:
            print(f"\nEpisode ended: {info['outcome']}, Total reward: {total_reward}")
            break
    
    env.close()
    print("\nTest completado!")

"""
Evaluación de Modelos para CARCOSA
==================================
Evalúa modelos BC y RL contra los bots heurísticos existentes.

Uso:
    python train/evaluate.py --model models/bc_mlp_GOAL_best.pt --episodes 50
    python train/evaluate.py --compare --episodes 100
"""

import argparse
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional

import torch
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.config import Config
from engine.rng import RNG
from engine.transition import step
from engine.legality import get_legal_actions
from engine.actions import Action, ActionType
from engine.tension import compute_features, tension_T
from sim.runner import make_smoke_state
from sim.policies import (
    GoalDirectedPlayerPolicy, 
    CowardPolicy, 
    BerserkerPolicy, 
    SpeedrunnerPolicy,
    RandomPolicy,
    get_king_policy,
)

from train.model import CarcosaPolicyNet, load_model


class NeuralNetworkPlayerPolicy:
    """
    Policy que usa una red neuronal entrenada para decidir acciones.
    Compatible con el sistema de simulación existente.
    """
    
    # Mapeo de action_id a ActionType
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
        model_path: str, 
        cfg: Config = None,
        device: str = "cpu",
        temperature: float = 1.0,
    ):
        """
        Args:
            model_path: Ruta al modelo .pt
            cfg: Configuración del juego
            device: "cuda" o "cpu"
            temperature: Temperatura para sampling (1.0 = greedy via argmax)
        """
        self.cfg = cfg or Config()
        self.device = torch.device(device)
        self.temperature = temperature
        
        # Cargar modelo
        checkpoint = torch.load(model_path, map_location=self.device)
        
        obs_dim = checkpoint.get("obs_dim", 10)
        num_actions = checkpoint.get("num_actions", len(self.ACTION_TYPES))
        hidden_sizes = checkpoint.get("hidden_sizes", [128, 128, 64])
        
        self.model = CarcosaPolicyNet(obs_dim, num_actions, hidden_sizes)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()
        
        # Ajustar la lista de tipos de acción para que coincida con la salida del modelo
        self.action_types = self.ACTION_TYPES[:num_actions]

        print(f"Modelo cargado: {model_path}")
        print(f"  obs_dim={obs_dim}, num_actions={num_actions}")
        
    def _get_obs(self, state) -> torch.Tensor:
        """Extrae observación del estado."""
        features = compute_features(state, self.cfg)
        tension = tension_T(state, self.cfg, features=features)
        
        obs = torch.tensor([
            features.get("P_sanity", 0.0),
            features.get("P_keys", 0.0),
            features.get("P_mon", 0.0),
            features.get("P_umbral", 0.0),
            features.get("P_debuff", 0.0),
            features.get("P_king_risk", 0.0),
            features.get("P_crown", 0.0),
            features.get("P_round", 0.0),
            tension,
            state.king_floor / 3.0,
        ], dtype=torch.float32, device=self.device)
        
        return obs
    
    def choose(self, state, rng: RNG) -> Action:
        """
        Elige una acción usando la red neuronal.
        
        Compatible con la interfaz de PlayerPolicy.
        """
        actor = str(state.turn_order[state.turn_pos])
        legal = get_legal_actions(state, actor)
        
        if not legal:
            return Action(actor=actor, type=ActionType.END_TURN, data={})
        
        # Obtener observación
        obs = self._get_obs(state)
        
        # Forward pass
        with torch.no_grad():
            logits = self.model(obs.unsqueeze(0)).squeeze(0)
            
            # Aplicar máscara de acciones legales (acoplada al tamaño de salida del modelo)
            legal_types = set(a.type for a in legal)
            mask = torch.zeros(len(self.action_types), device=self.device)

            for i, at in enumerate(self.action_types):
                if at in legal_types:
                    mask[i] = 1.0
            
            # Aplicar máscara (poner -inf en acciones ilegales)
            masked_logits = logits.clone()
            masked_logits[mask == 0] = float("-inf")
            
            # Elegir acción
            if self.temperature == 1.0:
                action_id = torch.argmax(masked_logits).item()
            else:
                probs = torch.softmax(masked_logits / self.temperature, dim=-1)
                action_id = torch.multinomial(probs, 1).item()
        
        # Mapear a Action
            target_type = self.action_types[action_id]
        
        for a in legal:
            if a.type == target_type:
                return a
        
        # Fallback: primera acción legal
        return legal[0]


def run_evaluation_episode(
    policy,
    king_policy,
    seed: int,
    cfg: Config,
    max_steps: int = 500,
) -> Dict:
    """
    Ejecuta un episodio completo y retorna métricas.
    """
    rng = RNG(seed)
    state = make_smoke_state(seed=seed, cfg=cfg)
    
    step_idx = 0
    
    while step_idx < max_steps and not state.game_over:
        if state.phase == "PLAYER":
            action = policy.choose(state, rng)
        else:
            action = king_policy.choose(state, rng)
        
        if action is None:
            actor = str(state.turn_order[state.turn_pos]) if state.phase == "PLAYER" else "KING"
            if actor == "KING":
                action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
            else:
                action = Action(actor=actor, type=ActionType.END_TURN, data={})
        
        # Verificar legalidad
        actor = action.actor
        legal = get_legal_actions(state, actor)
        if action not in legal:
            action = rng.choice(legal) if legal else action
        
        try:
            state = step(state, action, rng, cfg)
        except ValueError:
            # Acción ilegal inesperada: intentar elegir otra acción legal o saltar turno
            actor = action.actor
            legal = get_legal_actions(state, actor)
            if legal:
                alt_action = rng.choice(legal)
                try:
                    state = step(state, alt_action, rng, cfg)
                except Exception:
                    # Si aún falla, forzar END_TURN o KING endround según corresponda
                    if state.phase == "PLAYER":
                        fallback = Action(actor=actor, type=ActionType.END_TURN, data={})
                    else:
                        fallback = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
                    try:
                        state = step(state, fallback, rng, cfg)
                    except Exception:
                        # Si sigue fallando, marcar game_over y romper
                        state.game_over = True
                        break
            else:
                # No hay acciones legales; terminar episodio
                state.game_over = True
                break
        step_idx += 1
    
    return {
        "outcome": state.outcome or "TIMEOUT",
        "steps": step_idx,
        "rounds": state.round,
        "keys_in_hand": sum(p.keys for p in state.players.values()),
        "min_sanity": min(p.sanity for p in state.players.values()),
    }


def evaluate_policy(
    policy,
    policy_name: str,
    episodes: int = 50,
    cfg: Config = None,
) -> Dict:
    """
    Evalúa una policy sobre múltiples episodios.
    """
    cfg = cfg or Config()
    king_policy = get_king_policy("RANDOM", cfg)
    
    results = {
        "policy": policy_name,
        "episodes": episodes,
        "wins": 0,
        "losses": 0,
        "timeouts": 0,
        "total_steps": [],
        "total_rounds": [],
        "final_keys": [],
        "final_sanity": [],
    }
    
    for ep in range(episodes):
        ep_result = run_evaluation_episode(
            policy=policy,
            king_policy=king_policy,
            seed=ep * 100 + 42,
            cfg=cfg,
        )
        
        if ep_result["outcome"] == "WIN":
            results["wins"] += 1
        elif ep_result["outcome"] == "LOSE":
            results["losses"] += 1
        else:
            results["timeouts"] += 1
        
        results["total_steps"].append(ep_result["steps"])
        results["total_rounds"].append(ep_result["rounds"])
        results["final_keys"].append(ep_result["keys_in_hand"])
        results["final_sanity"].append(ep_result["min_sanity"])
    
    # Calcular estadísticas
    results["win_rate"] = results["wins"] / episodes
    results["avg_steps"] = np.mean(results["total_steps"])
    results["avg_rounds"] = np.mean(results["total_rounds"])
    results["avg_keys"] = np.mean(results["final_keys"])
    results["avg_sanity"] = np.mean(results["final_sanity"])
    
    return results


def print_results(results: Dict):
    """Imprime resultados de evaluación."""
    print(f"\n{'='*50}")
    print(f"Policy: {results['policy']}")
    print(f"{'='*50}")
    print(f"Episodes: {results['episodes']}")
    print(f"Win Rate: {100*results['win_rate']:.1f}%")
    print(f"  Wins: {results['wins']}, Losses: {results['losses']}, Timeouts: {results['timeouts']}")
    print(f"Avg Steps: {results['avg_steps']:.1f}")
    print(f"Avg Rounds: {results['avg_rounds']:.1f}")
    print(f"Avg Final Keys: {results['avg_keys']:.2f}")
    print(f"Avg Final Sanity: {results['avg_sanity']:.2f}")


def compare_policies(episodes: int = 50):
    """
    Compara múltiples policies entre sí.
    """
    cfg = Config()
    
    policies = {
        "GOAL": GoalDirectedPlayerPolicy(cfg),
        "COWARD": CowardPolicy(cfg),
        "BERSERKER": BerserkerPolicy(cfg),
        "SPEEDRUNNER": SpeedrunnerPolicy(cfg),
        "RANDOM": RandomPolicy(),
    }
    
    all_results = []
    
    for name, policy in policies.items():
        print(f"\nEvaluando {name}...")
        results = evaluate_policy(policy, name, episodes, cfg)
        print_results(results)
        all_results.append(results)
    
    # Tabla comparativa
    print(f"\n{'='*70}")
    print("COMPARACIÓN DE POLICIES")
    print(f"{'='*70}")
    print(f"{'Policy':<15} {'Win Rate':>10} {'Avg Steps':>12} {'Avg Rounds':>12}")
    print(f"{'-'*70}")
    
    for r in sorted(all_results, key=lambda x: -x["win_rate"]):
        print(f"{r['policy']:<15} {100*r['win_rate']:>9.1f}% {r['avg_steps']:>12.1f} {r['avg_rounds']:>12.1f}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate CARCOSA models")
    
    parser.add_argument("--model", type=str, default=None,
                        help="Ruta al modelo .pt para evaluar")
    parser.add_argument("--episodes", type=int, default=50,
                        help="Número de episodios")
    parser.add_argument("--compare", action="store_true",
                        help="Comparar todas las policies heurísticas")
    parser.add_argument("--temperature", type=float, default=1.0,
                        help="Temperatura para sampling (1.0 = greedy)")
    parser.add_argument("--device", type=str, default=None,
                        help="Dispositivo a usar: 'cuda' o 'cpu'. Si no se especifica, intenta usar cuda si está disponible.")
    
    args = parser.parse_args()
    
    if args.compare:
        compare_policies(args.episodes)
    elif args.model:
        cfg = Config()
        # Determinar dispositivo: usar argumento si se dio, sino intentar cuda cuando esté disponible
        device = args.device if args.device is not None else ("cuda" if torch.cuda.is_available() else "cpu")
        policy = NeuralNetworkPlayerPolicy(
            args.model,
            cfg=cfg,
            device=device,
            temperature=args.temperature,
        )
        results = evaluate_policy(policy, f"NN:{Path(args.model).stem}", args.episodes, cfg)
        print_results(results)
    else:
        print("Uso:")
        print("  python train/evaluate.py --model models/bc_mlp_GOAL_best.pt --episodes 50")
        print("  python train/evaluate.py --compare --episodes 100")


if __name__ == "__main__":
    main()

from __future__ import annotations
from typing import Any, Dict, List
import json
import os
import time

from engine.config import Config
from engine.state import GameState
from engine.tension import compute_features, tension_T, king_utility


def _keys_in_hand(state: GameState) -> int:
    return sum(p.keys for p in state.players.values())


def _keys_in_game(state: GameState, cfg: Config) -> int:
    return max(0, cfg.KEYS_TOTAL - state.keys_destroyed)


def _summary(state: GameState, cfg: Config) -> Dict[str, Any]:
    sanities = [p.sanity for p in state.players.values()] if state.players else []
    umbral_frac = (sum(1 for p in state.players.values() if p.at_umbral) / len(state.players)) if state.players else 0.0
    return {
        "min_sanity": min(sanities) if sanities else None,
        "mean_sanity": (sum(sanities) / len(sanities)) if sanities else None,
        "monsters": len(state.monsters),
        "keys_in_hand": _keys_in_hand(state),
        "keys_destroyed": state.keys_destroyed,
        "keys_in_game": _keys_in_game(state, cfg),
        "crown": bool(state.flags.get("CROWN_YELLOW", False)),
        "umbral_frac": umbral_frac,
        "king_floor": state.king_floor,
    }



def calculate_reward(state: GameState, next_state: GameState, cfg: Config) -> float:
    """
    Calcula la recompensa (reward) para RL basada en la transición.
    Schema propuesta:
    - WIN: +100
    - LOSE: -10
    - Encontrar Llave (Global): +1
    - Revelar Habitación: +0.1
    - Perder Cordura: -0.1 per point
    - Morir (Game Over Lose): -10 (ya cubierto por LOSE, pero si es personal...)
    """
    if next_state.game_over:
        if next_state.outcome == "WIN":
            return 100.0
        else:
            return -10.0

    reward = 0.0

    # 1. Keys Progress
    keys_prev = sum(p.keys for p in state.players.values())
    keys_next = sum(p.keys for p in next_state.players.values())
    if keys_next > keys_prev:
        reward += 1.0 * (keys_next - keys_prev)

    # 2. Key Pool Increase (Cámara Letal success)
    # Check effective keys total? 
    # Hard to track directly without diffing cfg/state complexly. 
    # Let's stick to keys in hand for now.

    # 3. Exploration (Revealed Rooms)
    revealed_prev = sum(1 for r in state.rooms.values() if r.revealed > 0)
    revealed_next = sum(1 for r in next_state.rooms.values() if r.revealed > 0)
    if revealed_next > revealed_prev:
        reward += 0.1 * (revealed_next - revealed_prev)

    # 4. Sanity Loss (Penalización leve)
    # Comparar sanidad total
    sanity_prev = sum(p.sanity for p in state.players.values())
    sanity_next = sum(p.sanity for p in next_state.players.values())
    diff_sanity = sanity_next - sanity_prev
    # Note: diff_sanity is negative if damage taken
    if diff_sanity < 0:
        reward += 0.1 * diff_sanity # -0.1 per point lost

    return reward


def transition_record(
    state: GameState,
    action: Dict[str, Any],
    next_state: GameState,
    cfg: Config,
    step_idx: int,
) -> Dict[str, Any]:
    roles_assigned = None
    if step_idx == 0:
        if getattr(state, "roles_assigned", None):
            roles_assigned = {str(k): str(v) for k, v in state.roles_assigned.items()}
        else:
            roles_assigned = {str(pid): p.role_id for pid, p in state.players.items()}

    f0 = compute_features(state, cfg)
    f1 = compute_features(next_state, cfg)
    T0 = tension_T(state, cfg, features=f0)
    T1 = tension_T(next_state, cfg, features=f1)

    # Calculate RL Reward
    reward = calculate_reward(state, next_state, cfg)

    # Prepare action_data, including d6 if present
    action_data = action.get("data", {}).copy()
    if "d6" in action:
        action_data["d6"] = action["d6"]

    rec: Dict[str, Any] = {
        "step": step_idx,
        "round": state.round,
        "phase": state.phase,
        "actor": action["actor"],
        "action_type": action["type"],
        "action_data": action_data,

        "reward": reward,  # New RL Field

        "T_pre": T0,
        "T_post": T1,
        "features_pre": f0,
        "features_post": f1,

        "summary_pre": _summary(state, cfg),
        "summary_post": _summary(next_state, cfg),

        "king_utility_pre": king_utility(state, cfg, features=f0),
        "king_utility_post": king_utility(next_state, cfg, features=f1),
        "king_reward": king_utility(next_state, cfg, features=f1) - king_utility(state, cfg, features=f0),

        "done": bool(next_state.game_over),
        "outcome": next_state.outcome,
        "sanity_loss_events": list(getattr(next_state, "last_sanity_loss_events", [])),
        
        # FULL REPLAY STATE
        "full_state": state.to_dict()
    }
    if roles_assigned is not None:
        rec["roles_assigned"] = roles_assigned
    return rec


def write_jsonl(path: str, records: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def default_run_path(prefix: str = "runs/run") -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.jsonl"

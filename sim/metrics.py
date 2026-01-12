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


def transition_record(
    state: GameState,
    action: Dict[str, Any],
    next_state: GameState,
    cfg: Config,
    step_idx: int,
) -> Dict[str, Any]:
    f0 = compute_features(state, cfg)
    f1 = compute_features(next_state, cfg)
    T0 = tension_T(state, cfg)
    T1 = tension_T(next_state, cfg)

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

        "T_pre": T0,
        "T_post": T1,
        "features_pre": f0,
        "features_post": f1,

        "summary_pre": _summary(state, cfg),
        "summary_post": _summary(next_state, cfg),

        "king_utility_pre": king_utility(state, cfg),
        "king_utility_post": king_utility(next_state, cfg),
        "king_reward": king_utility(next_state, cfg) - king_utility(state, cfg),

        "done": bool(next_state.game_over),
        "outcome": next_state.outcome,
    }
    return rec


def write_jsonl(path: str, records: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def default_run_path(prefix: str = "runs/run") -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.jsonl"

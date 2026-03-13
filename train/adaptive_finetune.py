"""
Fine-tuning adaptativo por bloques para CARCOSA.
================================================

Entrena en chunks (ej. 5k), evalúa cada candidato y continúa desde
el mejor checkpoint aceptado con selector lexicográfico.

Selector principal (lexicográfico):
    1) win_rate
    2) win_given_reached_keys_goal
    3) rate_reached_keys_goal
    4) rate_all_near_umbral
    5) key_destroyed_rate (menor es mejor)
    6) minus5_rate (menor es mejor)
    7) avg_reward

Score auxiliar de desempate:
    score = w_win_rate * win_rate
          + w_reward * reward_norm
          + w_cross_info * usage_cross_ratio
          - w_minus5_penalty * minus5_rate

Uso sugerido:
    python train/adaptive_finetune.py \
      --base-model models/rl_info100k_finetune3_balanced/ppo_carcosa_finetune3_balanced_final_20260305_222647.zip \
      --total-timesteps 50000 \
      --chunk-timesteps 5000 \
      --n-envs 4 \
      --eval-episodes 30

Perfiles de selector:
    - default: prioriza victoria directa (win_rate) + cierre.
    - funnel: prioriza embudo de llaves (3 -> 4 -> win_given_reached_keys_goal).
    - funnel_k4: prioriza conversión a 4 llaves (4 -> 3 -> ...).
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from collections import Counter, deque

import numpy as np

try:
    from stable_baselines3 import PPO, A2C, DQN
    from stable_baselines3.common.vec_env import DummyVecEnv
    from stable_baselines3.common.buffers import RolloutBuffer
    HAS_SB3 = True
except ImportError:
    HAS_SB3 = False
    print("ERROR: stable-baselines3 no instalado. Instalar con: pip install stable-baselines3")

try:
    from sb3_contrib import MaskablePPO
    HAS_SB3_CONTRIB = True
except ImportError:
    MaskablePPO = None
    HAS_SB3_CONTRIB = False

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.actions import ActionType
from engine.board import floor_of, neighbors
from engine.legality import get_legal_actions
from train.carcosa_env import CarcosaEnv


def _normalize_algorithm_name(raw_name: Optional[str]) -> str:
    name = (raw_name or "ppo").strip().lower()
    if name in {"maskable", "maskableppo", "maskable_ppo"}:
        return "maskable_ppo"
    return name


def _bootstrap_maskable_from_ppo(
    ppo_model: PPO,
    env,
    args: Optional[argparse.Namespace],
    tensorboard_log: Optional[str] = None,
):
    if not HAS_SB3_CONTRIB:
        raise RuntimeError(
            "sb3-contrib no está disponible; instalar con: pip install sb3-contrib"
        )

    default_lr = getattr(args, "learning_rate", 3e-4) if args is not None else 3e-4
    default_n_steps = getattr(args, "ppo_n_steps", 2048) if args is not None else 2048
    default_clip_range = getattr(args, "clip_range", 0.2) if args is not None else 0.2
    default_ent_coef = getattr(args, "ent_coef", 0.01) if args is not None else 0.01
    default_seed = getattr(args, "seed", 72) if args is not None else 72

    policy_name = "MlpPolicy"
    model = MaskablePPO(
        policy=policy_name,
        env=env,
        learning_rate=getattr(ppo_model, "learning_rate", default_lr),
        n_steps=getattr(ppo_model, "n_steps", default_n_steps),
        batch_size=getattr(ppo_model, "batch_size", 64),
        n_epochs=getattr(ppo_model, "n_epochs", 10),
        gamma=getattr(ppo_model, "gamma", 0.99),
        gae_lambda=getattr(ppo_model, "gae_lambda", 0.95),
        clip_range=getattr(ppo_model, "clip_range", default_clip_range),
        ent_coef=getattr(ppo_model, "ent_coef", default_ent_coef),
        vf_coef=getattr(ppo_model, "vf_coef", 0.5),
        max_grad_norm=getattr(ppo_model, "max_grad_norm", 0.5),
        tensorboard_log=tensorboard_log,
        seed=default_seed,
        policy_kwargs=getattr(ppo_model, "policy_kwargs", None),
        verbose=0,
    )

    model.policy.load_state_dict(ppo_model.policy.state_dict(), strict=False)
    return model


def _load_model(
    model_path: str,
    *,
    algorithm: str,
    env=None,
    tensorboard_log: Optional[str] = None,
    args: Optional[argparse.Namespace] = None,
):
    algorithm = _normalize_algorithm_name(algorithm)

    if algorithm == "a2c":
        return A2C.load(model_path, env=env)
    if algorithm == "dqn":
        return DQN.load(model_path, env=env)
    if algorithm == "maskable_ppo":
        if not HAS_SB3_CONTRIB:
            raise RuntimeError(
                "MaskablePPO requiere sb3-contrib. Instalar con: pip install sb3-contrib"
            )
        try:
            return MaskablePPO.load(model_path, env=env, tensorboard_log=tensorboard_log)
        except Exception:
            if args is None:
                raise
            ppo_model = PPO.load(model_path, env=env, tensorboard_log=tensorboard_log)
            return _bootstrap_maskable_from_ppo(ppo_model, env=env, args=args, tensorboard_log=tensorboard_log)

    return PPO.load(model_path, env=env, tensorboard_log=tensorboard_log)


def _load_training_model(model_path: str, env, tensorboard_log: str, args: argparse.Namespace):
    return _load_model(
        model_path=model_path,
        algorithm=args.algorithm,
        env=env,
        tensorboard_log=tensorboard_log,
        args=args,
    )


def _current_actor(env: CarcosaEnv) -> str:
    pending = env.state.flags.get("PENDING_SACRIFICE_CHECK")
    if isinstance(pending, list):
        pending = pending[0] if pending else None
    if pending:
        return str(pending)
    if env.state.phase == "KING":
        return "KING"
    return str(env.state.turn_order[env.state.turn_pos])


def _classify_outcome(outcome: Any) -> str:
    if outcome == "WIN":
        return "WIN"
    if isinstance(outcome, str) and outcome.startswith("LOSE"):
        return "LOSE"
    return "TIMEOUT"


def _classify_keys_goal_loss_reason(
    *,
    entered_minus5_with_keys: bool,
    executed_action_type: Optional[str],
) -> str:
    if entered_minus5_with_keys:
        return "minus5_with_keys"

    if executed_action_type == ActionType.ACCEPT_SACRIFICE.value:
        return "accept_sacrifice"
    if executed_action_type == ActionType.SACRIFICE.value:
        return "sacrifice"

    if executed_action_type:
        return f"action_{executed_action_type}"
    return "unknown"


def _classify_keys_goal_post_reach_reason(
    *,
    outcome: str,
    outcome_raw: str,
    had_keys_and_all_at_umbral: bool,
    keys_goal_lost_reason: Optional[str],
) -> str:
    if outcome == "WIN":
        return "win"

    if keys_goal_lost_reason:
        return f"lost_4th_key::{keys_goal_lost_reason}"

    if had_keys_and_all_at_umbral:
        return "nonwin_despite_keys_and_umbral"

    if "KEYS_DESTROYED" in outcome_raw:
        return "lose_keys_destroyed_before_umbral"
    if "MINUS5" in outcome_raw:
        return "lose_minus5_before_umbral"
    if outcome == "TIMEOUT":
        return "timeout_before_umbral"

    return "umbral_not_converged"


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _reward_to_unit_interval(avg_reward: float, reward_floor: float, reward_ceiling: float) -> float:
    if reward_ceiling <= reward_floor:
        return 0.0
    return _clip01((avg_reward - reward_floor) / (reward_ceiling - reward_floor))


def _compute_score(metrics: Dict[str, float], args: argparse.Namespace) -> float:
    reward_norm = _reward_to_unit_interval(
        avg_reward=metrics["avg_reward"],
        reward_floor=args.reward_floor,
        reward_ceiling=args.reward_ceiling,
    )
    score = (
        args.weight_win_rate * metrics["win_rate"]
        + args.weight_reward * reward_norm
        + args.weight_cross_info * metrics["usage_cross_ratio"]
        - args.weight_minus5_penalty * metrics["minus5_rate"]
    )
    metrics["reward_norm"] = reward_norm
    metrics["score"] = score
    return score


def _room_neighbors_with_stairs(state, room):
    for nb in neighbors(room):
        yield nb

    floor = floor_of(room)
    if room == state.stairs.get(floor):
        if floor > 1:
            up = state.stairs.get(floor - 1)
            if up is not None:
                yield up
        if floor < 3:
            down = state.stairs.get(floor + 1)
            if down is not None:
                yield down


def _distance_to_umbral(state, umbral_node: str, room) -> int:
    if str(room) == str(umbral_node):
        return 0

    queue = deque([(room, 0)])
    visited = {room}
    while queue:
        current, dist = queue.popleft()
        for nb in _room_neighbors_with_stairs(state, current):
            if nb in visited:
                continue
            if str(nb) == str(umbral_node):
                return dist + 1
            visited.add(nb)
            queue.append((nb, dist + 1))

    return 999


def _all_players_within_umbral_distance(state, umbral_node: str, max_distance: int = 1) -> bool:
    return all(
        _distance_to_umbral(state, umbral_node, player.room) <= max_distance
        for player in state.players.values()
    )


def _all_players_at_umbral(state, umbral_node: str) -> bool:
    return all(
        _distance_to_umbral(state, umbral_node, player.room) == 0
        for player in state.players.values()
    )


def _lex_metric_compare(candidate_value: float, incumbent_value: float, higher_is_better: bool, epsilon: float) -> int:
    if higher_is_better:
        if candidate_value > incumbent_value + epsilon:
            return 1
        if incumbent_value > candidate_value + epsilon:
            return -1
        return 0

    if candidate_value + epsilon < incumbent_value:
        return 1
    if incumbent_value + epsilon < candidate_value:
        return -1
    return 0


def _selector_order_checks(args: argparse.Namespace):
    profile = str(getattr(args, "selector_profile", "default")).strip().lower()
    if profile == "funnel":
        return [
            ("rate_reached_3_keys", True, args.lex_eps_rate),
            ("rate_reached_4_keys", True, args.lex_eps_rate),
            ("minus5_entry_with_keys_rate", False, args.lex_eps_rate),
            ("win_given_reached_keys_goal", True, args.lex_eps_rate),
            ("win_rate", True, args.lex_eps_rate),
            ("rate_reached_keys_goal", True, args.lex_eps_rate),
            ("rate_all_near_umbral", True, args.lex_eps_rate),
            ("key_destroyed_rate", False, args.lex_eps_rate),
            ("minus5_rate", False, args.lex_eps_rate),
            ("avg_reward", True, args.lex_eps_reward),
        ]
    if profile == "funnel_k4":
        return [
            ("rate_reached_4_keys", True, args.lex_eps_rate),
            ("rate_reached_3_keys", True, args.lex_eps_rate),
            ("minus5_entry_with_keys_rate", False, args.lex_eps_rate),
            ("win_given_reached_keys_goal", True, args.lex_eps_rate),
            ("win_rate", True, args.lex_eps_rate),
            ("rate_reached_keys_goal", True, args.lex_eps_rate),
            ("rate_all_near_umbral", True, args.lex_eps_rate),
            ("key_destroyed_rate", False, args.lex_eps_rate),
            ("minus5_rate", False, args.lex_eps_rate),
            ("avg_reward", True, args.lex_eps_reward),
        ]

    return [
        ("win_rate", True, args.lex_eps_rate),
        ("win_given_reached_keys_goal", True, args.lex_eps_rate),
        ("rate_reached_keys_goal", True, args.lex_eps_rate),
        ("rate_all_near_umbral", True, args.lex_eps_rate),
        ("key_destroyed_rate", False, args.lex_eps_rate),
        ("minus5_rate", False, args.lex_eps_rate),
        ("avg_reward", True, args.lex_eps_reward),
    ]


def _selector_order_labels(args: argparse.Namespace) -> list[str]:
    labels = []
    for metric_name, higher_is_better, _ in _selector_order_checks(args):
        labels.append(metric_name if higher_is_better else f"{metric_name} (lower)")
    labels.append("score_tiebreak")
    return labels


def compare_metrics_lexicographic(
    candidate_metrics: Dict[str, float],
    incumbent_metrics: Dict[str, float],
    args: argparse.Namespace,
) -> tuple[bool, str, float]:
    candidate_match_rate = float(candidate_metrics.get("requested_executed_match_rate", 0.0))
    candidate_fallback_rate = float(candidate_metrics.get("fallback_substitution_rate", 1.0))
    candidate_minus5_with_keys_rate = float(candidate_metrics.get("minus5_entry_with_keys_rate", 0.0))
    if candidate_match_rate + 1e-9 < args.min_match_rate:
        return False, "action_gate_match", candidate_match_rate - args.min_match_rate
    if candidate_fallback_rate - 1e-9 > args.max_fallback_substitution_rate:
        return False, "action_gate_fallback", candidate_fallback_rate - args.max_fallback_substitution_rate
    if candidate_minus5_with_keys_rate - 1e-9 > args.max_minus5_with_keys_rate:
        return False, "risk_gate_minus5_with_keys", candidate_minus5_with_keys_rate - args.max_minus5_with_keys_rate

    ordered_checks = _selector_order_checks(args)

    for metric_name, higher_is_better, epsilon in ordered_checks:
        candidate_value = float(candidate_metrics.get(metric_name, 0.0))
        incumbent_value = float(incumbent_metrics.get(metric_name, 0.0))
        cmp_result = _lex_metric_compare(candidate_value, incumbent_value, higher_is_better, epsilon)
        if cmp_result > 0:
            return True, metric_name, candidate_value - incumbent_value
        if cmp_result < 0:
            return False, metric_name, candidate_value - incumbent_value

    score_delta = float(candidate_metrics.get("score", 0.0) - incumbent_metrics.get("score", 0.0))
    return score_delta >= args.min_improvement, "score_tiebreak", score_delta


def _predict_action(model, obs, env: CarcosaEnv, algorithm: str):
    if _normalize_algorithm_name(algorithm) == "maskable_ppo":
        action_mask = env.action_masks()
        action, _ = model.predict(obs, deterministic=True, action_masks=action_mask)
        return action
    action, _ = model.predict(obs, deterministic=True)
    return action


def evaluate_model(
    model_path: str,
    episodes: int,
    seed_base: int,
    env_kwargs: Dict[str, Any],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    algorithm = _normalize_algorithm_name(getattr(args, "algorithm", "ppo"))
    env = CarcosaEnv(**env_kwargs)
    model = _load_model(
        model_path,
        algorithm=algorithm,
        env=env,
        args=args,
    )

    outcomes = {"WIN": 0, "LOSE": 0, "TIMEOUT": 0}
    rewards = []
    steps_list = []
    keys_goal = int(env.cfg.KEYS_TO_WIN)
    umbral_node = str(env.cfg.UMBRAL_NODE)
    key_milestones = sorted({1, 2, 3, 4, keys_goal})
    milestone_step_sums = {milestone: 0 for milestone in key_milestones}
    milestone_hits = {milestone: 0 for milestone in key_milestones}

    reached_keys_goal_episodes = 0
    all_near_umbral_episodes = 0
    wins_after_keys_goal = 0
    episodes_with_keys_and_all_at_umbral = 0
    fail_after_keys_goal_total = 0
    fail_after_keys_goal_without_full_umbral = 0
    fail_after_keys_goal_with_full_umbral = 0
    fail_after_keys_goal_due_umbral_only = 0
    keys_goal_reach_events = 0
    keys_goal_source_counter = Counter()
    keys_goal_carrier_counter = Counter()
    keys_goal_lost_events = 0
    keys_goal_lost_with_minus5_with_keys_events = 0
    keys_goal_loss_action_counter = Counter()
    keys_goal_loss_reason_counter = Counter()
    keys_goal_lost_carrier_counter = Counter()
    keys_goal_post_reach_reason_counter = Counter()
    keys_goal_terminal_outcome_counter = Counter()
    keys_goal_carriers_at_reach_sum = 0
    keys_goal_carriers_at_reach_count = 0
    keys_goal_steps_to_loss_sum = 0
    keys_goal_steps_to_loss_count = 0
    keys_goal_survival_steps_sum = 0
    keys_goal_survival_steps_count = 0
    keys_goal_survived_to_end_episodes = 0
    keys_goal_end_team_distance_sum = 0
    keys_goal_end_team_distance_count = 0
    keys_goal_end_team_distance_nonwin_sum = 0
    keys_goal_end_team_distance_nonwin_count = 0
    keys_goal_nonwin_with_keys_without_umbral_events = 0

    player_steps = 0
    king_steps = 0
    peek_available_steps = 0
    pred_peek_when_available = 0
    pred_skip_when_available = 0
    exec_peek_when_available = 0
    exec_skip_when_available = 0
    predicted_legal_type_steps = 0
    requested_matched_executed_steps = 0
    invalid_intent_steps = 0
    masked_out_steps = 0
    fallback_substitution_steps = 0
    action_source_counter = Counter()
    fallback_steps = 0

    effective_peek_steps = 0
    effective_search_steps = 0
    usage_events_total = 0
    usage_events_cross = 0
    resolved_events_total = 0
    resolved_events_cross = 0
    minus5_losses = 0
    key_destroyed_losses = 0
    minus5_entry_events = 0
    minus5_entry_with_keys_events = 0
    sacrifice_action_steps = 0
    accept_sacrifice_action_steps = 0

    action_types = CarcosaEnv.ACTION_TYPES
    peek_idx = action_types.index(ActionType.PEEK_ROOM_DECK)
    skip_idx = action_types.index(ActionType.SKIP_PEEK)

    for ep in range(episodes):
        obs, info = env.reset(seed=seed_base + ep * 37)
        done = False
        ep_reward = 0.0
        ep_steps = 0
        reached_keys_goal = False
        all_near_umbral = False
        had_keys_and_all_at_umbral = False
        milestone_first_step = {milestone: None for milestone in key_milestones}
        keys_goal_first_step = None
        keys_goal_first_source = None
        keys_goal_first_carriers: list[str] = []
        keys_goal_lost_step = None
        keys_goal_lost_reason = None

        while not done:
            pre_player_snapshot = {
                str(pid): {
                    "at_minus5": bool(player.at_minus5),
                    "sanity": int(player.sanity),
                    "keys": int(player.keys),
                }
                for pid, player in env.state.players.items()
            }
            pre_total_keys = sum(player_info["keys"] for player_info in pre_player_snapshot.values())
            entered_minus5_with_keys_this_step = False

            actor = _current_actor(env)
            if actor == "KING":
                king_steps += 1
                legal = []
                legal_types = set()
            else:
                player_steps += 1
                legal = get_legal_actions(env.state, actor)
                legal_types = {a.type for a in legal}

            has_peek = any(a.type == ActionType.PEEK_ROOM_DECK for a in legal)
            if has_peek:
                peek_available_steps += 1

            before_memory = {
                k: {
                    "used_count": int(v.get("used_count", 0)),
                    "resolved": bool(v.get("resolved", False)),
                    "source_player": v.get("source_player"),
                }
                for k, v in env.shared_info_memory.items()
            }

            action = _predict_action(model, obs, env=env, algorithm=algorithm)
            action_id = int(action)
            pred_type = action_types[action_id] if 0 <= action_id < len(action_types) else None

            if actor != "KING" and pred_type in legal_types:
                predicted_legal_type_steps += 1

            if has_peek and action_id == peek_idx:
                pred_peek_when_available += 1
            if has_peek and action_id == skip_idx:
                pred_skip_when_available += 1

            obs, reward, terminated, truncated, info = env.step(action_id)
            done = terminated or truncated
            ep_reward += float(reward)
            ep_steps += 1
            current_player_keys = {
                str(pid): int(player.keys)
                for pid, player in env.state.players.items()
            }

            keys_in_hand = int(info.get("keys_in_hand", 0))
            for milestone in key_milestones:
                if keys_in_hand >= milestone and milestone_first_step[milestone] is None:
                    milestone_first_step[milestone] = ep_steps

            if keys_in_hand >= keys_goal:
                reached_keys_goal = True
            if _all_players_within_umbral_distance(env.state, umbral_node, max_distance=1):
                all_near_umbral = True
            if keys_in_hand >= keys_goal and _all_players_at_umbral(env.state, umbral_node):
                had_keys_and_all_at_umbral = True

            executed_action_type = info.get("executed_action_type")
            if has_peek and executed_action_type == ActionType.PEEK_ROOM_DECK.value:
                exec_peek_when_available += 1
            if has_peek and executed_action_type == ActionType.SKIP_PEEK.value:
                exec_skip_when_available += 1
            if executed_action_type == ActionType.SACRIFICE.value:
                sacrifice_action_steps += 1
            if executed_action_type == ActionType.ACCEPT_SACRIFICE.value:
                accept_sacrifice_action_steps += 1

            if keys_goal_first_step is None and keys_in_hand >= keys_goal and pre_total_keys < keys_goal:
                keys_goal_first_step = ep_steps
                keys_goal_first_source = executed_action_type or "UNKNOWN"
                keys_goal_reach_events += 1
                keys_goal_source_counter[keys_goal_first_source] += 1

                gained_players = [
                    pid
                    for pid, curr_keys in current_player_keys.items()
                    if curr_keys > int(pre_player_snapshot.get(pid, {}).get("keys", 0))
                ]
                if gained_players:
                    keys_goal_first_carriers = gained_players
                else:
                    keys_goal_first_carriers = [
                        pid
                        for pid, curr_keys in current_player_keys.items()
                        if curr_keys > 0
                    ]
                for pid in keys_goal_first_carriers:
                    keys_goal_carrier_counter[pid] += 1
                keys_goal_carriers_at_reach_sum += len(keys_goal_first_carriers)
                keys_goal_carriers_at_reach_count += 1

            for pid, player in env.state.players.items():
                pid_key = str(pid)
                before = pre_player_snapshot.get(pid_key)
                if before is None:
                    continue
                entered_minus5 = (
                    (not bool(before["at_minus5"]))
                    and (bool(player.at_minus5) or int(player.sanity) <= -5)
                )
                if entered_minus5:
                    minus5_entry_events += 1
                    if int(before["keys"]) > 0:
                        minus5_entry_with_keys_events += 1
                        entered_minus5_with_keys_this_step = True

            if keys_goal_first_step is not None and keys_goal_lost_step is None and keys_in_hand < keys_goal:
                keys_goal_lost_step = ep_steps
                keys_goal_lost_events += 1
                loss_action = executed_action_type or "UNKNOWN"
                keys_goal_loss_action_counter[loss_action] += 1

                lost_carriers = [
                    pid
                    for pid, before_snapshot in pre_player_snapshot.items()
                    if int(current_player_keys.get(pid, 0)) < int(before_snapshot.get("keys", 0))
                ]
                for pid in lost_carriers:
                    keys_goal_lost_carrier_counter[pid] += 1

                keys_goal_lost_reason = _classify_keys_goal_loss_reason(
                    entered_minus5_with_keys=entered_minus5_with_keys_this_step,
                    executed_action_type=executed_action_type,
                )
                keys_goal_loss_reason_counter[keys_goal_lost_reason] += 1

                if keys_goal_first_step is not None:
                    keys_goal_steps_to_loss_sum += max(0, int(ep_steps) - int(keys_goal_first_step))
                    keys_goal_steps_to_loss_count += 1

                if entered_minus5_with_keys_this_step:
                    keys_goal_lost_with_minus5_with_keys_events += 1

            if actor != "KING" and info.get("requested_action_matched_executed"):
                requested_matched_executed_steps += 1
            if actor != "KING" and info.get("illegal_action_intent"):
                invalid_intent_steps += 1
            if actor != "KING" and info.get("masked_out_action"):
                masked_out_steps += 1
            if actor != "KING" and info.get("fallback_substitution"):
                fallback_substitution_steps += 1

            action_source = info.get("action_selection_source")
            if action_source:
                action_source_counter[str(action_source)] += 1
                if action_source in {
                    "GUIDED_FALLBACK",
                    "RANDOM_FALLBACK",
                    "PENDING_RANDOM_FALLBACK",
                    "DETERMINISTIC_FALLBACK",
                    "PENDING_DETERMINISTIC_FALLBACK",
                }:
                    fallback_steps += 1

            step_id = env.step_count
            seen_this_step = [
                entry
                for entry in env.shared_info_memory.values()
                if int(entry.get("seen_step", -1)) == step_id
            ]
            if any(entry.get("observation_type") == ActionType.PEEK_ROOM_DECK.value for entry in seen_this_step):
                effective_peek_steps += 1
            if any(entry.get("observation_type") == ActionType.SEARCH.value for entry in seen_this_step):
                effective_search_steps += 1

            for memory_key, after_entry in env.shared_info_memory.items():
                before_entry = before_memory.get(memory_key)
                prev_used = 0 if before_entry is None else before_entry["used_count"]
                curr_used = int(after_entry.get("used_count", 0))
                if curr_used > prev_used:
                    delta = curr_used - prev_used
                    usage_events_total += delta
                    source_player = after_entry.get("source_player")
                    if source_player and source_player != actor:
                        usage_events_cross += delta

                prev_resolved = False if before_entry is None else before_entry["resolved"]
                curr_resolved = bool(after_entry.get("resolved", False))
                if (not prev_resolved) and curr_resolved:
                    resolved_events_total += 1
                    source_player = after_entry.get("source_player")
                    if source_player and source_player != actor:
                        resolved_events_cross += 1

        outcome_raw = str(info.get("outcome") or "")
        outcome = _classify_outcome(outcome_raw)
        outcomes[outcome] += 1
        if "MINUS5" in outcome_raw:
            minus5_losses += 1
        if "KEYS_DESTROYED" in outcome_raw:
            key_destroyed_losses += 1
        rewards.append(ep_reward)
        steps_list.append(ep_steps)

        for milestone, first_step in milestone_first_step.items():
            if first_step is None:
                continue
            milestone_hits[milestone] += 1
            milestone_step_sums[milestone] += int(first_step)

        if keys_goal_first_step is not None:
            survival_end_step = keys_goal_lost_step if keys_goal_lost_step is not None else ep_steps
            keys_goal_survival_steps_sum += max(0, int(survival_end_step) - int(keys_goal_first_step))
            keys_goal_survival_steps_count += 1
            if keys_goal_lost_step is None:
                keys_goal_survived_to_end_episodes += 1

        if reached_keys_goal:
            reached_keys_goal_episodes += 1
            keys_goal_terminal_outcome_counter[outcome_raw or outcome] += 1

            final_team_distance = sum(
                _distance_to_umbral(env.state, umbral_node, player.room)
                for player in env.state.players.values()
            )
            keys_goal_end_team_distance_sum += float(final_team_distance)
            keys_goal_end_team_distance_count += 1

            if outcome == "WIN":
                wins_after_keys_goal += 1
            if had_keys_and_all_at_umbral:
                episodes_with_keys_and_all_at_umbral += 1

            post_reach_reason = _classify_keys_goal_post_reach_reason(
                outcome=outcome,
                outcome_raw=outcome_raw,
                had_keys_and_all_at_umbral=had_keys_and_all_at_umbral,
                keys_goal_lost_reason=keys_goal_lost_reason,
            )
            keys_goal_post_reach_reason_counter[post_reach_reason] += 1

            if outcome != "WIN":
                keys_goal_end_team_distance_nonwin_sum += float(final_team_distance)
                keys_goal_end_team_distance_nonwin_count += 1
                fail_after_keys_goal_total += 1
                if had_keys_and_all_at_umbral:
                    fail_after_keys_goal_with_full_umbral += 1
                else:
                    fail_after_keys_goal_without_full_umbral += 1
                    if keys_goal_lost_step is None:
                        keys_goal_nonwin_with_keys_without_umbral_events += 1
                    if "MINUS5" not in outcome_raw and "KEYS_DESTROYED" not in outcome_raw:
                        fail_after_keys_goal_due_umbral_only += 1
        if all_near_umbral:
            all_near_umbral_episodes += 1

    env.close()

    total_steps = player_steps + king_steps
    metrics = {
        "algorithm": algorithm,
        "episodes": episodes,
        "wins": outcomes["WIN"],
        "losses": outcomes["LOSE"],
        "timeouts": outcomes["TIMEOUT"],
        "win_rate": outcomes["WIN"] / episodes if episodes else 0.0,
        "avg_reward": float(np.mean(rewards)) if rewards else 0.0,
        "std_reward": float(np.std(rewards)) if rewards else 0.0,
        "avg_steps": float(np.mean(steps_list)) if steps_list else 0.0,
        "rate_reached_keys_goal": (reached_keys_goal_episodes / episodes) if episodes else 0.0,
        "win_given_reached_keys_goal": (wins_after_keys_goal / reached_keys_goal_episodes) if reached_keys_goal_episodes else 0.0,
        "episodes_with_keys_and_all_at_umbral": episodes_with_keys_and_all_at_umbral,
        "rate_keys_goal_and_all_at_umbral": (episodes_with_keys_and_all_at_umbral / episodes) if episodes else 0.0,
        "fail_after_keys_goal_total": fail_after_keys_goal_total,
        "fail_after_keys_goal_rate": (fail_after_keys_goal_total / episodes) if episodes else 0.0,
        "fail_after_keys_goal_without_full_umbral": fail_after_keys_goal_without_full_umbral,
        "fail_after_keys_goal_without_full_umbral_share": (
            fail_after_keys_goal_without_full_umbral / fail_after_keys_goal_total
        ) if fail_after_keys_goal_total else 0.0,
        "fail_after_keys_goal_with_full_umbral": fail_after_keys_goal_with_full_umbral,
        "fail_after_keys_goal_with_full_umbral_share": (
            fail_after_keys_goal_with_full_umbral / fail_after_keys_goal_total
        ) if fail_after_keys_goal_total else 0.0,
        "fail_after_keys_goal_due_umbral_only": fail_after_keys_goal_due_umbral_only,
        "fail_after_keys_goal_due_umbral_only_share": (
            fail_after_keys_goal_due_umbral_only / fail_after_keys_goal_total
        ) if fail_after_keys_goal_total else 0.0,
        "keys_goal_reach_events": keys_goal_reach_events,
        "keys_goal_lost_events": keys_goal_lost_events,
        "keys_goal_loss_rate_given_reached": (
            keys_goal_lost_events / keys_goal_reach_events
        ) if keys_goal_reach_events else 0.0,
        "keys_goal_survived_to_end_episodes": keys_goal_survived_to_end_episodes,
        "keys_goal_survived_to_end_rate_given_reached": (
            keys_goal_survived_to_end_episodes / keys_goal_reach_events
        ) if keys_goal_reach_events else 0.0,
        "avg_steps_4th_key_survived": (
            keys_goal_survival_steps_sum / keys_goal_survival_steps_count
        ) if keys_goal_survival_steps_count else 0.0,
        "keys_goal_lost_with_minus5_with_keys_events": keys_goal_lost_with_minus5_with_keys_events,
        "keys_goal_lost_with_minus5_with_keys_share": (
            keys_goal_lost_with_minus5_with_keys_events / keys_goal_lost_events
        ) if keys_goal_lost_events else 0.0,
        "avg_carriers_when_4th_key_reached": (
            keys_goal_carriers_at_reach_sum / keys_goal_carriers_at_reach_count
        ) if keys_goal_carriers_at_reach_count else 0.0,
        "avg_steps_from_4th_key_to_loss_when_lost": (
            keys_goal_steps_to_loss_sum / keys_goal_steps_to_loss_count
        ) if keys_goal_steps_to_loss_count else 0.0,
        "avg_team_distance_to_umbral_at_end_after_4th_key": (
            keys_goal_end_team_distance_sum / keys_goal_end_team_distance_count
        ) if keys_goal_end_team_distance_count else 0.0,
        "avg_team_distance_to_umbral_at_end_after_4th_key_nonwin": (
            keys_goal_end_team_distance_nonwin_sum / keys_goal_end_team_distance_nonwin_count
        ) if keys_goal_end_team_distance_nonwin_count else 0.0,
        "keys_goal_nonwin_with_keys_without_umbral_events": keys_goal_nonwin_with_keys_without_umbral_events,
        "keys_goal_nonwin_with_keys_without_umbral_rate_given_reached": (
            keys_goal_nonwin_with_keys_without_umbral_events / reached_keys_goal_episodes
        ) if reached_keys_goal_episodes else 0.0,
        "keys_goal_source_counts": dict(keys_goal_source_counter),
        "keys_goal_carrier_counts": dict(keys_goal_carrier_counter),
        "keys_goal_loss_action_counts": dict(keys_goal_loss_action_counter),
        "keys_goal_loss_reason_counts": dict(keys_goal_loss_reason_counter),
        "keys_goal_lost_carrier_counts": dict(keys_goal_lost_carrier_counter),
        "keys_goal_post_reach_reason_counts": dict(keys_goal_post_reach_reason_counter),
        "keys_goal_terminal_outcome_counts": dict(keys_goal_terminal_outcome_counter),
        "rate_all_near_umbral": (all_near_umbral_episodes / episodes) if episodes else 0.0,
        "predicted_legal_rate": (predicted_legal_type_steps / player_steps) if player_steps else 0.0,
        "requested_executed_match_rate": (requested_matched_executed_steps / player_steps) if player_steps else 0.0,
        "invalid_intent_rate": (invalid_intent_steps / player_steps) if player_steps else 0.0,
        "masked_out_rate": (masked_out_steps / player_steps) if player_steps else 0.0,
        "fallback_substitution_rate": (fallback_substitution_steps / player_steps) if player_steps else 0.0,
        "peek_available_steps": peek_available_steps,
        "pred_peek_rate_when_available": (pred_peek_when_available / peek_available_steps) if peek_available_steps else 0.0,
        "pred_skip_rate_when_available": (pred_skip_when_available / peek_available_steps) if peek_available_steps else 0.0,
        "exec_peek_rate_when_available": (exec_peek_when_available / peek_available_steps) if peek_available_steps else 0.0,
        "exec_skip_rate_when_available": (exec_skip_when_available / peek_available_steps) if peek_available_steps else 0.0,
        "fallback_rate": (fallback_steps / player_steps) if player_steps else 0.0,
        "effective_peek_rate_over_total": (effective_peek_steps / total_steps) if total_steps else 0.0,
        "effective_peek_steps": effective_peek_steps,
        "effective_search_steps": effective_search_steps,
        "usage_events_total": usage_events_total,
        "usage_events_cross": usage_events_cross,
        "usage_cross_ratio": (usage_events_cross / usage_events_total) if usage_events_total else 0.0,
        "resolved_events_total": resolved_events_total,
        "resolved_events_cross": resolved_events_cross,
        "resolved_cross_ratio": (resolved_events_cross / resolved_events_total) if resolved_events_total else 0.0,
        "minus5_losses": minus5_losses,
        "minus5_rate": (minus5_losses / episodes) if episodes else 0.0,
        "minus5_entry_events": minus5_entry_events,
        "minus5_entry_with_keys_events": minus5_entry_with_keys_events,
        "minus5_entry_with_keys_rate": (
            minus5_entry_with_keys_events / minus5_entry_events
        ) if minus5_entry_events else 0.0,
        "sacrifice_action_steps": sacrifice_action_steps,
        "accept_sacrifice_action_steps": accept_sacrifice_action_steps,
        "sacrifice_vs_accept_ratio": (
            sacrifice_action_steps / accept_sacrifice_action_steps
        ) if accept_sacrifice_action_steps else float(sacrifice_action_steps),
        "key_destroyed_losses": key_destroyed_losses,
        "key_destroyed_rate": (key_destroyed_losses / episodes) if episodes else 0.0,
        "action_source_counts": dict(action_source_counter),
    }

    for milestone in key_milestones:
        hit_count = milestone_hits[milestone]
        metrics[f"rate_reached_{milestone}_keys"] = (hit_count / episodes) if episodes else 0.0
        metrics[f"avg_step_to_{milestone}_keys_when_reached"] = (
            milestone_step_sums[milestone] / hit_count
        ) if hit_count else 0.0

    metrics["time_to_first_key_avg"] = metrics.get("avg_step_to_1_keys_when_reached", 0.0)
    metrics["time_to_keys_goal_avg"] = metrics.get(f"avg_step_to_{keys_goal}_keys_when_reached", 0.0)

    _compute_score(metrics, args)
    return metrics


def _parse_json_dict(raw: str | None) -> Dict[str, Any]:
    if raw is None or raw.strip() == "":
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("El valor debe ser un JSON object")
    return data


def _make_env_factory(seed: int, rank: int, env_kwargs: Dict[str, Any]):
    def _init():
        return CarcosaEnv(seed=seed + rank, **env_kwargs)

    return _init


def _configure_policy_gradient_after_load(model, args: argparse.Namespace) -> None:
    model.learning_rate = args.learning_rate
    model.lr_schedule = lambda _: args.learning_rate
    model.ent_coef = args.ent_coef
    model.clip_range = lambda _: args.clip_range

    target_n_steps = args.ppo_n_steps
    if target_n_steps is not None and target_n_steps != model.n_steps:
        if target_n_steps <= 1:
            raise ValueError("--ppo-n-steps debe ser > 1")
        model.n_steps = target_n_steps
        rollout_buffer_class = getattr(model, "rollout_buffer_class", RolloutBuffer)
        model.rollout_buffer = rollout_buffer_class(
            buffer_size=model.n_steps,
            observation_space=model.observation_space,
            action_space=model.action_space,
            device=model.device,
            gae_lambda=model.gae_lambda,
            gamma=model.gamma,
            n_envs=model.n_envs,
        )


def run_adaptive_finetune(args: argparse.Namespace) -> Dict[str, Any]:
    if not HAS_SB3:
        raise RuntimeError("stable-baselines3 no está disponible")

    args.algorithm = _normalize_algorithm_name(getattr(args, "algorithm", "ppo"))
    args.selector_profile = str(getattr(args, "selector_profile", "default")).strip().lower()
    if args.selector_profile not in {"default", "funnel", "funnel_k4"}:
        raise ValueError("--selector-profile debe ser 'default', 'funnel' o 'funnel_k4'")

    if args.algorithm == "maskable_ppo" and not HAS_SB3_CONTRIB:
        raise RuntimeError(
            "--algorithm maskable_ppo requiere sb3-contrib. "
            "Instalar con: pip install sb3-contrib"
        )

    base_model = Path(args.base_model)
    if not base_model.exists():
        raise FileNotFoundError(f"Base model no existe: {base_model}")

    if args.chunk_timesteps <= 0:
        raise ValueError("--chunk-timesteps debe ser > 0")
    if args.total_timesteps <= 0:
        raise ValueError("--total-timesteps debe ser > 0")

    env_kwargs = _parse_json_dict(args.env_overrides)
    eval_env_kwargs = _parse_json_dict(args.eval_env_overrides) if args.eval_env_overrides else dict(env_kwargs)

    if "curriculum_closing_prob" not in env_kwargs:
        env_kwargs["curriculum_closing_prob"] = args.curriculum_closing_prob
    if "curriculum_keys34_prob" not in env_kwargs:
        env_kwargs["curriculum_keys34_prob"] = args.curriculum_keys34_prob
    if "curriculum_keys_start" not in env_kwargs:
        env_kwargs["curriculum_keys_start"] = args.curriculum_keys_start
    if "curriculum_far_player_prob" not in env_kwargs:
        env_kwargs["curriculum_far_player_prob"] = args.curriculum_far_player_prob
    if "curriculum_keys34_min_keys" not in env_kwargs:
        env_kwargs["curriculum_keys34_min_keys"] = args.curriculum_keys34_min_keys
    if "curriculum_keys34_max_keys" not in env_kwargs:
        env_kwargs["curriculum_keys34_max_keys"] = args.curriculum_keys34_max_keys
    if "curriculum_keys34_fragile_sanity_min" not in env_kwargs:
        env_kwargs["curriculum_keys34_fragile_sanity_min"] = args.curriculum_keys34_fragile_sanity_min
    if "curriculum_keys34_fragile_sanity_max" not in env_kwargs:
        env_kwargs["curriculum_keys34_fragile_sanity_max"] = args.curriculum_keys34_fragile_sanity_max
    if "curriculum_keys34_fragile_carriers" not in env_kwargs:
        env_kwargs["curriculum_keys34_fragile_carriers"] = args.curriculum_keys34_fragile_carriers

    if "curriculum_closing_prob" not in eval_env_kwargs:
        eval_env_kwargs["curriculum_closing_prob"] = args.curriculum_eval_closing_prob
    if "curriculum_keys34_prob" not in eval_env_kwargs:
        eval_env_kwargs["curriculum_keys34_prob"] = args.curriculum_eval_keys34_prob

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"adaptive_{timestamp}"

    save_root = Path(args.save_dir) / run_name
    log_root = Path(args.log_dir) / run_name
    candidates_dir = save_root / "candidates"
    accepted_dir = save_root / "accepted"
    save_root.mkdir(parents=True, exist_ok=True)
    candidates_dir.mkdir(parents=True, exist_ok=True)
    accepted_dir.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("ADAPTIVE FINE-TUNE (selección cada chunk)")
    print(f"Algorithm: {args.algorithm}")
    print(f"Selector profile: {args.selector_profile}")
    print(f"Base model: {base_model}")
    print(f"Total timesteps: {args.total_timesteps}")
    print(f"Chunk timesteps: {args.chunk_timesteps}")
    print(f"N envs: {args.n_envs}")
    print(f"Seed: {args.seed}")
    print(f"Env kwargs: {env_kwargs}")
    print(f"Eval env kwargs: {eval_env_kwargs}")
    print(
        f"Curriculum focus keys34: {args.curriculum_auto_focus_keys34} "
        f"(threshold rate4={args.curriculum_focus_threshold_rate4:.3f})"
    )
    print(f"Save root: {save_root}")
    print(f"Log root: {log_root}")
    print("=" * 80)

    current_best_path = str(base_model)
    incumbent = evaluate_model(
        model_path=current_best_path,
        episodes=args.eval_episodes,
        seed_base=args.eval_seed_base,
        env_kwargs=eval_env_kwargs,
        args=args,
    )

    print(
        f"[INIT] score={incumbent['score']:.4f} | win_rate={incumbent['win_rate']:.3f} "
        f"| k3={incumbent.get('rate_reached_3_keys', 0.0):.3f} "
        f"| k4={incumbent.get('rate_reached_4_keys', incumbent['rate_reached_keys_goal']):.3f} "
        f"| m5k={incumbent.get('minus5_entry_with_keys_rate', 0.0):.3f} "
        f"| win@keys={incumbent['win_given_reached_keys_goal']:.3f} "
        f"| keys_goal={incumbent['rate_reached_keys_goal']:.3f} "
        f"| near_umbral={incumbent['rate_all_near_umbral']:.3f} "
        f"| match={incumbent['requested_executed_match_rate']:.3f} "
        f"| fallback_sub={incumbent['fallback_substitution_rate']:.3f} "
        f"| avg_reward={incumbent['avg_reward']:.2f} "
        f"| minus5={incumbent['minus5_rate']:.3f}"
    )

    shutil.copy2(current_best_path, accepted_dir / "best_chunk_000.zip")

    history = [
        {
            "chunk": 0,
            "trained_timesteps": 0,
            "accepted": True,
            "selected_model": str(Path(accepted_dir / "best_chunk_000.zip")),
            "candidate_model": current_best_path,
            "metrics": incumbent,
        }
    ]

    remaining = args.total_timesteps
    chunk_index = 0

    while remaining > 0:
        chunk_index += 1
        chunk_steps = min(args.chunk_timesteps, remaining)

        chunk_seed = args.seed + chunk_index * args.chunk_seed_stride
        train_env_kwargs = dict(env_kwargs)
        curriculum_mode = "baseline"
        incumbent_rate4 = float(incumbent.get("rate_reached_4_keys", incumbent.get("rate_reached_keys_goal", 0.0)))
        if args.curriculum_auto_focus_keys34 and incumbent_rate4 < args.curriculum_focus_threshold_rate4:
            train_env_kwargs["curriculum_closing_prob"] = args.curriculum_closing_prob_below_threshold
            train_env_kwargs["curriculum_keys34_prob"] = max(
                float(train_env_kwargs.get("curriculum_keys34_prob", 0.0)),
                args.curriculum_keys34_prob_focus,
            )
            curriculum_mode = "keys34_focus"

        train_env = DummyVecEnv([
            _make_env_factory(chunk_seed, i, train_env_kwargs)
            for i in range(args.n_envs)
        ])

        model = _load_training_model(
            model_path=current_best_path,
            env=train_env,
            tensorboard_log=str(log_root),
            args=args,
        )
        _configure_policy_gradient_after_load(model, args)
        model.set_random_seed(chunk_seed)

        model.learn(
            total_timesteps=chunk_steps,
            reset_num_timesteps=False,
            progress_bar=args.progress,
        )

        candidate_stem = candidates_dir / f"chunk_{chunk_index:03d}"
        model.save(str(candidate_stem))
        candidate_path = f"{candidate_stem}.zip"
        del model
        train_env.close()

        candidate_metrics = evaluate_model(
            model_path=candidate_path,
            episodes=args.eval_episodes,
            seed_base=args.eval_seed_base,
            env_kwargs=eval_env_kwargs,
            args=args,
        )

        score_improvement = candidate_metrics["score"] - incumbent["score"]
        accepted, decision_metric, decision_delta = compare_metrics_lexicographic(
            candidate_metrics=candidate_metrics,
            incumbent_metrics=incumbent,
            args=args,
        )

        if accepted:
            current_best_path = candidate_path
            incumbent = candidate_metrics
            selected_copy = accepted_dir / f"best_chunk_{chunk_index:03d}.zip"
            shutil.copy2(candidate_path, selected_copy)
            selected_model = str(selected_copy)
        else:
            selected_model = current_best_path

        history.append(
            {
                "chunk": chunk_index,
                "trained_timesteps": int(chunk_steps),
                "accepted": accepted,
                "score_improvement": score_improvement,
                "decision_metric": decision_metric,
                "decision_delta": decision_delta,
                "selected_model": selected_model,
                "candidate_model": candidate_path,
                "curriculum_mode": curriculum_mode,
                "train_env_kwargs": train_env_kwargs,
                "candidate_metrics": candidate_metrics,
                "incumbent_metrics": incumbent,
            }
        )

        print(
            f"[CHUNK {chunk_index:03d}] steps={chunk_steps} | "
            f"seed={chunk_seed} | "
            f"cand_score={candidate_metrics['score']:.4f} | "
            f"inc_score={incumbent['score']:.4f} | "
            f"score_delta={score_improvement:+.4f} | "
            f"decision={decision_metric}({decision_delta:+.4f}) | "
            f"mode={curriculum_mode} | "
            f"cand_k3={candidate_metrics.get('rate_reached_3_keys', 0.0):.3f} | "
            f"cand_k4={candidate_metrics.get('rate_reached_4_keys', candidate_metrics['rate_reached_keys_goal']):.3f} | "
            f"cand_m5k={candidate_metrics.get('minus5_entry_with_keys_rate', 0.0):.3f} | "
            f"cand_win@keys={candidate_metrics['win_given_reached_keys_goal']:.3f} | "
            f"cand_match={candidate_metrics['requested_executed_match_rate']:.3f} | "
            f"cand_fallback_sub={candidate_metrics['fallback_substitution_rate']:.3f} | "
            f"cand_minus5={candidate_metrics['minus5_rate']:.3f} | accepted={accepted}"
        )

        remaining -= chunk_steps

    final_selected = save_root / "best_model_selected.zip"
    shutil.copy2(current_best_path, final_selected)

    summary = {
        "run_name": run_name,
        "algorithm": args.algorithm,
        "selector_profile": args.selector_profile,
        "base_model": str(base_model),
        "final_selected_model": str(final_selected),
        "total_timesteps_requested": args.total_timesteps,
        "chunk_timesteps": args.chunk_timesteps,
        "eval_episodes": args.eval_episodes,
        "accepted_chunks": sum(1 for row in history[1:] if row.get("accepted")),
        "history": history,
        "final_metrics": incumbent,
        "weights": {
            "win_rate": args.weight_win_rate,
            "reward": args.weight_reward,
            "cross_info": args.weight_cross_info,
            "minus5_penalty": args.weight_minus5_penalty,
        },
        "selector": {
            "type": "lexicographic",
            "profile": args.selector_profile,
            "order": _selector_order_labels(args),
            "lex_eps_rate": args.lex_eps_rate,
            "lex_eps_reward": args.lex_eps_reward,
            "min_match_rate": args.min_match_rate,
            "max_fallback_substitution_rate": args.max_fallback_substitution_rate,
            "max_minus5_with_keys_rate": args.max_minus5_with_keys_rate,
        },
        "reward_normalization": {
            "floor": args.reward_floor,
            "ceiling": args.reward_ceiling,
        },
        "curriculum": {
            "closing_prob_train": args.curriculum_closing_prob,
            "keys34_prob_train": args.curriculum_keys34_prob,
            "keys34_prob_focus": args.curriculum_keys34_prob_focus,
            "keys_start": args.curriculum_keys_start,
            "far_player_prob": args.curriculum_far_player_prob,
            "closing_prob_eval": args.curriculum_eval_closing_prob,
            "keys34_prob_eval": args.curriculum_eval_keys34_prob,
            "auto_focus_keys34": args.curriculum_auto_focus_keys34,
            "focus_threshold_rate4": args.curriculum_focus_threshold_rate4,
            "closing_prob_below_threshold": args.curriculum_closing_prob_below_threshold,
        },
        "env_kwargs": env_kwargs,
        "eval_env_kwargs": eval_env_kwargs,
    }

    summary_path = save_root / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    history_path = save_root / "history.jsonl"
    with history_path.open("w", encoding="utf-8") as f:
        for row in history:
            f.write(json.dumps(row) + "\n")

    print("\n" + "=" * 80)
    print("Adaptive fine-tune completado")
    print(f"Final selected model: {final_selected}")
    print(
        f"Final score={incumbent['score']:.4f} | win_rate={incumbent['win_rate']:.3f} "
        f"| k3={incumbent.get('rate_reached_3_keys', 0.0):.3f} "
        f"| k4={incumbent.get('rate_reached_4_keys', incumbent['rate_reached_keys_goal']):.3f} "
        f"| m5k={incumbent.get('minus5_entry_with_keys_rate', 0.0):.3f} "
        f"| win@keys={incumbent['win_given_reached_keys_goal']:.3f} "
        f"| keys_goal={incumbent['rate_reached_keys_goal']:.3f} "
        f"| near_umbral={incumbent['rate_all_near_umbral']:.3f} "
        f"| match={incumbent['requested_executed_match_rate']:.3f} "
        f"| fallback_sub={incumbent['fallback_substitution_rate']:.3f} "
        f"| avg_reward={incumbent['avg_reward']:.2f} "
        f"| minus5={incumbent['minus5_rate']:.3f}"
    )
    print(f"Resumen: {summary_path}")
    print("=" * 80)

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fine-tuning adaptativo para CARCOSA")
    parser.add_argument(
        "--algorithm",
        type=str,
        default="ppo",
        choices=["ppo", "maskable_ppo"],
        help="Algoritmo base para cargar/entrenar.",
    )
    parser.add_argument(
        "--selector-profile",
        type=str,
        default="funnel",
        choices=["default", "funnel", "funnel_k4"],
        help="Perfil del selector lexicográfico (default, funnel o funnel_k4).",
    )
    parser.add_argument("--base-model", type=str, required=True, help="Modelo inicial (.zip)")
    parser.add_argument("--total-timesteps", type=int, default=50_000)
    parser.add_argument("--chunk-timesteps", type=int, default=5_000)
    parser.add_argument("--n-envs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=72)
    parser.add_argument(
        "--chunk-seed-stride",
        type=int,
        default=997,
        help="Incremento de seed por chunk para evitar candidatos idénticos.",
    )
    parser.add_argument("--eval-seed-base", type=int, default=9000)
    parser.add_argument("--eval-episodes", type=int, default=30)

    parser.add_argument("--learning-rate", type=float, default=4e-5)
    parser.add_argument("--ent-coef", type=float, default=0.004)
    parser.add_argument("--clip-range", type=float, default=0.12)
    parser.add_argument(
        "--ppo-n-steps",
        type=int,
        default=None,
        help="n_steps de PPO. Si no se indica y chunk es divisible por n_envs, usa chunk/n_envs.",
    )

    parser.add_argument("--save-dir", type=str, default="models/rl_adaptive_select")
    parser.add_argument("--log-dir", type=str, default="runs/rl_training_adaptive_select")

    parser.add_argument("--env-overrides", type=str, default="{}", help="JSON con kwargs para CarcosaEnv en train")
    parser.add_argument(
        "--eval-env-overrides",
        type=str,
        default="",
        help="JSON con kwargs para evaluación. Si vacío, usa env-overrides.",
    )
    parser.add_argument(
        "--curriculum-closing-prob",
        type=float,
        default=0.0,
        help="Probabilidad de reset en escenario de cierre (solo entrenamiento).",
    )
    parser.add_argument(
        "--curriculum-keys34-prob",
        type=float,
        default=0.0,
        help="Probabilidad de reset en escenario 2->3->4 llaves (solo entrenamiento).",
    )
    parser.add_argument(
        "--curriculum-keys34-prob-focus",
        type=float,
        default=0.35,
        help="Probabilidad objetivo de curriculum keys34 durante modo foco (< umbral rate4).",
    )
    parser.add_argument(
        "--curriculum-keys34-min-keys",
        type=int,
        default=2,
        help="Llaves mínimas iniciales en curriculum keys34.",
    )
    parser.add_argument(
        "--curriculum-keys34-max-keys",
        type=int,
        default=3,
        help="Llaves máximas iniciales en curriculum keys34.",
    )
    parser.add_argument(
        "--curriculum-keys34-fragile-sanity-min",
        type=int,
        default=-4,
        help="Sanity mínima para portadores frágiles en curriculum keys34.",
    )
    parser.add_argument(
        "--curriculum-keys34-fragile-sanity-max",
        type=int,
        default=-2,
        help="Sanity máxima para portadores frágiles en curriculum keys34.",
    )
    parser.add_argument(
        "--curriculum-keys34-fragile-carriers",
        type=int,
        default=2,
        help="Cantidad de portadores frágiles en curriculum keys34.",
    )
    parser.add_argument(
        "--curriculum-keys-start",
        type=int,
        default=4,
        help="Llaves iniciales en el escenario de curriculum de cierre.",
    )
    parser.add_argument(
        "--curriculum-far-player-prob",
        type=float,
        default=0.8,
        help="Probabilidad de dejar 1 jugador lejos del Umbral en curriculum de cierre.",
    )
    parser.add_argument(
        "--curriculum-eval-closing-prob",
        type=float,
        default=0.0,
        help="Probabilidad de curriculum de cierre en evaluación (recomendado 0.0).",
    )
    parser.add_argument(
        "--curriculum-eval-keys34-prob",
        type=float,
        default=0.0,
        help="Probabilidad de curriculum keys34 en evaluación (recomendado 0.0).",
    )
    parser.add_argument(
        "--curriculum-auto-focus-keys34",
        action="store_true",
        help="Si rate_reached_4_keys es bajo, reduce cierre y prioriza curriculum keys34.",
    )
    parser.add_argument(
        "--curriculum-focus-threshold-rate4",
        type=float,
        default=0.10,
        help="Umbral de rate_reached_4_keys para salir del modo foco keys34.",
    )
    parser.add_argument(
        "--curriculum-closing-prob-below-threshold",
        type=float,
        default=0.0,
        help="Probabilidad de curriculum de cierre mientras rate4 < umbral.",
    )

    parser.add_argument("--weight-win-rate", type=float, default=0.60)
    parser.add_argument("--weight-reward", type=float, default=0.30)
    parser.add_argument("--weight-cross-info", type=float, default=0.05)
    parser.add_argument("--weight-minus5-penalty", type=float, default=0.10)
    parser.add_argument("--lex-eps-rate", type=float, default=0.01)
    parser.add_argument("--lex-eps-reward", type=float, default=0.5)
    parser.add_argument(
        "--min-match-rate",
        type=float,
        default=0.85,
        help="Gate duro: requested_executed_match_rate mínimo para aceptar un candidato.",
    )
    parser.add_argument(
        "--max-fallback-substitution-rate",
        type=float,
        default=0.15,
        help="Gate duro: fallback_substitution_rate máximo para aceptar un candidato.",
    )
    parser.add_argument(
        "--max-minus5-with-keys-rate",
        type=float,
        default=1.0,
        help="Gate de riesgo: máximo permitido para minus5_entry_with_keys_rate.",
    )
    parser.add_argument("--reward-floor", type=float, default=-25.0)
    parser.add_argument("--reward-ceiling", type=float, default=5.0)
    parser.add_argument("--min-improvement", type=float, default=1e-4)

    parser.add_argument("--progress", action="store_true", help="Mostrar barra de progreso en cada chunk")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.curriculum_keys34_max_keys < args.curriculum_keys34_min_keys:
        raise ValueError("--curriculum-keys34-max-keys debe ser >= --curriculum-keys34-min-keys")
    if args.curriculum_keys34_fragile_sanity_max < args.curriculum_keys34_fragile_sanity_min:
        raise ValueError(
            "--curriculum-keys34-fragile-sanity-max debe ser >= --curriculum-keys34-fragile-sanity-min"
        )
    if args.max_minus5_with_keys_rate < 0:
        raise ValueError("--max-minus5-with-keys-rate debe ser >= 0")

    if args.ppo_n_steps is None:
        if args.chunk_timesteps % args.n_envs == 0:
            args.ppo_n_steps = args.chunk_timesteps // args.n_envs
        else:
            args.ppo_n_steps = 2048
            print(
                "WARNING: chunk_timesteps no divisible por n_envs; "
                "se mantiene n_steps=2048 y SB3 puede sobrepasar el chunk solicitado."
            )

    weight_sum = (
        args.weight_win_rate
        + args.weight_reward
        + args.weight_cross_info
        + args.weight_minus5_penalty
    )
    if weight_sum <= 0:
        raise ValueError("La suma de weights debe ser > 0")

    args.weight_win_rate = args.weight_win_rate / weight_sum
    args.weight_reward = args.weight_reward / weight_sum
    args.weight_cross_info = args.weight_cross_info / weight_sum
    args.weight_minus5_penalty = args.weight_minus5_penalty / weight_sum

    run_adaptive_finetune(args)


if __name__ == "__main__":
    main()

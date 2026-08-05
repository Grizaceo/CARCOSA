"""
Métricas diagnósticas estilo Pezza para CARCOSA
================================================

Inspirado en las métricas del video de Pezza "I made A.I Gladiators FIGHT"
(PTkHnfF5It4). Pezza medía:
  - Agresividad (daño/segundo, cercanía al enemigo)
  - Velocidad (duración del combate en victoria vs derrota)
  - Eficiencia (HP restante del ganador, recursos usados)
  - Estilo de juego (acciones ofensivas vs defensivas)
  - Diversidad (variabilidad entre seeds/stats)

Este módulo traduce esos conceptos a métricas CARCOSA para diagnosticar
qué está mal con el bot. No son reward shaping — son métricas de evaluación.

Uso:
    from train.pezza_metrics import diagnose_episode, diagnose_model
    metrics = diagnose_model("models/best.zip", seeds=range(50))
"""

from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import numpy as np
import sys
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _get_predict_params(model) -> list:
    """Devuelve los nombres de parámetros de model.predict. [] si model es None."""
    if model is None:
        return []
    try:
        sig = inspect.signature(model.predict)
        return list(sig.parameters.keys())
    except (ValueError, TypeError):
        return []


def diagnose_episode(env, model=None, seed: int = 0, max_steps: int = 2000) -> Dict[str, Any]:
    """
    Corre un episodio completo y captura métricas diagnósticas estilo Pezza.

    Args:
        env: CarcosaEnv ya configurado
        model: modelo PPO/MaskablePPO (None = random policy)
        seed: semilla del episodio
        max_steps: límite de pasos

    Returns:
        Dict con métricas diagnósticas por episodio.
    """
    obs, info = env.reset(seed=seed)

    # Tracking por episodio
    action_counts = defaultdict(int)  # tipo de acción -> count
    keys_per_round = []  # keys totales al final de cada ronda
    sanity_per_round = []  # sanity total al final de cada ronda
    umbral_distance_per_round = []  # distancia al umbral por ronda
    search_count = 0
    move_count = 0
    use_object_count = 0
    end_turn_count = 0
    key_gain_events = 0  # veces que el equipo ganó una key
    key_loss_events = 0  # veces que el equipo perdió una key
    sanction_count = 0  # sanciones recibidas (proxy de daño del King)
    peek_count = 0  # exploración de mazo

    prev_keys = sum(p.keys for p in env.state.players.values())
    prev_sanity = sum(p.sanity for p in env.state.players.values())
    prev_round = env.state.round

    done = False
    steps = 0
    final_reward = 0.0
    reward_accum = 0.0

    # Detectar si el modelo soporta action_masks (MaskablePPO vs PPO estándar)
    _supports_masks = hasattr(model, 'predict') and 'action_masks' in _get_predict_params(model)

    while not done and steps < max_steps:
        if model is not None:
            if _supports_masks:
                try:
                    action_masks = env.action_masks()
                    action, _ = model.predict(obs, action_masks=action_masks, deterministic=True)
                except Exception:
                    action, _ = model.predict(obs, deterministic=True)
            else:
                action, _ = model.predict(obs, deterministic=True)
        else:
            legal_mask = info.get("legal_actions", np.ones(env.action_space.n))
            legal_ids = np.where(legal_mask > 0)[0]
            action = np.random.choice(legal_ids) if len(legal_ids) > 0 else 0

        # Capturar tipo de acción ANTES del step
        action_type = "UNKNOWN"
        if hasattr(env, 'last_action_debug') and env.last_action_debug:
            action_type = env.last_action_debug.get("executed_action_type", "UNKNOWN") or "UNKNOWN"
        else:
            if 0 <= action < len(env.ACTION_TYPES):
                action_type = env.ACTION_TYPES[action].value
        if not action_type:
            action_type = "UNKNOWN"

        obs, reward, terminated, truncated, info = env.step(action)
        reward_accum += reward
        done = terminated or truncated
        steps += 1

        # Contabilizar acción
        action_counts[action_type] += 1
        if "SEARCH" in str(action_type):
            search_count += 1
        elif "MOVE" in str(action_type):
            move_count += 1
        elif "USE" in str(action_type) or "ACTIVATE" in str(action_type):
            use_object_count += 1
        elif "END_TURN" in str(action_type):
            end_turn_count += 1
        elif "PEEK" in str(action_type):
            peek_count += 1

        # Capturar deltas de keys/sanity
        curr_keys = sum(p.keys for p in env.state.players.values())
        curr_sanity = sum(p.sanity for p in env.state.players.values())

        if curr_keys > prev_keys:
            key_gain_events += curr_keys - prev_keys
        elif curr_keys < prev_keys:
            key_loss_events += prev_keys - curr_keys

        # Detectar cambio de ronda
        if env.state.round > prev_round:
            keys_per_round.append(curr_keys)
            sanity_per_round.append(curr_sanity)
            # Distancia al umbral (proxy de "cercanía a la meta")
            umbral_dist = _team_umbral_distance_quick(env.state)
            umbral_distance_per_round.append(umbral_dist)
            prev_round = env.state.round

        prev_keys = curr_keys
        prev_sanity = curr_sanity

    # Métricas finales
    outcome = info.get("outcome", "TIMEOUT")
    final_round = info.get("round", env.state.round)
    final_keys = sum(p.keys for p in env.state.players.values())
    final_sanity = sum(p.sanity for p in env.state.players.values())
    keys_needed = env.cfg.KEYS_TO_WIN

    # === MÉTRICAS DIAGNÓSTICAS ESTILO PEZZA ===
    metrics = {
        # --- VELOCIDAD (Pezza: duración del combate) ---
        "pezza_speed_win_round": final_round if outcome == "WIN" else None,
        "pezza_speed_lose_round": final_round if "LOSE" in str(outcome) else None,
        "pezza_speed_timeout": 1 if outcome == "TIMEOUT" or "TIMEOUT" in str(outcome) else 0,
        "pezza_steps_total": steps,

        # --- AGRESIVIDAD OFENSIVA (Pezza: daño/segundo → keys/ronda) ---
        "pezza_keys_per_round": float(final_keys) / max(1, final_round) if final_round > 0 else 0.0,
        "pezza_key_gain_events": key_gain_events,
        "pezza_key_loss_events": key_loss_events,
        "pezza_key_net": key_gain_events - key_loss_events,
        "pezza_key_progress_rate": key_gain_events / max(1, final_round),

        # --- EFFICIENCY (Pezza: HP del ganador → sanity/keys al ganar) ---
        "pezza_final_sanity": final_sanity,
        "pezza_final_keys": final_keys,
        "pezza_keys_to_win": keys_needed,
        "pezza_keys_deficit": keys_needed - final_keys,
        "pezza_efficiency_sanity_per_key": final_sanity / max(1, final_keys) if final_keys > 0 else None,

        # --- ESTILO DE JUEGO (Pezza: acciones ofensivas vs defensivas) ---
        "pezza_action_search_pct": search_count / max(1, steps) * 100,
        "pezza_action_move_pct": move_count / max(1, steps) * 100,
        "pezza_action_use_pct": use_object_count / max(1, steps) * 100,
        "pezza_action_end_turn_pct": end_turn_count / max(1, steps) * 100,
        "pezza_action_peek_pct": peek_count / max(1, steps) * 100,
        "pezza_search_to_move_ratio": search_count / max(1, move_count),

        # --- PROGRESIÓN (Pezza: trayectoria de HP → trayectoria de keys/sanity) ---
        "pezza_keys_trajectory": keys_per_round,  # lista: keys al final de cada ronda
        "pezza_sanity_trajectory": sanity_per_round,
        "pezza_umbral_trajectory": umbral_distance_per_round,
        "pezza_keys_at_round_10": keys_per_round[9] if len(keys_per_round) > 9 else None,
        "pezza_keys_at_round_20": keys_per_round[19] if len(keys_per_round) > 19 else None,
        "pezza_sanity_at_round_10": sanity_per_round[9] if len(sanity_per_round) > 9 else None,
        "pezza_rounds_to_first_key": _rounds_to_first_key(keys_per_round),

        # --- RESULTADO ---
        "outcome": outcome,
        "win": outcome == "WIN",
        "round": final_round,
        "seed": seed,
        "reward_total": reward_accum,
    }

    return metrics


def _rounds_to_first_key(keys_trajectory: List[int]) -> Optional[int]:
    """En qué ronda el equipo consiguió su primera key."""
    for i, k in enumerate(keys_trajectory):
        if k > 0:
            return i + 1
    return None


def _team_umbral_distance_quick(state) -> int:
    """Distancia mínima del equipo al Umbral (proxy de cercanía a la meta)."""
    try:
        from engine.board import neighbors
        # Distancia Manhattan aproximada al umbral más cercano
        min_dist = float('inf')
        for player in state.players.values():
            # Si no hay floor info, usar 0
            dist = 0
            try:
                from engine.board import floor_of
                p_floor = floor_of(player.room)
                # El umbral está en el piso -1 (abajo)
                dist = abs(p_floor - (-1)) + 1  # floors + 1 room
            except Exception:
                dist = 0
            min_dist = min(min_dist, dist)
        return int(min_dist) if min_dist != float('inf') else 0
    except Exception:
        return 0


def diagnose_model(
    model_path: str,
    seeds: range = range(50),
    device: str = "cpu",
    king_enabled: bool = False,
    extra_kwargs: Dict = None,
) -> Dict[str, Any]:
    """
    Evalúa un modelo sobre múltiples seeds y agrega métricas Pezza.

    Returns:
        Dict con:
        - per_episode: lista de métricas por episodio
        - aggregate: métricas promediadas/agregadas
        - pezza_diagnosis: diagnóstico textual de qué está mal
    """
    import torch
    from stable_baselines3 import PPO
    from sb3_contrib import MaskablePPO
    from train.carcosa_env import CarcosaEnv

    torch.set_num_threads(1)

    # Cargar modelo
    env_kwargs = {"king_enabled": king_enabled}
    env_kwargs["penalty_existence_per_round"] = 0.0  # métricas: sin penalty
    if extra_kwargs:
        env_kwargs.update(extra_kwargs)
    env = CarcosaEnv(**env_kwargs)

    model = None
    is_maskable = False
    if model_path and model_path != "GOAL":
        if "maskable" in model_path.lower():
            model = MaskablePPO.load(str(model_path), env=env, device=device)
            is_maskable = True
        else:
            model = PPO.load(str(model_path), env=env, device=device)

    per_episode = []
    for seed in seeds:
        if is_maskable:
            metrics = _diagnose_maskable(env, model, seed)
        else:
            metrics = diagnose_episode(env, model, seed)
        per_episode.append(metrics)

    # Agregar
    wins = [m for m in per_episode if m["win"]]
    losses = [m for m in per_episode if "LOSE" in str(m["outcome"])]
    timeouts = [m for m in per_episode if "TIMEOUT" in str(m["outcome"])]

    aggregate = {
        "n_episodes": len(per_episode),
        "win_rate": len(wins) / max(1, len(per_episode)) * 100,
        "n_wins": len(wins),
        "n_losses": len(losses),
        "n_timeouts": len(timeouts),

        # Velocidad
        "avg_win_round": np.mean([m["pezza_speed_win_round"] for m in wins if m["pezza_speed_win_round"] is not None]) if wins else None,
        "avg_lose_round": np.mean([m["pezza_speed_lose_round"] for m in losses if m["pezza_speed_lose_round"] is not None]) if losses else None,
        "timeout_rate": len(timeouts) / max(1, len(per_episode)) * 100,

        # Agresividad
        "avg_keys_per_round": np.mean([m["pezza_keys_per_round"] for m in per_episode]),
        "avg_key_gain_events": np.mean([m["pezza_key_gain_events"] for m in per_episode]),
        "avg_key_loss_events": np.mean([m["pezza_key_loss_events"] for m in per_episode]),
        "avg_key_net": np.mean([m["pezza_key_net"] for m in per_episode]),

        # Efficiency
        "avg_final_keys": np.mean([m["pezza_final_keys"] for m in per_episode]),
        "avg_keys_deficit": np.mean([m["pezza_keys_deficit"] for m in per_episode]),
        "avg_final_sanity": np.mean([m["pezza_final_sanity"] for m in per_episode]),

        # Estilo
        "avg_search_pct": np.mean([m["pezza_action_search_pct"] for m in per_episode]),
        "avg_move_pct": np.mean([m["pezza_action_move_pct"] for m in per_episode]),
        "avg_use_pct": np.mean([m["pezza_action_use_pct"] for m in per_episode]),
        "avg_end_turn_pct": np.mean([m["pezza_action_end_turn_pct"] for m in per_episode]),
        "avg_search_to_move_ratio": np.mean([m["pezza_search_to_move_ratio"] for m in per_episode]),

        # Progresión
        "avg_rounds_to_first_key": np.mean([m["pezza_rounds_to_first_key"] for m in per_episode if m["pezza_rounds_to_first_key"] is not None]) if any(m["pezza_rounds_to_first_key"] is not None for m in per_episode) else None,
        "pct_never_got_key": sum(1 for m in per_episode if m["pezza_rounds_to_first_key"] is None) / len(per_episode) * 100,
    }

    # === DIAGNÓSTICO TEXTUAL ===
    diagnosis = _generate_diagnosis(aggregate, per_episode)

    return {
        "per_episode": per_episode,
        "aggregate": aggregate,
        "diagnosis": diagnosis,
    }


def _diagnose_maskable(env, model, seed: int) -> Dict[str, Any]:
    """Wrapper para MaskablePPO con action masks."""
    obs, info = env.reset(seed=seed)

    action_counts = defaultdict(int)
    keys_per_round = []
    sanity_per_round = []
    umbral_distance_per_round = []
    search_count = 0
    move_count = 0
    use_object_count = 0
    end_turn_count = 0
    key_gain_events = 0
    key_loss_events = 0

    prev_keys = sum(p.keys for p in env.state.players.values())
    prev_sanity = sum(p.sanity for p in env.state.players.values())
    prev_round = env.state.round

    done = False
    steps = 0
    reward_accum = 0.0

    _supports_masks = 'action_masks' in _get_predict_params(model)

    while not done and steps < 2000:
        if _supports_masks:
            try:
                action_masks = env.action_masks()
                action, _ = model.predict(obs, action_masks=action_masks, deterministic=True)
            except Exception:
                action, _ = model.predict(obs, deterministic=True)
        else:
            action, _ = model.predict(obs, deterministic=True)

        obs, reward, terminated, truncated, info = env.step(action)
        reward_accum += reward
        done = terminated or truncated
        steps += 1

        action_type = "UNKNOWN"
        if hasattr(env, 'last_action_debug') and env.last_action_debug:
            action_type = env.last_action_debug.get("executed_action_type", "UNKNOWN") or "UNKNOWN"
        elif 0 <= action < len(env.ACTION_TYPES):
            action_type = env.ACTION_TYPES[action].value

        action_counts[action_type] += 1
        if "SEARCH" in str(action_type):
            search_count += 1
        elif "MOVE" in str(action_type):
            move_count += 1
        elif "USE" in str(action_type) or "ACTIVATE" in str(action_type):
            use_object_count += 1
        elif "END_TURN" in str(action_type):
            end_turn_count += 1

        curr_keys = sum(p.keys for p in env.state.players.values())
        curr_sanity = sum(p.sanity for p in env.state.players.values())

        if curr_keys > prev_keys:
            key_gain_events += curr_keys - prev_keys
        elif curr_keys < prev_keys:
            key_loss_events += prev_keys - curr_keys

        if env.state.round > prev_round:
            keys_per_round.append(curr_keys)
            sanity_per_round.append(curr_sanity)
            umbral_distance_per_round.append(_team_umbral_distance_quick(env.state))
            prev_round = env.state.round

        prev_keys = curr_keys
        prev_sanity = curr_sanity

    outcome = info.get("outcome", "TIMEOUT")
    final_round = info.get("round", env.state.round)
    final_keys = sum(p.keys for p in env.state.players.values())
    final_sanity = sum(p.sanity for p in env.state.players.values())
    keys_needed = env.cfg.KEYS_TO_WIN

    return {
        "pezza_speed_win_round": final_round if outcome == "WIN" else None,
        "pezza_speed_lose_round": final_round if "LOSE" in str(outcome) else None,
        "pezza_speed_timeout": 1 if "TIMEOUT" in str(outcome) else 0,
        "pezza_steps_total": steps,
        "pezza_keys_per_round": float(final_keys) / max(1, final_round) if final_round > 0 else 0.0,
        "pezza_key_gain_events": key_gain_events,
        "pezza_key_loss_events": key_loss_events,
        "pezza_key_net": key_gain_events - key_loss_events,
        "pezza_final_sanity": final_sanity,
        "pezza_final_keys": final_keys,
        "pezza_keys_to_win": keys_needed,
        "pezza_keys_deficit": keys_needed - final_keys,
        "pezza_action_search_pct": search_count / max(1, steps) * 100,
        "pezza_action_move_pct": move_count / max(1, steps) * 100,
        "pezza_action_use_pct": use_object_count / max(1, steps) * 100,
        "pezza_action_end_turn_pct": end_turn_count / max(1, steps) * 100,
        "pezza_search_to_move_ratio": search_count / max(1, move_count),
        "pezza_keys_trajectory": keys_per_round,
        "pezza_sanity_trajectory": sanity_per_round,
        "pezza_umbral_trajectory": umbral_distance_per_round,
        "pezza_rounds_to_first_key": _rounds_to_first_key(keys_per_round),
        "outcome": outcome,
        "win": outcome == "WIN",
        "round": final_round,
        "seed": seed,
        "reward_total": reward_accum,
    }


def _generate_diagnosis(agg: Dict, episodes: List[Dict]) -> str:
    """Genera un diagnóstico textual de qué está mal con el bot."""
    lines = []
    lines.append("=" * 60)
    lines.append("DIAGNÓSTICO PEZZA — ¿QUÉ ESTÁ MAL CON EL BOT?")
    lines.append("=" * 60)

    # 1. VELOCIDAD
    lines.append("")
    lines.append("1. VELOCIDAD (Pezza: duración del combate)")
    if agg["avg_win_round"] is not None:
        lines.append(f"   Victorias en promedio: ronda {agg['avg_win_round']:.1f}")
    else:
        lines.append("   SIN victorias — no se puede medir velocidad de cierre")
    if agg["avg_lose_round"] is not None:
        lines.append(f"   Derrotas en promedio: ronda {agg['avg_lose_round']:.1f}")
        if agg["avg_win_round"] is not None:
            ratio = agg["avg_lose_round"] / agg["avg_win_round"]
            lines.append(f"   Ratio derrota/victoria: {ratio:.2f}x (>1.5 = el bot pierde lento, gana lento)")

    # 2. AGRESIVIDAD
    lines.append("")
    lines.append("2. AGRESIVIDAD OFENSIVA (Pezza: daño/seg → keys/ronda)")
    lines.append(f"   Keys/ronda promedio: {agg['avg_keys_per_round']:.3f}")
    lines.append(f"   Eventos de ganar keys: {agg['avg_key_gain_events']:.1f}/episodio")
    lines.append(f"   Eventos de perder keys: {agg['avg_key_loss_events']:.1f}/episodio")
    lines.append(f"   Net de keys: {agg['avg_key_net']:.1f}/episodio")
    if agg['avg_key_loss_events'] > agg['avg_key_gain_events']:
        lines.append("   ⚠ PIERDE MÁS KEYS DE LAS QUE GANA — el bot es reactivo, no ofensivo")
    if agg['avg_keys_per_round'] < 0.3:
        lines.append("   ⚠ Keys/ronda < 0.3 — el bot apenas busca keys (falta de agresividad)")

    # 3. EFFICIENCY
    lines.append("")
    lines.append("3. EFFICIENCY (Pezza: HP del ganador → keys/sanity al final)")
    lines.append(f"   Keys finales promedio: {agg['avg_final_keys']:.1f}/{agg.get('pezza_keys_to_win', 4)}")
    lines.append(f"   Deficit de keys: {agg['avg_keys_deficit']:.1f}")
    lines.append(f"   Sanity final promedio: {agg['avg_final_sanity']:.1f}")
    if agg['avg_keys_deficit'] > 2:
        lines.append("   ⚠ DEFICIT > 2 keys — el bot no llega ni cerca de la meta")

    # 4. ESTILO
    lines.append("")
    lines.append("4. ESTILO DE JUEGO (Pezza: ofensivo vs defensivo)")
    lines.append(f"   SEARCH: {agg['avg_search_pct']:.1f}%  MOVE: {agg['avg_move_pct']:.1f}%  USE: {agg['avg_use_pct']:.1f}%  END_TURN: {agg['avg_end_turn_pct']:.1f}%")
    lines.append(f"   Ratio SEARCH/MOVE: {agg['avg_search_to_move_ratio']:.2f}")
    if agg['avg_end_turn_pct'] > 40:
        lines.append("   ⚠ END_TURN > 40% — el bot pasa demasiado (no toma iniciativa)")
    if agg['avg_search_pct'] < 20:
        lines.append("   ⚠ SEARCH < 20% — el bot no explora lo suficiente para encontrar keys")
    if agg['avg_use_pct'] < 5:
        lines.append("   ⚠ USE < 5% — el bot casi no usa objetos (puede estar ignorando recursos)")

    # 5. PROGRESIÓN
    lines.append("")
    lines.append("5. PROGRESIÓN (Pezza: trayectoria de HP → trayectoria de keys)")
    if agg['avg_rounds_to_first_key'] is not None:
        lines.append(f"   Rondas promedio a primera key: {agg['avg_rounds_to_first_key']:.1f}")
    else:
        lines.append("   NUNCA consigue keys en ningún episodio")
    lines.append(f"   % episodios que NUNCA consiguieron key: {agg['pct_never_got_key']:.1f}%")
    if agg['pct_never_got_key'] > 50:
        lines.append("   ⚠ >50% de episodios sin NINGUNA key — el bot no tiene dirección ofensiva")

    # 6. TIMEOUTS
    lines.append("")
    lines.append("6. TIMEOUTS (Pezza: got stuck → nuestro: stall sin game_over)")
    lines.append(f"   Rate de timeout: {agg['timeout_rate']:.1f}%")
    if agg['timeout_rate'] > 20:
        lines.append("   ⚠ >20% timeouts — el bot se queda dando vueltas sin progresar")

    # VEREDICTO
    lines.append("")
    lines.append("=" * 60)
    lines.append("VEREDICTO")
    lines.append("=" * 60)
    problems = []
    if agg['avg_keys_per_round'] < 0.3:
        problems.append("falta agresividad ofensiva (keys/ronda baja)")
    if agg['avg_key_loss_events'] > agg['avg_key_gain_events']:
        problems.append("pierde más keys de las que gana")
    if agg['avg_keys_deficit'] > 2:
        problems.append("no llega cerca de la meta de keys")
    if agg['avg_end_turn_pct'] > 40:
        problems.append("demasiado pasivo (END_TURN alto)")
    if agg['avg_search_pct'] < 20:
        problems.append("no explora lo suficiente")
    if agg['pct_never_got_key'] > 50:
        problems.append("sin dirección ofensiva")
    if agg['timeout_rate'] > 20:
        problems.append("se queda stuck (timeouts)")

    if problems:
        lines.append("Problemas detectados:")
        for p in problems:
            lines.append(f"  • {p}")
    else:
        lines.append("No se detectaron problemas obvios — el bot juega bien pero no gana (¿problema de suerte/setup?)")

    lines.append("")
    return "\n".join(lines)


def diagnose_goal(seeds: range = range(50)) -> Dict[str, Any]:
    """Diagnostica el policy GOAL (heurístico) para tener baseline."""
    from sim.runner import run_episode
    from train.carcosa_env import CarcosaEnv

    per_episode = []
    for seed in seeds:
        st = run_episode(max_steps=2000, seed=seed, policy_name="GOAL")
        final_keys = sum(p.keys for p in st.players.values())
        final_sanity = sum(p.sanity for p in st.players.values())
        per_episode.append({
            "pezza_speed_win_round": st.round if st.outcome == "WIN" else None,
            "pezza_speed_lose_round": st.round if st.outcome != "WIN" else None,
            "pezza_speed_timeout": 1 if "TIMEOUT" in str(st.outcome) else 0,
            "pezza_keys_per_round": float(final_keys) / max(1, st.round),
            "pezza_final_keys": final_keys,
            "pezza_keys_deficit": st.config.KEYS_TO_WIN if hasattr(st, 'config') else 4 - final_keys,
            "pezza_final_sanity": final_sanity,
            "pezza_key_gain_events": 0,  # GOAL no trackea esto
            "pezza_key_loss_events": 0,
            "pezza_key_net": 0,
            "pezza_action_search_pct": 0,  # GOAL no trackea acciones
            "pezza_action_move_pct": 0,
            "pezza_action_use_pct": 0,
            "pezza_action_end_turn_pct": 0,
            "pezza_search_to_move_ratio": 0,
            "pezza_rounds_to_first_key": None,
            "outcome": st.outcome,
            "win": st.outcome == "WIN",
            "round": st.round,
            "seed": seed,
            "reward_total": 0,
        })

    wins = [m for m in per_episode if m["win"]]
    losses = [m for m in per_episode if "LOSE" in str(m["outcome"])]
    timeouts = [m for m in per_episode if "TIMEOUT" in str(m["outcome"])]

    aggregate = {
        "n_episodes": len(per_episode),
        "win_rate": len(wins) / max(1, len(per_episode)) * 100,
        "n_wins": len(wins),
        "n_losses": len(losses),
        "n_timeouts": len(timeouts),
        "avg_win_round": np.mean([m["pezza_speed_win_round"] for m in wins if m["pezza_speed_win_round"] is not None]) if wins else None,
        "avg_lose_round": np.mean([m["pezza_speed_lose_round"] for m in losses if m["pezza_speed_lose_round"] is not None]) if losses else None,
        "timeout_rate": len(timeouts) / max(1, len(per_episode)) * 100,
        "avg_keys_per_round": np.mean([m["pezza_keys_per_round"] for m in per_episode]),
        "avg_key_gain_events": 0,
        "avg_key_loss_events": 0,
        "avg_key_net": 0,
        "avg_final_keys": np.mean([m["pezza_final_keys"] for m in per_episode]),
        "avg_keys_deficit": np.mean([m["pezza_keys_deficit"] for m in per_episode]),
        "avg_final_sanity": np.mean([m["pezza_final_sanity"] for m in per_episode]),
        "avg_search_pct": 0,
        "avg_move_pct": 0,
        "avg_use_pct": 0,
        "avg_end_turn_pct": 0,
        "avg_search_to_move_ratio": 0,
        "avg_rounds_to_first_key": None,
        "pct_never_got_key": 0,
    }

    diagnosis = _generate_diagnosis(aggregate, per_episode)
    return {
        "per_episode": per_episode,
        "aggregate": aggregate,
        "diagnosis": diagnosis,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Métricas diagnósticas Pezza para CARCOSA")
    parser.add_argument("model", type=str, help="Ruta al modelo .zip o 'GOAL'")
    parser.add_argument("--seeds", type=int, default=50, help="Número de seeds")
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--king-enabled", action="store_true", default=False)
    args = parser.parse_args()

    if args.model == "GOAL":
        result = diagnose_goal(seeds=range(args.seeds))
    else:
        result = diagnose_model(args.model, seeds=range(args.seeds), device=args.device, king_enabled=args.king_enabled)

    print(result["diagnosis"])
    print("\n--- AGREGATE ---")
    for k, v in result["aggregate"].items():
        print(f"  {k}: {v}")

from __future__ import annotations
from typing import Dict, Optional
import math

from engine.config import Config
from engine.state import GameState
from engine.board import floor_of


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def sigmoid(z: float) -> float:
    # numéricamente estable para rangos típicos
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    else:
        ez = math.exp(z)
        return ez / (1.0 + ez)


def sanity_pressure(state: GameState, cfg: Config) -> float:
    # p_i = clip((S_SAFE - s_i) / (S_SAFE - S_LOSS), 0, 1)
    denom = (cfg.S_SAFE - cfg.S_LOSS)
    if denom <= 0:
        raise ValueError("Config invalid: S_SAFE must be > S_LOSS")

    ps = []
    for p in state.players.values():
        pi = (cfg.S_SAFE - p.sanity) / denom
        ps.append(_clip01(pi))

    if not ps:
        return 0.0

    return 0.7 * max(ps) + 0.3 * (sum(ps) / len(ps))


def round_pressure(state: GameState, cfg: Config) -> float:
    # 1 - exp(-R/tau)
    if cfg.TAU_ROUNDS <= 0:
        return 0.0
    return _clip01(1.0 - math.exp(-(state.round / cfg.TAU_ROUNDS)))


def monster_pressure(state: GameState, cfg: Config) -> float:
    m = len(state.monsters)
    if cfg.TAU_MONSTERS <= 0:
        return 0.0
    return _clip01(1.0 - math.exp(-(m / cfg.TAU_MONSTERS)))


def keys_pressure(state: GameState, cfg: Config) -> float:
    keys_in_hand = sum(p.keys for p in state.players.values())
    if cfg.KEYS_TO_WIN <= 0:
        return 0.0
    return _clip01(keys_in_hand / cfg.KEYS_TO_WIN)


def crown_pressure(state: GameState) -> float:
    # acelerador binario por ahora
    return 1.0 if bool(state.flags.get("CROWN_YELLOW", False)) else 0.0


def umbral_pressure(state: GameState) -> float:
    # fracción de jugadores "en umbral" (placeholder)
    if not state.players:
        return 0.0
    frac = sum(1 for p in state.players.values() if p.at_umbral) / len(state.players)
    return _clip01(frac)


def debuff_pressure(state: GameState, cfg: Config) -> float:
    if not state.players:
        return 0.0
    emax = cfg.E_MAX_PER_PLAYER * len(state.players)
    if emax <= 0:
        return 0.0

    total = 0.0
    for p in state.players.values():
        for st in p.statuses:
            # considera "negativos" según whitelist; si no está, ignora
            if st.status_id in cfg.NEGATIVE_STATUS_IDS:
                total += max(0, st.remaining_rounds) * max(1, st.stacks)

    return _clip01(total / emax)


def king_risk_pressure(state: GameState, cfg: Config) -> float:
    """
    Riesgo del Rey: (jugadores en piso del Rey) × (severidad por min_sanity).
    Captura el peligro de tener jugadores expuestos a King Presence.
    """
    if not state.players:
        return 0.0
    on_king_floor = sum(1 for p in state.players.values() 
                        if floor_of(p.room) == state.king_floor)
    exposure = on_king_floor / len(state.players)
    min_sanity = min(p.sanity for p in state.players.values())
    # Multiplicador de severidad: crece cuando min_sanity < -2
    severity = 1 + max(0, -2 - min_sanity)
    return _clip01(exposure * severity / 3.0)  # normalizar a [0,1]


def compute_features(state: GameState, cfg: Config) -> Dict[str, float]:
    return {
        "P_sanity": sanity_pressure(state, cfg),
        "P_round": round_pressure(state, cfg),
        "P_mon": monster_pressure(state, cfg),
        "P_keys": keys_pressure(state, cfg),
        "P_crown": crown_pressure(state),
        "P_umbral": umbral_pressure(state),
        "P_debuff": debuff_pressure(state, cfg),
        "P_king_risk": king_risk_pressure(state, cfg),
    }


def tension_T(state: GameState, cfg: Config, features: Optional[Dict[str, float]] = None) -> float:
    f = features if features is not None else compute_features(state, cfg)
    z = (
        cfg.BIAS
        + cfg.W_SANITY * f["P_sanity"]
        + cfg.W_ROUND * f["P_round"]
        + cfg.W_MON * f["P_mon"]
        + cfg.W_KEYS * f["P_keys"]
        + cfg.W_CROWN * f["P_crown"]
        + cfg.W_UMBRAL * f["P_umbral"]
        + cfg.W_DEBUFF * f["P_debuff"]
        + cfg.W_KING_RISK * f["P_king_risk"]
    )
    return _clip01(sigmoid(z))


def band_loss(T: float, cfg: Config) -> float:
    """
    Penaliza estar fuera de [low, high].
    Dentro de banda => 0.
    """
    if T < cfg.T_BAND_LOW:
        return ((cfg.T_BAND_LOW - T) / max(cfg.T_BAND_LOW, 1e-9)) ** 2
    if T > cfg.T_BAND_HIGH:
        return ((T - cfg.T_BAND_HIGH) / max(1.0 - cfg.T_BAND_HIGH, 1e-9)) ** 2
    return 0.0


def king_utility(state: GameState, cfg: Config, features: Optional[Dict[str, float]] = None) -> float:
    """
    Utilidad (a maximizar) para el Rey:
    - Mantener T en la banda.
    - Evitar derrota (matar / colapso).
    - Evitar victoria (cerrar el juego) si la intención es "tensión sin matar".
    """
    if state.outcome == "LOSE":
        return -cfg.PENALTY_LOSE
    if state.outcome == "WIN":
        return -cfg.PENALTY_WIN

    T = tension_T(state, cfg, features=features)

    # Queremos maximizar utilidad => minimizar loss
    loss = band_loss(T, cfg)

    # Pequeño incentivo por estar cerca del target dentro de banda (suave)
    closeness = 1.0 - abs(T - cfg.T_TARGET)

    return (0.4 * closeness) - loss

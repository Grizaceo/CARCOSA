from __future__ import annotations
from dataclasses import dataclass, field
from typing import Set


@dataclass(frozen=True)
class Config:
    # --- Tensión objetivo ---
    T_TARGET: float = 0.80
    T_BAND_LOW: float = 0.75
    T_BAND_HIGH: float = 0.85

    # --- Cordura (normalización / derrota) ---
    S_SAFE: int = 3
    S_LOSS: int = -5  # umbral -5

    # --- Casa (pérdida base al final de ronda) ---
    HOUSE_LOSS_PER_ROUND: int = 1

    # --- Monstruos ---
    MAX_MONSTERS_ON_BOARD: int = 8

    # --- Saturaciones ---
    TAU_ROUNDS: float = 6.0
    TAU_MONSTERS: float = 2.0

    # --- Debuffs ---
    E_MAX_PER_PLAYER: float = 3.0
    NEGATIVE_STATUS_IDS: Set[str] = field(default_factory=lambda: {"STUN", "CURSE", "BLEED"})

    # --- Llaves ---
    KEYS_TO_WIN: int = 4
    KEYS_TOTAL: int = 6              # pool canónico base: 5 en mazos + 1 en Motemey
    KEYS_LOSE_THRESHOLD: int = 3     # derrota si quedan <= 3 llaves "en juego" (no destruidas)

    # --- Umbral ---
    # CORRECCIÓN: Umbral de Amarillo es el pasillo del piso 1
    UMBRAL_NODE: str = "F2_P"

    # --- Pesos tensión (baseline) ---
    BIAS: float = -1.2
    W_SANITY: float = 2.2
    W_ROUND: float = 0.8
    W_MON: float = 0.9
    W_KEYS: float = 1.3
    W_CROWN: float = 1.0
    W_UMBRAL: float = 0.7
    W_DEBUFF: float = 0.6

    # --- Penalizaciones utilidad Rey ---
    PENALTY_LOSE: float = 10.0
    PENALTY_WIN: float = 2.5

    # --- Toggle: presencia del Rey (tu experimento) ---
    KING_PRESENCE_START_ROUND: int = 2

    # --- Heurística Rey: evitar -5 hasta ronda 10, luego relajar ---
    KING_KILL_AVOID_START_ROUND: int = 10
    KING_KILL_AVOID_FADE_ROUNDS: int = 10
    KING_KILL_AVOID_PENALTY: float = 60.0

    # a partir de esta ronda el Rey “deja ganar” si la victoria es alcanzable
    KING_ALLOW_WIN_START_ROUND: int = 12

    # Alternativa/seguro anti-stall: permitir WIN cuando el grupo estuvo WIN-ready N veces
    KING_ALLOW_WIN_AFTER_READY_HITS: int = 2

    # --- Termination (sim-only) ---
    # 0 desactiva. Si round > MAX_ROUNDS => TIMEOUT
    MAX_ROUNDS: int = 60
    # MCTS Configuration
    MCTS_ROLLOUTS: int = 100
    MCTS_DEPTH: int = 50
    MCTS_TOP_K: int = 5
    MCTS_DETERMINIZE: bool = False
    TIMEOUT_OUTCOME: str = "TIMEOUT"
    # Si True y no quedan cartas en habitaciones (no pasillos) => LOSE_DECK
    LOSE_ON_DECK_EXHAUSTION: bool = False

    # --- Heurística jugadores ---
    PLAYER_SANITY_PANIC: int = -4

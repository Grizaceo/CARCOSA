from __future__ import annotations

from engine.config import Config
from engine.rules.keys import get_effective_keys_total
from engine.rules.umbral import all_players_in_umbral
from engine.state import GameState


def can_win(state: GameState, cfg: Config) -> bool:
    if state.game_over:
        return False
    if not all_players_in_umbral(state, cfg):
        return False
    total_keys = sum(p.keys for p in state.players.values())
    return total_keys >= int(cfg.KEYS_TO_WIN)


def can_lose_all_minus5(state: GameState, cfg: Config) -> bool:
    if state.game_over:
        return False
    return all(p.sanity <= cfg.S_LOSS for p in state.players.values())


def can_lose_keys_destroyed(state: GameState, cfg: Config) -> bool:
    if state.game_over:
        return False
    if state.keys_destroyed <= 0:
        return False
    keys_total = get_effective_keys_total(state, cfg)
    keys_threshold = getattr(cfg, "KEYS_LOSE_THRESHOLD", 3)
    keys_available = keys_total - state.keys_destroyed
    return keys_available <= keys_threshold

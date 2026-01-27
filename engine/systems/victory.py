from __future__ import annotations

from engine.rules.victory_defeat import can_win, can_lose_all_minus5, can_lose_keys_destroyed
from engine.state import GameState


def check_victory(state: GameState, cfg) -> bool:
    if not can_win(state, cfg):
        return False
    state.game_over = True
    state.outcome = "WIN"
    return True


def check_defeat(state: GameState, cfg) -> bool:
    if can_lose_all_minus5(state, cfg):
        state.game_over = True
        source = state.last_sanity_loss_event or "UNKNOWN"
        state.outcome = f"LOSE_ALL_MINUS5 ({source})"
        return True
    if can_lose_keys_destroyed(state, cfg):
        state.game_over = True
        state.outcome = "LOSE_KEYS_DESTROYED"
        return True
    return False

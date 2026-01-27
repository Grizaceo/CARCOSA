from __future__ import annotations

from engine.config import Config
from engine.state import GameState
from engine.rules.sanity import sanity_cap


def finalize_step(state: GameState, cfg: Config, check_defeat_fn) -> None:
    # Clamp sanity (always)
    for pl in state.players.values():
        if pl.sanity < cfg.S_LOSS:
            pl.sanity = cfg.S_LOSS
        cap = sanity_cap(pl)
        if pl.sanity > cap:
            pl.sanity = cap

    # Cap monsters if configured
    cap = int(getattr(cfg, "MAX_MONSTERS_ON_BOARD", 0) or 0)
    if cap > 0:
        if isinstance(state.monsters, list):
            if len(state.monsters) > cap:
                state.monsters = state.monsters[:cap]
        else:
            try:
                if int(state.monsters) > cap:
                    state.monsters = cap
            except (TypeError, ValueError):
                pass

    if not state.flags.get("PENDING_SACRIFICE_CHECK"):
        check_defeat_fn(state, cfg)

    if (not state.game_over) and getattr(cfg, "LOSE_ON_DECK_EXHAUSTION", False):
        if state.boxes:
            remaining = sum(box.deck.remaining() for box in state.boxes.values())
        else:
            remaining = 0
            for rid, room in state.rooms.items():
                if str(rid).endswith("_P"):
                    continue
                remaining += room.deck.remaining()
        if remaining <= 0:
            state.game_over = True
            state.outcome = "LOSE_DECK"

    max_rounds = int(getattr(cfg, "MAX_ROUNDS", 0) or 0)
    if (not state.game_over) and max_rounds > 0 and state.round > max_rounds:
        state.game_over = True
        state.outcome = getattr(cfg, "TIMEOUT_OUTCOME", "TIMEOUT")


def finalize_and_return(state: GameState, cfg: Config, check_defeat_fn) -> GameState:
    finalize_step(state, cfg, check_defeat_fn)
    return state

from __future__ import annotations

from engine.config import Config
from engine.state import GameState


def all_players_in_umbral(state: GameState, cfg: Config) -> bool:
    return all(str(p.room) == str(cfg.UMBRAL_NODE) for p in state.players.values())

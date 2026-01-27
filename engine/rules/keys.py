from __future__ import annotations

from engine.config import Config
from engine.state import GameState


def get_base_keys_total(cfg: Config) -> int:
    return int(getattr(cfg, "KEYS_TOTAL", 6))


def get_effective_keys_total(state: GameState, cfg: Config) -> int:
    """
    Base pool +1 if CAMARA_LETAL is revealed.
    """
    base = get_base_keys_total(cfg)
    for room in state.rooms.values():
        if room.special_card_id == "CAMARA_LETAL" and room.special_revealed:
            return base + 1
    return base

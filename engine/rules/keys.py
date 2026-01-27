from __future__ import annotations

from engine.config import Config
from engine.state import GameState
from engine.setup import normalize_room_type


def get_base_keys_total(cfg: Config) -> int:
    return int(getattr(cfg, "KEYS_TOTAL", 6))


def get_effective_keys_total(state: GameState, cfg: Config) -> int:
    """
    Base pool +1 if CAMARA_LETAL is revealed.
    """
    base = get_base_keys_total(cfg)
    for room in state.rooms.values():
        if normalize_room_type(room.special_card_id or "") == "CAMARA_LETAL" and room.special_revealed:
            return base + 1
    return base

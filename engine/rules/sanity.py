from __future__ import annotations

from engine.objects import get_effective_sanity_max
from engine.state import PlayerState


def sanity_cap(player: PlayerState) -> int:
    return get_effective_sanity_max(player)

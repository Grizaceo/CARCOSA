from __future__ import annotations

from engine.handlers.statuses import (
    apply_end_of_round_status_effects as _apply_end_of_round_status_effects,
    apply_end_of_turn_status_effects as _apply_end_of_turn_status_effects,
)
from engine.state import GameState


def apply_end_of_round_status_effects(state: GameState) -> None:
    """
    Apply end-of-round status effects before duration tick.

    Implemented:
    - ENVENENADO/SANGRADO: permanent -1 sanity_max
    - MALDITO: other players on same floor lose 1 sanity
    """
    _apply_end_of_round_status_effects(state)


def apply_end_of_turn_status_effects(state: GameState) -> None:
    """
    Apply end-of-turn status effects.
    
    Implemented:
    - SANIDAD: heal 1 sanity (at end of EACH turn)
    """
    _apply_end_of_turn_status_effects(state)

from __future__ import annotations

from engine.board import floor_of
from engine.effects.states_canonical import has_status
from engine.state import GameState
from engine.systems.sanity import heal_player


def apply_end_of_round_status_effects(state: GameState) -> None:
    """
    Apply end-of-round status effects before duration tick.

    Implemented:
    - ENVENENADO/SANGRADO: permanent -1 sanity_max
    - MALDITO: other players on same floor lose 1 sanity
    - SANIDAD: heal 1 sanity (also on end_of_turn)
    """
    # ENVENENADO (alias SANGRADO): Reduce sanity_max in 1 permanently
    for p in state.players.values():
        if has_status(p, "ENVENENADO"):
            if p.sanity_max is not None and p.sanity_max > -5:
                p.sanity_max -= 1
                if p.sanity > p.sanity_max:
                    p.sanity = p.sanity_max

    # MALDITO: affects other players on same floor
    for pid, p in state.players.items():
        if has_status(p, "MALDITO"):
            player_floor = floor_of(p.room)
            for other_pid, other in state.players.items():
                if other_pid != pid and floor_of(other.room) == player_floor:
                    other.sanity -= 1

    # SANIDAD: heal 1
    for p in state.players.values():
        if has_status(p, "SANIDAD"):
            heal_player(p, 1)

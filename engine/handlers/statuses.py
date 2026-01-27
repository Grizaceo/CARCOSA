from __future__ import annotations

from typing import Callable, Dict

from engine.board import floor_of
from engine.effects.states_canonical import has_status
from engine.state import GameState
from engine.systems.sanity import heal_player
from engine.types import PlayerId

StatusEndOfRoundHandler = Callable[[GameState, PlayerId], None]

# Registry for end-of-round status effects (resolved by status_id)
STATUS_END_OF_ROUND_HANDLERS: Dict[str, StatusEndOfRoundHandler] = {}


def register_status_end_of_round(status_id: str) -> Callable[[StatusEndOfRoundHandler], StatusEndOfRoundHandler]:
    def decorator(fn: StatusEndOfRoundHandler) -> StatusEndOfRoundHandler:
        STATUS_END_OF_ROUND_HANDLERS[status_id] = fn
        return fn

    return decorator


def apply_end_of_round_status_effects(state: GameState) -> None:
    for status_id, handler in STATUS_END_OF_ROUND_HANDLERS.items():
        for pid, p in state.players.items():
            if has_status(p, status_id):
                handler(state, pid)


@register_status_end_of_round("ENVENENADO")
def _status_venom(state: GameState, pid: PlayerId) -> None:
    p = state.players[pid]
    if p.sanity_max is not None and p.sanity_max > -5:
        p.sanity_max -= 1
        if p.sanity > p.sanity_max:
            p.sanity = p.sanity_max


@register_status_end_of_round("MALDITO")
def _status_cursed(state: GameState, pid: PlayerId) -> None:
    p = state.players[pid]
    player_floor = floor_of(p.room)
    for other_pid, other in state.players.items():
        if other_pid != pid and floor_of(other.room) == player_floor:
            other.sanity -= 1


@register_status_end_of_round("SANIDAD")
def _status_sanity(state: GameState, pid: PlayerId) -> None:
    p = state.players[pid]
    heal_player(p, 1)


__all__ = [
    "STATUS_END_OF_ROUND_HANDLERS",
    "register_status_end_of_round",
    "apply_end_of_round_status_effects",
]

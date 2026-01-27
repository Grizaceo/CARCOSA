from __future__ import annotations

from typing import Callable, Dict, Optional

from engine.board import floor_of
from engine.rng import RNG
from engine.state import GameState, MonsterState
from engine.systems.sanity import apply_sanity_loss
from engine.types import PlayerId, RoomId

OmenHandler = Callable[[GameState, PlayerId, str, RoomId, bool, Optional[RNG]], bool]

# Registry for omen handlers (resolved by omen_id)
OMEN_HANDLERS: Dict[str, OmenHandler] = {}


def register_omen(omen_id: str) -> Callable[[OmenHandler], OmenHandler]:
    def decorator(fn: OmenHandler) -> OmenHandler:
        OMEN_HANDLERS[omen_id] = fn
        return fn

    return decorator


def get_omen_handler(omen_id: str) -> OmenHandler | None:
    return OMEN_HANDLERS.get(omen_id)


def _spawn_monster(state: GameState, monster_id: str, room: RoomId) -> None:
    from engine.systems.monsters import on_monster_enters_room

    state.monsters.append(MonsterState(monster_id=monster_id, room=room))
    on_monster_enters_room(state, room)


@register_omen("ARAÑA")
def _omen_spider(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, is_early: bool, rng: Optional[RNG]) -> bool:
    if is_early:
        exists = any("SPIDER" in m.monster_id or "ARAÑA" in m.monster_id for m in state.monsters)
        if not exists:
            _spawn_monster(state, "MONSTER:SPIDER", spawn_pos)
    else:
        _spawn_monster(state, "MONSTER:BABY_SPIDER", spawn_pos)
    return True


@register_omen("DUENDE")
def _omen_goblin(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, is_early: bool, rng: Optional[RNG]) -> bool:
    if is_early:
        exists = any("DUENDE" in m.monster_id for m in state.monsters)
        if not exists:
            _spawn_monster(state, "MONSTER:DUENDE", spawn_pos)
    else:
        p = state.players[pid]
        if p.objects:
            p.objects.pop()
    return True


@register_omen("REINA_HELADA")
def _omen_ice_queen(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, is_early: bool, rng: Optional[RNG]) -> bool:
    if is_early:
        exists = any("REINA_HELADA" in m.monster_id for m in state.monsters)
        if not exists:
            corridor = RoomId(f"F{floor_of(spawn_pos)}_P")
            _spawn_monster(state, "MONSTER:REINA_HELADA", corridor)
    else:
        _spawn_monster(state, "MONSTER:ICE_SERVANT", spawn_pos)
    return True


@register_omen("TUE_TUE")
def _omen_tue_tue(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, is_early: bool, rng: Optional[RNG]) -> bool:
    p = state.players[pid]
    state.tue_tue_revelations += 1
    rev = state.tue_tue_revelations
    if rev == 1:
        apply_sanity_loss(state, p, 1, source="TUE_TUE_1")
    elif rev == 2:
        apply_sanity_loss(state, p, 2, source="TUE_TUE_2")
    else:
        p.sanity = -5
    return True

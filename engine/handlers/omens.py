from __future__ import annotations

from typing import Callable, Dict, Optional

from engine.board import floor_of
from engine.config import Config
from engine.rng import RNG
from engine.state import GameState, MonsterState
from engine.types import PlayerId, RoomId
from engine.pathing import find_nearest_empty_room
from engine.handlers.monsters import apply_monster_post_spawn, try_monster_spawn
from engine.objects import can_discard

OmenHandler = Callable[[GameState, PlayerId, str, RoomId, int, bool, Config, Optional[RNG]], bool]

# Registry for omen handlers (resolved by omen_id)
OMEN_HANDLERS: Dict[str, OmenHandler] = {}


def register_omen(omen_id: str) -> Callable[[OmenHandler], OmenHandler]:
    def decorator(fn: OmenHandler) -> OmenHandler:
        OMEN_HANDLERS[omen_id] = fn
        return fn

    return decorator


def get_omen_handler(omen_id: str) -> OmenHandler | None:
    return OMEN_HANDLERS.get(omen_id)


def _spawn_monster(state: GameState, pid: PlayerId, monster_id: str, room: RoomId, cfg: Config, rng: Optional[RNG]) -> None:
    from engine.systems.monsters import on_monster_enters_room

    monster = MonsterState(monster_id=monster_id, room=room)
    state.monsters.append(monster)
    on_monster_enters_room(state, room)
    apply_monster_post_spawn(state, pid, monster, cfg, rng)


def _cap_actions_on_floor(state: GameState, floor: int) -> None:
    for pid, p in state.players.items():
        if floor_of(p.room) == floor:
            state.remaining_actions[pid] = min(state.remaining_actions.get(pid, 0), 1)


@register_omen("ARAÑA")
def _omen_spider(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, total: int, is_low: bool, cfg: Config, rng: Optional[RNG]) -> bool:
    # CANON: 0-1 -> Araña. 2+ -> Pierdes el turno + Araña bebé en habitación cercana sin jugadores.
    if is_low:
        exists = any("SPIDER" in m.monster_id or "ARAÑA" in m.monster_id for m in state.monsters)
        if not exists:
            _spawn_monster(state, pid, "SPIDER", spawn_pos, cfg, rng)
    else:
        state.flags[f"SKIP_TURN_{pid}"] = True
        target_room = find_nearest_empty_room(state, spawn_pos)
        _spawn_monster(state, pid, "BABY_SPIDER", target_room, cfg, rng)

    return True


@register_omen("DUENDE")
def _omen_goblin(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, total: int, is_low: bool, cfg: Config, rng: Optional[RNG]) -> bool:
    if is_low:
        exists = any("DUENDE" in m.monster_id for m in state.monsters)
        if not exists:
            _spawn_monster(state, pid, "DUENDE", spawn_pos, cfg, rng)
    else:
        p = state.players[pid]
        discardable = [obj for obj in p.objects if can_discard(obj)]
        if discardable:
            drop = rng.choice(discardable) if rng else discardable[-1]
            p.objects.remove(drop)
            if drop in p.object_charges:
                del p.object_charges[drop]
            state.discard_pile.append(drop)
    return True


@register_omen("REINA_HELADA")
def _omen_ice_queen(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, total: int, is_low: bool, cfg: Config, rng: Optional[RNG]) -> bool:
    corridor = RoomId(f"F{floor_of(spawn_pos)}_P")

    if is_low:
        exists = any("REINA_HELADA" in m.monster_id for m in state.monsters)
        if not exists:
            _spawn_monster(state, pid, "REINA_HELADA", corridor, cfg, rng)
    else:
        _spawn_monster(state, pid, "ICE_SERVANT", corridor, cfg, rng)
        _cap_actions_on_floor(state, floor_of(spawn_pos))

    return True


@register_omen("TUE_TUE")
def _omen_tue_tue(state: GameState, pid: PlayerId, omen_id: str, spawn_pos: RoomId, total: int, is_low: bool, cfg: Config, rng: Optional[RNG]) -> bool:
    # CANON: 0-1 cuenta como aparición (sin ficha). 2+ -> cordura vuelve a 0.
    p = state.players[pid]
    if is_low:
        try_monster_spawn(state, pid, "TUE_TUE", cfg, rng)
    else:
        p.sanity = 0

    return True

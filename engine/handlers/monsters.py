from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from engine.board import corridor_id, floor_of
from engine.config import Config
from engine.effects.event_utils import add_status
from engine.rng import RNG
from engine.state import GameState, MonsterState, StatusInstance
from engine.systems.rooms import on_player_enters_room
from engine.systems.sanity import apply_sanity_loss
from engine.types import PlayerId, RoomId

MonsterSpawnHandler = Callable[[GameState, PlayerId, str, Config, Optional[RNG]], bool]
MonsterRevealHandler = Callable[[GameState, PlayerId, str, Config, Optional[RNG]], None]
MonsterPostSpawnHandler = Callable[[GameState, PlayerId, MonsterState, Config, Optional[RNG]], None]

# Registry for monster behaviors (resolved by monster_id)
MONSTER_SPAWN_HANDLERS: Dict[str, MonsterSpawnHandler] = {}
MONSTER_REVEAL_HANDLERS: Dict[str, MonsterRevealHandler] = {}
MONSTER_POST_SPAWN_HANDLERS: Dict[str, MonsterPostSpawnHandler] = {}
MONSTER_POST_SPAWN_CONTAINS: List[Tuple[str, MonsterPostSpawnHandler]] = []


def register_monster_spawn(monster_id: str) -> Callable[[MonsterSpawnHandler], MonsterSpawnHandler]:
    def decorator(fn: MonsterSpawnHandler) -> MonsterSpawnHandler:
        MONSTER_SPAWN_HANDLERS[monster_id] = fn
        return fn

    return decorator


def register_monster_reveal(monster_id: str) -> Callable[[MonsterRevealHandler], MonsterRevealHandler]:
    def decorator(fn: MonsterRevealHandler) -> MonsterRevealHandler:
        MONSTER_REVEAL_HANDLERS[monster_id] = fn
        return fn

    return decorator


def register_monster_post_spawn(
    monster_id: str, *, contains: bool = False
) -> Callable[[MonsterPostSpawnHandler], MonsterPostSpawnHandler]:
    def decorator(fn: MonsterPostSpawnHandler) -> MonsterPostSpawnHandler:
        if contains:
            MONSTER_POST_SPAWN_CONTAINS.append((monster_id, fn))
        else:
            MONSTER_POST_SPAWN_HANDLERS[monster_id] = fn
        return fn

    return decorator


def try_monster_spawn(state: GameState, pid: PlayerId, monster_id: str, cfg: Config, rng: Optional[RNG]) -> bool:
    handler = MONSTER_SPAWN_HANDLERS.get(monster_id)
    if handler is None:
        return False
    return handler(state, pid, monster_id, cfg, rng)


def apply_monster_reveal(state: GameState, pid: PlayerId, monster_id: str, cfg: Config, rng: Optional[RNG]) -> None:
    handler = MONSTER_REVEAL_HANDLERS.get(monster_id)
    if handler is not None:
        handler(state, pid, monster_id, cfg, rng)


def apply_monster_post_spawn(state: GameState, pid: PlayerId, monster: MonsterState, cfg: Config, rng: Optional[RNG]) -> None:
    handler = MONSTER_POST_SPAWN_HANDLERS.get(monster.monster_id)
    if handler is not None:
        handler(state, pid, monster, cfg, rng)
        return

    for token, fn in MONSTER_POST_SPAWN_CONTAINS:
        if token in monster.monster_id:
            fn(state, pid, monster, cfg, rng)
            return


@register_monster_spawn("TUE_TUE")
def _spawn_tue_tue(state: GameState, pid: PlayerId, monster_id: str, cfg: Config, rng: Optional[RNG]) -> bool:
    p = state.players[pid]
    state.tue_tue_revelations += 1
    rev = state.tue_tue_revelations
    if rev == 1:
        apply_sanity_loss(state, p, 1, source="TUE_TUE_1", cfg=cfg)
    elif rev == 2:
        apply_sanity_loss(state, p, 2, source="TUE_TUE_2", cfg=cfg)
    else:
        p.sanity = -5
    return True


@register_monster_reveal("ARAÑA")
def _reveal_spider(state: GameState, pid: PlayerId, monster_id: str, cfg: Config, rng: Optional[RNG]) -> None:
    add_status(state.players[pid], "TRAPPED", duration=3, metadata={"source_monster_id": monster_id})


@register_monster_reveal("SPIDER")
def _reveal_spider_en(state: GameState, pid: PlayerId, monster_id: str, cfg: Config, rng: Optional[RNG]) -> None:
    add_status(state.players[pid], "TRAPPED", duration=3, metadata={"source_monster_id": monster_id})


@register_monster_post_spawn("REINA_HELADA")
def _post_spawn_reina_helada(state: GameState, pid: PlayerId, monster: MonsterState, cfg: Config, rng: Optional[RNG]) -> None:
    p = state.players[pid]
    monster.room = corridor_id(floor_of(p.room))
    monster_floor = floor_of(monster.room)
    for other_pid, other in state.players.items():
        if floor_of(other.room) == monster_floor:
            if other_pid not in state.movement_blocked_players:
                state.movement_blocked_players.append(other_pid)


@register_monster_post_spawn("ICE_QUEEN")
def _post_spawn_ice_queen(state: GameState, pid: PlayerId, monster: MonsterState, cfg: Config, rng: Optional[RNG]) -> None:
    _post_spawn_reina_helada(state, pid, monster, cfg, rng)


@register_monster_post_spawn("FROZEN_QUEEN")
def _post_spawn_frozen_queen(state: GameState, pid: PlayerId, monster: MonsterState, cfg: Config, rng: Optional[RNG]) -> None:
    _post_spawn_reina_helada(state, pid, monster, cfg, rng)


@register_monster_post_spawn("DUENDE", contains=True)
def _post_spawn_goblin(state: GameState, pid: PlayerId, monster: MonsterState, cfg: Config, rng: Optional[RNG]) -> None:
    p = state.players[pid]
    if p.objects:
        p.objects = []
        state.flags[f"GOBLIN_HAS_LOOT_{monster.monster_id}"] = True

    if rng:
        current_floor = floor_of(monster.room)
        floors = [f for f in (1, 2, 3) if f != current_floor]
        if floors:
            new_floor = rng.choice(floors)
            parts = str(monster.room).split("_")
            if len(parts) >= 2:
                suffix = parts[1]
                new_room_id = RoomId(f"F{new_floor}_{suffix}")
                monster.room = new_room_id
                from engine.systems.monsters import on_monster_enters_room
                on_monster_enters_room(state, new_room_id)


@register_monster_post_spawn("GOBLIN", contains=True)
def _post_spawn_goblin_en(state: GameState, pid: PlayerId, monster: MonsterState, cfg: Config, rng: Optional[RNG]) -> None:
    _post_spawn_goblin(state, pid, monster, cfg, rng)


@register_monster_post_spawn("VIEJO", contains=True)
def _post_spawn_sack(state: GameState, pid: PlayerId, monster: MonsterState, cfg: Config, rng: Optional[RNG]) -> None:
    p = state.players[pid]
    p.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=3, metadata={"source_monster_id": monster.monster_id}))
    state.flags[f"SACK_HAS_VICTIM_{monster.monster_id}"] = True

    if rng:
        current_floor = floor_of(monster.room)
        floors = [f for f in (1, 2, 3) if f != current_floor]
        if floors:
            new_floor = rng.choice(floors)
            parts = str(monster.room).split("_")
            if len(parts) >= 2:
                suffix = parts[1]
                new_room_id = RoomId(f"F{new_floor}_{suffix}")
                monster.room = new_room_id
                from engine.systems.monsters import on_monster_enters_room
                on_monster_enters_room(state, new_room_id)

                p.room = new_room_id
                on_player_enters_room(state, pid, new_room_id)


@register_monster_post_spawn("SACK", contains=True)
def _post_spawn_sack_en(state: GameState, pid: PlayerId, monster: MonsterState, cfg: Config, rng: Optional[RNG]) -> None:
    _post_spawn_sack(state, pid, monster, cfg, rng)


__all__ = [
    "MONSTER_SPAWN_HANDLERS",
    "MONSTER_REVEAL_HANDLERS",
    "MONSTER_POST_SPAWN_HANDLERS",
    "register_monster_spawn",
    "register_monster_reveal",
    "register_monster_post_spawn",
    "try_monster_spawn",
    "apply_monster_reveal",
    "apply_monster_post_spawn",
]

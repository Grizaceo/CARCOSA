from __future__ import annotations

from engine.board import corridor_id, floor_of, room_from_d4, FLOORS
from engine.config import Config
from engine.rng import RNG
from engine.rules.sanity import sanity_cap
from engine.rules.victory_defeat import can_lose_all_minus5, can_lose_keys_destroyed, can_win
from engine.state import GameState
from engine.systems.sanity import apply_sanity_loss
from engine.types import PlayerId, RoomId

PENDING_SACRIFICE_FLAG = "PENDING_SACRIFICE_CHECK"


def current_false_king_floor(state: GameState) -> int | None:
    sync_crown_holder(state)
    holder_id = state.flags.get("CROWN_HOLDER") if state.flags else None
    if not holder_id:
        return state.false_king_floor
    holder = state.players.get(PlayerId(holder_id))
    if holder is None:
        return state.false_king_floor
    return floor_of(holder.room)


def sync_crown_holder(state: GameState) -> None:
    if state.flags is None:
        return
    holder_id = state.flags.get("CROWN_HOLDER")
    if holder_id:
        holder = state.players.get(PlayerId(holder_id))
        if holder is not None and "CROWN" not in holder.soulbound_items:
            holder.soulbound_items.append("CROWN")
        if not state.flags.get("CROWN_YELLOW"):
            state.flags["CROWN_YELLOW"] = True
        return
    for pid, player in state.players.items():
        if player is None:
            continue
        if "CROWN" in player.soulbound_items:
            state.flags["CROWN_HOLDER"] = str(pid)
            state.flags["CROWN_YELLOW"] = True
            return


def presence_damage_for_round(round_n: int) -> int:
    if round_n <= 3:
        return 1
    if round_n <= 6:
        return 2
    if round_n <= 9:
        return 3
    return 4


def shuffle_all_room_decks(state: GameState, rng: RNG) -> None:
    if state.boxes:
        decks = [box.deck for box in state.boxes.values()]
    else:
        decks = [room.deck for room in state.rooms.values()]
    for deck in decks:
        if deck.remaining() > 1:
            tail = deck.cards[deck.top :]
            rng.shuffle(tail)
            deck.cards[deck.top :] = tail


def expel_players_from_floor(state: GameState, floor: int) -> None:
    if floor == 1:
        dest_floor = 2
    elif floor == 2:
        dest_floor = 1
    elif floor == 3:
        dest_floor = 2
    else:
        return

    stair_room = state.stairs.get(dest_floor)
    if stair_room is None:
        return

    for p in state.players.values():
        if floor_of(p.room) == floor:
            p.room = stair_room


def attract_players_to_floor(state: GameState, floor: int) -> None:
    target = corridor_id(floor)
    fk_floor = current_false_king_floor(state)
    for p in state.players.values():
        if fk_floor is not None and floor_of(p.room) == fk_floor:
            continue
        p.room = target


def expel_players_from_floor_except_fk(state: GameState, floor: int, fk_floor: int | None) -> None:
    if floor == 1:
        dest_floor = 2
    elif floor == 2:
        dest_floor = 1
    elif floor == 3:
        dest_floor = 2
    else:
        return

    stair_room = state.stairs.get(dest_floor)
    if stair_room is None:
        return

    for p in state.players.values():
        if floor_of(p.room) == floor:
            if fk_floor is not None and floor_of(p.room) == fk_floor:
                continue
            p.room = stair_room


def attract_players_to_floor_except_fk(state: GameState, floor: int, fk_floor: int | None) -> None:
    target = corridor_id(floor)
    for p in state.players.values():
        if fk_floor is not None and floor_of(p.room) == fk_floor:
            continue
        p.room = target


def roll_stairs(state: GameState, rng: RNG) -> None:
    for floor in range(1, FLOORS + 1):
        roll = rng.randint(1, 4)
        state.stairs[floor] = room_from_d4(floor, roll)


def false_king_check(state: GameState, rng: RNG, cfg: Config) -> None:
    fk_floor = current_false_king_floor(state)
    if fk_floor is None:
        return

    holder_id = state.flags.get("CROWN_HOLDER")
    if not holder_id:
        return

    holder = state.players.get(PlayerId(holder_id))
    if holder is None:
        return

    if state.false_king_round_appeared is None:
        state.false_king_round_appeared = state.round

    rounds_since = max(0, state.round - state.false_king_round_appeared)
    threshold = int(sanity_cap(holder)) + 1 + int(rounds_since)
    total = rng.randint(1, 6) + max(0, int(holder.sanity))

    if total <= threshold:
        pres = presence_damage_for_round(state.round)
        for p in state.players.values():
            if floor_of(p.room) == fk_floor:
                apply_sanity_loss(state, p, pres, source="FALSE_KING_PRESENCE", cfg=cfg)


def end_of_round_checks(state: GameState, cfg: Config) -> None:
    if state.game_over:
        return
    if not state.flags.get(PENDING_SACRIFICE_FLAG) and can_lose_all_minus5(state, cfg):
        source = state.last_sanity_loss_event or "UNKNOWN"
        state.game_over = True
        state.outcome = f"LOSE_ALL_MINUS5 ({source})"
        return
    if not state.flags.get(PENDING_SACRIFICE_FLAG) and can_lose_keys_destroyed(state, cfg):
        state.game_over = True
        state.outcome = "LOSE_KEYS_DESTROYED"
        return
    if can_win(state, cfg):
        state.game_over = True
        state.outcome = "WIN"


def resolve_king_phase(state: GameState, action, rng: RNG, cfg: Config):
    from engine import transition
    return transition._resolve_king_phase(state, action, rng, cfg)

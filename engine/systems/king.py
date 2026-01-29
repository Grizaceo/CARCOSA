from __future__ import annotations

from engine.board import corridor_id, floor_of, ruleta_floor, rotate_boxes, rotate_boxes_intra_floor
from engine.boxes import sync_room_decks_from_boxes
from engine.config import Config
from engine.effects.states_canonical import decrement_status_durations
from engine.objects import is_soulbound
from engine.rng import RNG
from engine.rules.sanity import sanity_cap
from engine.rules.victory_defeat import can_lose_all_minus5, can_lose_keys_destroyed, can_win
from engine.state import GameState, ensure_canonical_rooms
from engine.systems.finalize import finalize_and_return
from engine.systems.monsters import monster_phase
from engine.systems.rooms import update_umbral_flags
from engine.systems.sacrifice import apply_minus5_transitions
from engine.systems.sanity import apply_sanity_loss
from engine.systems.stairs import roll_stairs
from engine.systems.status import apply_end_of_round_status_effects
from engine.systems.turn import start_new_round
from engine.systems.victory import check_defeat
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


def _roll_override(action, key: str, lo: int, hi: int) -> int | None:
    if not action or not getattr(action, "data", None):
        return None
    val = action.data.get(key)
    try:
        val = int(val)
    except (TypeError, ValueError):
        return None
    if lo <= val <= hi:
        return val
    return None


def resolve_king_phase(state: GameState, action, rng: RNG, cfg: Config):
    # PASO 1: Casa (configurable) a todos
    for p in state.players.values():
        apply_sanity_loss(state, p, cfg.HOUSE_LOSS_PER_ROUND, source="HOUSE_LOSS")

    # Verificar Vanish
    king_active = True
    if state.king_vanished_turns > 0:
        state.king_vanished_turns -= 1
        king_active = False

    if king_active:
        # PASO 2: Ruleta d4 para determinar nuevo piso (canon P0)
        d4 = _roll_override(action, "d4", 1, 4)
        if d4 is None:
            d4 = rng.randint(1, 4)
        rng.last_king_d4 = d4
        new_floor = ruleta_floor(state.king_floor, d4)

        # Excepcion: si cae en piso del Falso Rey, repetir hasta que sea distinto
        fk_floor = current_false_king_floor(state)
        while fk_floor is not None and new_floor == fk_floor:
            d4 = rng.randint(1, 4)
            rng.last_king_d4 = d4
            new_floor = ruleta_floor(state.king_floor, d4)
            fk_floor = current_false_king_floor(state)

        state.king_floor = new_floor

        # PASO 3: Dano por presencia del Rey (en piso nuevo, despues de llegar)
        if state.round >= cfg.KING_PRESENCE_START_ROUND:
            pres = presence_damage_for_round(state.round)
            for p in state.players.values():
                if floor_of(p.room) == state.king_floor:
                    apply_sanity_loss(state, p, pres, source="KING_PRESENCE")

        # PASO 4: Efecto d6 aleatorio
        d6 = _roll_override(action, "d6", 1, 6)
        if d6 is None:
            d6 = rng.randint(1, 6)
        rng.last_king_d6 = d6
        fk_floor = current_false_king_floor(state)

        if d6 == 1:
            state.flags["king_d6_intra_rotation"] = True
        elif d6 == 2:
            for p in state.players.values():
                if fk_floor is None or floor_of(p.room) != fk_floor:
                    apply_sanity_loss(state, p, 1, source="KING_D6_2")
        elif d6 == 3:
            state.limited_action_floor_next = state.king_floor
        elif d6 == 4:
            expel_players_from_floor_except_fk(state, state.king_floor, fk_floor)
        elif d6 == 5:
            attract_players_to_floor_except_fk(state, state.king_floor, fk_floor)
        elif d6 == 6:
            for p in state.players.values():
                if fk_floor is None or floor_of(p.room) != fk_floor:
                    discardable = [obj for obj in p.objects if not is_soulbound(obj)]
                    if discardable:
                        p.objects.remove(discardable[-1])

    # PASO 4.4: FASE DE MONSTRUOS (Ataque/Stun)
    monster_phase(state, cfg)

    # PASO 4.5: Aplicar efectos de estados al final de ronda (antes de tick)
    apply_end_of_round_status_effects(state)

    # PASO 5: Tick estados (decremento de duraciones)
    for p in state.players.values():
        decrement_status_durations(p)

    # Check defeat finally
    if not state.flags.get(PENDING_SACRIFICE_FLAG):
        check_defeat(state, cfg)

    # PASO 6: Check del Falso Rey
    false_king_check(state, rng, cfg)

    update_umbral_flags(state, cfg)
    apply_minus5_transitions(state, cfg)
    roll_stairs(state, rng)

    if state.flags.get("king_d6_intra_rotation"):
        state.box_at_room = rotate_boxes_intra_floor(state.box_at_room)
        state.flags["king_d6_intra_rotation"] = False
    else:
        state.box_at_room = rotate_boxes(state.box_at_room)

    ensure_canonical_rooms(state)
    sync_room_decks_from_boxes(state)

    end_of_round_checks(state, cfg)

    state.round += 1
    if not state.game_over:
        start_new_round(state)

    return finalize_and_return(state, cfg, check_defeat)

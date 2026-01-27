from __future__ import annotations

from engine.board import floor_of
from engine.rng import RNG
from engine.setup import normalize_room_type
from engine.state import GameState, MonsterState
from engine.handlers.monsters import apply_monster_post_spawn, apply_monster_reveal, try_monster_spawn
from engine.handlers.omens import get_omen_handler
from engine.types import PlayerId, RoomId


def on_monster_enters_room(state: GameState, room: RoomId) -> None:
    """
    P1 - FASE 1.5.3: Hook cuando un monstruo entra a una habitación.

    Si la habitación tiene una habitación especial activa (no destruida), la destruye.
    Según P1: cuando un monstruo entra, la habitación especial se destruye, pero el nodo
    y su mazo permanecen intactos.

    ESPECIFICO: Para Armeria, ademas vacia su almacenamiento.
    """
    if room not in state.rooms:
        return

    room_state = state.rooms[room]

    if (room_state.special_card_id is not None and
        not room_state.special_destroyed):

        room_state.special_destroyed = True

        room_type = normalize_room_type(room_state.special_card_id or "")
        if room_type == "ARMERIA":
            if room in state.armory_storage:
                state.armory_storage[room] = []

        if room_type == "ARMERIA":
            state.flags[f"ARMORY_DESTROYED_{room}"] = True


def monster_phase(state: GameState, cfg) -> None:
    """
    Fase de Monstruos (Fin de Ronda):
    1. Movimiento de monstruos (si no están STUNNED).
    2. Ataque básico (1 daño cordura) a jugadores en la misma habitación.
    3. Decremento de STUN (si están STUNNED no atacan ni mueven en este turno).
    """
    move_monsters(state, cfg)

    for m in state.monsters:
        if m.stunned_remaining_rounds > 0:
            m.stunned_remaining_rounds -= 1
        else:
            # CANON: No daño pasivo por estar en la misma habitación.
            pass


def move_monsters(state: GameState, cfg) -> None:
    """
    Lógica de movimiento de monstruos (AI).
    """
    from engine.board import get_next_move_to_targets, get_next_move_away_from_targets

    player_rooms = {p.room for p in state.players.values()}

    for m in state.monsters:
        if m.stunned_remaining_rounds > 0:
            continue

        mid = m.monster_id

        if "SPIDER" in mid or "ARAÑA" in mid:
            if m.room in player_rooms:
                continue
            next_room = get_next_move_to_targets(m.room, player_rooms)
            if next_room != m.room:
                m.room = next_room
                on_monster_enters_room(state, next_room)

        elif "DUENDE" in mid or "GOBLIN" in mid:
            has_loot = state.flags.get(f"GOBLIN_HAS_LOOT_{mid}", False)
            if has_loot:
                next_room = get_next_move_away_from_targets(m.room, player_rooms)
            else:
                if m.room in player_rooms:
                    continue
                next_room = get_next_move_to_targets(m.room, player_rooms)
            if next_room != m.room:
                m.room = next_room
                on_monster_enters_room(state, next_room)

        elif "VIEJO" in mid or "SACK" in mid:
            has_victim = state.flags.get(f"SACK_HAS_VICTIM_{mid}", False)
            if has_victim:
                next_room = get_next_move_away_from_targets(m.room, player_rooms)
            else:
                if m.room in player_rooms:
                    continue
                next_room = get_next_move_to_targets(m.room, player_rooms)
            if next_room != m.room:
                m.room = next_room
                on_monster_enters_room(state, next_room)

        elif "REINA" in mid or "HELADA" in mid:
            pass

        else:
            if m.room in player_rooms:
                continue
            next_room = get_next_move_to_targets(m.room, player_rooms)
            if next_room != m.room:
                m.room = next_room
                on_monster_enters_room(state, next_room)


def spawn_monster_from_card(state: GameState, pid: PlayerId, mid: str, cfg, rng: RNG | None) -> bool:
    """
    Spawns a monster revealed from a card, applying special-case rules.
    Returns True if handled (including no-spawn cases like TUE_TUE).
    """
    p = state.players[pid]

    if try_monster_spawn(state, pid, mid, cfg, rng):
        return True

    apply_monster_reveal(state, pid, mid, cfg, rng)

    cap = int(getattr(cfg, "MAX_MONSTERS_ON_BOARD", 0) or 0)
    if cap > 0 and len(state.monsters) >= cap:
        return True

    monster_room = p.room
    monster = MonsterState(monster_id=mid, room=monster_room)
    state.monsters.append(monster)
    on_monster_enters_room(state, monster_room)

    apply_monster_post_spawn(state, pid, monster, cfg, rng)

    return True


def handle_omen_reveal(state: GameState, pid: PlayerId, omen_id: str, rng: RNG | None) -> bool:
    """
    Handles OMEN effects related to monsters. Returns True if handled.
    """
    flag_name = f"OMEN_REVEALED_COUNT_{omen_id}"
    count = state.flags.get(flag_name, 0)
    state.flags[flag_name] = count + 1
    is_early = count < 2

    def find_spawn_room(start_room):
        occupied = {pl.room for pl in state.players.values()}
        current_floor_num = floor_of(start_room)

        candidates = []
        for r in range(1, 5):
            rid = RoomId(f"F{current_floor_num}_R{r}")
            if rid not in occupied:
                candidates.append(rid)
        if candidates:
            return candidates[0]

        cid = RoomId(f"F{current_floor_num}_P")
        if cid not in occupied:
            return cid

        for f in range(1, 4):
            if f == current_floor_num:
                continue
            cid = RoomId(f"F{f}_P")
            if cid not in occupied:
                return cid

        for f in range(1, 4):
            if f == current_floor_num:
                continue
            for r in range(1, 5):
                rid = RoomId(f"F{f}_R{r}")
                if rid not in occupied:
                    return rid

        return start_room

    spawn_pos = find_spawn_room(state.players[pid].room)

    handler = get_omen_handler(omen_id)
    if handler is not None:
        return handler(state, pid, omen_id, spawn_pos, is_early, rng)

    return False

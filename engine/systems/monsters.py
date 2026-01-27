from __future__ import annotations

from engine.board import corridor_id, floor_of
from engine.effects.event_utils import add_status
from engine.rng import RNG
from engine.setup import normalize_room_type
from engine.state import GameState, MonsterState, StatusInstance
from engine.systems.rooms import on_player_enters_room
from engine.systems.sanity import apply_sanity_loss
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

    if mid == "TUE_TUE":
        state.tue_tue_revelations += 1
        rev = state.tue_tue_revelations
        if rev == 1:
            apply_sanity_loss(state, p, 1, source="TUE_TUE_1", cfg=cfg)
        elif rev == 2:
            apply_sanity_loss(state, p, 2, source="TUE_TUE_2", cfg=cfg)
        else:
            p.sanity = -5
        return True

    if mid == "ARAÑA" or mid == "SPIDER":
        add_status(p, "TRAPPED", duration=3, metadata={"source_monster_id": mid})

    cap = int(getattr(cfg, "MAX_MONSTERS_ON_BOARD", 0) or 0)
    if cap > 0 and len(state.monsters) >= cap:
        return True

    monster_room = p.room
    state.monsters.append(MonsterState(monster_id=mid, room=monster_room))
    on_monster_enters_room(state, monster_room)

    if mid in ("REINA_HELADA", "ICE_QUEEN", "FROZEN_QUEEN"):
        monster_room = corridor_id(floor_of(p.room))
        state.monsters[-1].room = monster_room

        monster_floor = floor_of(monster_room)
        for other_pid, other in state.players.items():
            if floor_of(other.room) == monster_floor:
                if other_pid not in state.movement_blocked_players:
                    state.movement_blocked_players.append(other_pid)

    if "DUENDE" in mid or "GOBLIN" in mid:
        if p.objects:
            p.objects = []
            state.flags[f"GOBLIN_HAS_LOOT_{mid}"] = True

        if rng:
            current_floor = floor_of(monster_room)
            floors = [f for f in (1, 2, 3) if f != current_floor]
            if floors:
                new_floor = rng.choice(floors)
                parts = str(monster_room).split("_")
                if len(parts) >= 2:
                    suffix = parts[1]
                    new_room_id = RoomId(f"F{new_floor}_{suffix}")
                    state.monsters[-1].room = new_room_id
                    on_monster_enters_room(state, new_room_id)

    if "VIEJO" in mid or "SACK" in mid:
        p.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=3, metadata={"source_monster_id": mid}))
        state.flags[f"SACK_HAS_VICTIM_{mid}"] = True

        if rng:
            current_floor = floor_of(monster_room)
            floors = [f for f in (1, 2, 3) if f != current_floor]
            if floors:
                new_floor = rng.choice(floors)
                parts = str(monster_room).split("_")
                if len(parts) >= 2:
                    suffix = parts[1]
                    new_room_id = RoomId(f"F{new_floor}_{suffix}")
                    state.monsters[-1].room = new_room_id
                    on_monster_enters_room(state, new_room_id)

                    p.room = new_room_id
                    on_player_enters_room(state, pid, new_room_id)

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

    if omen_id == "ARAÑA":
        if is_early:
            exists = any("SPIDER" in m.monster_id or "ARAÑA" in m.monster_id for m in state.monsters)
            if not exists:
                state.monsters.append(MonsterState(monster_id="MONSTER:SPIDER", room=spawn_pos))
                on_monster_enters_room(state, spawn_pos)
        else:
            state.monsters.append(MonsterState(monster_id="MONSTER:BABY_SPIDER", room=spawn_pos))
            on_monster_enters_room(state, spawn_pos)
        return True

    if omen_id == "DUENDE":
        if is_early:
            exists = any("DUENDE" in m.monster_id for m in state.monsters)
            if not exists:
                state.monsters.append(MonsterState(monster_id="MONSTER:DUENDE", room=spawn_pos))
                on_monster_enters_room(state, spawn_pos)
        else:
            p = state.players[pid]
            if p.objects:
                p.objects.pop()
        return True

    if omen_id == "REINA_HELADA":
        if is_early:
            exists = any("REINA_HELADA" in m.monster_id for m in state.monsters)
            if not exists:
                c_id = RoomId(f"F{floor_of(spawn_pos)}_P")
                state.monsters.append(MonsterState(monster_id="MONSTER:REINA_HELADA", room=c_id))
                on_monster_enters_room(state, c_id)
        else:
            state.monsters.append(MonsterState(monster_id="MONSTER:ICE_SERVANT", room=spawn_pos))
            on_monster_enters_room(state, spawn_pos)
        return True

    if omen_id == "TUE_TUE":
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

    return False

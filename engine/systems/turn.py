from __future__ import annotations

from engine.board import floor_of
from engine.effects.states_canonical import has_status
from engine.effects.protect import apply_tank_shields
from engine.entities import normalize_monster_id
from engine.systems.status import apply_end_of_turn_status_effects
from engine.state import GameState


def advance_turn_or_king(state: GameState) -> None:
    # End of current player's turn logic (before switching)
    apply_end_of_turn_status_effects(state)

    order = state.turn_order
    if not order:
        state.phase = "KING"
        return

    start = state.turn_pos
    n = len(order)
    for i in range(1, n + 1):
        pos = (start + i) % n
        pid = order[pos]
        if state.remaining_actions.get(pid, 0) > 0:
            state.turn_pos = pos
            if pid in state.taberna_used_this_turn:
                del state.taberna_used_this_turn[pid]
            if pid in state.peek_used_this_turn:
                del state.peek_used_this_turn[pid]
            return

    state.phase = "KING"


def start_new_round(state: GameState) -> None:
    # TANK: Apply +1 shield at round start
    apply_tank_shields(state)
    
    order = state.turn_order
    if not order:
        state.phase = "PLAYER"
        return

    state.starter_pos = (state.starter_pos + 1) % len(order)
    state.turn_pos = state.starter_pos
    state.phase = "PLAYER"

    initial_pid = order[state.turn_pos]
    if initial_pid in state.taberna_used_this_turn:
        del state.taberna_used_this_turn[initial_pid]
    if initial_pid in state.peek_used_this_turn:
        del state.peek_used_this_turn[initial_pid]

    state.movement_blocked_players = []

    reina_floors = set()
    for monster in state.monsters:
        mid = normalize_monster_id(monster.monster_id)
        if mid in ("REINA_HELADA", "ICE_QUEEN", "FROZEN_QUEEN", "ICE_SERVANT"):
            if monster.stunned_remaining_rounds <= 0:
                reina_floors.add(floor_of(monster.room))

    for pid in order:
        p = state.players[pid]

        skip_flag = f"SKIP_TURN_{pid}"
        if state.flags.get(skip_flag, False):
            state.flags[skip_flag] = False
            state.remaining_actions[pid] = 0
            p.double_roll_used_this_turn = False
            p.free_move_used_this_turn = False
            continue

        p.double_roll_used_this_turn = False
        p.free_move_used_this_turn = False

        actions = 2

        if state.limited_action_floor_next is not None:
            if floor_of(p.room) == state.limited_action_floor_next:
                actions = min(actions, 1)

        if floor_of(state.players[pid].room) in reina_floors:
            actions = min(actions, 1)

        if has_status(p, "ILUMINADO"):
            actions += 1

        state.remaining_actions[pid] = actions

    state.limited_action_floor_next = None

from __future__ import annotations

from typing import Optional

from engine.actions import Action, ActionType
from engine.board import corridor_id, floor_of, is_corridor
from engine.config import Config
from engine.effects.states_canonical import remove_all_statuses
from engine.effects.event_utils import add_status
from engine.handlers.special_rooms import handle_special_room_action
from engine.objects import is_soulbound, use_object
from engine.roles import brawler_blunt_free
from engine.rng import RNG
from engine.state import GameState
from engine.systems.rooms import handle_hallway_peek_action, update_umbral_flags
from engine.systems.sacrifice import apply_sacrifice_choice, apply_minus5_transitions
from engine.systems.sanity import apply_sanity_loss, heal_player
from engine.types import PlayerId, RoomId


def apply_player_action(state: GameState, action: Action, rng: RNG, cfg: Config) -> GameState:
    from engine import transition

    s = state
    pid = PlayerId(action.actor)
    p = s.players[pid]

    if action.type == ActionType.MOVE:
        to = RoomId(action.data["to"])
        from_room = p.room
        previous_floor = floor_of(p.room)
        new_floor = floor_of(to)

        p.room = to

        if previous_floor != new_floor and getattr(p, "role_id", "") == "SCOUT":
            d6 = rng.randint(1, 6)
            if d6 + p.sanity < 3:
                # Canon: STUN if total < 3
                add_status(p, "STUN", duration=1)

        transition._on_player_enters_room(s, pid, to)

        if not is_corridor(from_room) and is_corridor(to) and previous_floor == new_floor:
            s.flags["PENDING_HALLWAY_PEEK"] = str(pid)
        else:
            card = transition._reveal_one(s, to)
            if card is not None:
                transition._resolve_card_minimal(s, pid, card, cfg, rng)

    elif action.type == ActionType.SEARCH:
        card = transition._reveal_one(s, p.room)
        if card is not None:
            transition._resolve_card_minimal(s, pid, card, cfg, rng)

    elif action.type == ActionType.MEDITATE:
        heal = 2 if is_corridor(p.room) else 1
        heal_player(p, heal)

    elif action.type == ActionType.DISCARD_SANIDAD:
        remove_all_statuses(p)

    elif action.type == ActionType.SACRIFICE:
        apply_sacrifice_choice(s, pid, cfg, action.data)

    elif action.type == ActionType.ESCAPE_TRAPPED:
        d6 = rng.randint(1, 6)
        total = d6 + p.sanity
        s.action_log.append({"event": "ESCAPE_ATTEMPT", "d6": d6, "sanity": p.sanity, "total": total, "success": total >= 3})

        if total >= 3:
            trapped_st = None
            for st in p.statuses:
                if st.status_id in ("TRAPPED", "TRAPPED_SPIDER"):
                    trapped_st = st
                    break

            p.statuses = [st for st in p.statuses if st.status_id not in ("TRAPPED", "TRAPPED_SPIDER")]

            if trapped_st and trapped_st.metadata.get("source_monster_id"):
                mid = trapped_st.metadata["source_monster_id"]
                for monster in s.monsters:
                    if monster.monster_id == mid:
                        if "YELLOW_KING" not in monster.monster_id:
                            monster.stunned_remaining_rounds = 1
                        break
            else:
                for monster in s.monsters:
                    if monster.room == p.room:
                        monster.stunned_remaining_rounds = 1
        else:
            s.remaining_actions[pid] = 0
            return transition._finalize_and_return(s, cfg)

    elif action.type == ActionType.END_TURN:
        s.remaining_actions[pid] = 0
        s.motemey_event_active = False

    elif handle_hallway_peek_action(s, pid, action):
        pass

    elif handle_special_room_action(s, pid, action, rng, cfg):
        pass

    elif action.type == ActionType.USE_ATTACH_TALE:
        tale_id = action.data.get("tale_id")
        if tale_id in p.objects:
            p.objects.remove(tale_id)
            s.chambers_tales_attached += 1
            s.flags[f"TALE_ATTACHED_{tale_id}"] = True
            if s.chambers_tales_attached >= 4:
                s.king_vanished_turns = 4
                s.action_log.append({"event": "KING_VANISHED", "turns": 4})

    elif action.type == ActionType.USE_HEALER_HEAL:
        apply_sanity_loss(s, p, 1, source="HEALER_ABILITY", cfg=cfg)
        status_choice = action.data.get("status_choice", "SANIDAD")
        others = [op for opid, op in s.players.items() if opid != pid]
        for op in others:
            heal_player(op, 2)
            add_status(op, status_choice)

    elif action.type == ActionType.USE_BLUNT:
        use_object(s, pid, "BLUNT", cfg, rng)

    elif action.type == ActionType.USE_PORTABLE_STAIRS:
        direction = action.data.get("direction", "UP")
        current = floor_of(p.room)
        target = current + 1 if direction == "UP" else current - 1

        if 1 <= target <= 3:
            if transition.consume_object(s, pid, "PORTABLE_STAIRS"):
                p.room = corridor_id(target)
                transition._on_player_enters_room(s, pid, p.room)
                card = transition._reveal_one(s, p.room)
                if card is not None:
                    transition._resolve_card_minimal(s, pid, card, cfg, rng)

    cost_override: Optional[int] = None
    if action.type == ActionType.USE_BLUNT:
        if brawler_blunt_free(p):
            cost_override = 0

    cost = transition._consume_action_if_needed(action.type, cost_override=cost_override)

    if action.type == ActionType.MOVE and getattr(p, "role_id", "") == "SCOUT":
        if not p.free_move_used_this_turn:
            cost = 0
            p.free_move_used_this_turn = True

    if cost > 0:
        s.remaining_actions[pid] = max(0, s.remaining_actions.get(pid, 0) - cost)

    update_umbral_flags(s, cfg)
    apply_minus5_transitions(s, cfg)

    if s.remaining_actions.get(pid, 0) <= 0:
        if action.type == ActionType.END_TURN:
            transition._advance_turn_or_king(s)

    return transition._finalize_and_return(s, cfg)

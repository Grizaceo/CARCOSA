from __future__ import annotations
from typing import Optional

from engine.actions import Action, ActionType
from engine.config import Config
from engine.legality import get_legal_actions
from engine.rng import RNG
from engine.state import GameState
from engine.types import PlayerId, RoomId, CardId
from engine.rules.actions_cost import consume_action_cost
from engine.systems.victory import check_victory, check_defeat
from engine.systems.finalize import finalize_step, finalize_and_return
from engine.systems.sanity import apply_sanity_loss
from engine.systems.status import apply_end_of_round_status_effects
from engine.systems.player import apply_player_action
from engine.systems.king import resolve_king_phase
from engine.systems.sacrifice import (
    PENDING_SACRIFICE_FLAG,
    apply_sacrifice_choice,
    apply_minus5_consequences,
    apply_minus5_transitions,
    pending_sacrifice_pid,
    pop_pending_sacrifice_damage,
    pop_pending_sacrifice,
)
from engine.compat.legacy import (
    legacy_reveal_one,
    legacy_resolve_card_minimal,
    legacy_resolve_event,
    legacy_on_player_enters_room,
    legacy_on_monster_enters_room,
    legacy_monster_phase,
    legacy_move_monsters,
    legacy_current_false_king_floor,
    legacy_presence_damage_for_round,
    legacy_shuffle_all_room_decks,
    legacy_expel_players_from_floor,
    legacy_attract_players_to_floor,
    legacy_expel_players_from_floor_except_fk,
    legacy_attract_players_to_floor_except_fk,
    legacy_roll_stairs,
    legacy_false_king_check,
    legacy_end_of_round_checks,
    legacy_advance_turn_or_king,
    legacy_start_new_round,
    normalize_action_type,
)
from engine.effects.states_canonical import has_status, decrement_status_durations

def _apply_minus5_transitions(s, cfg):
    apply_minus5_transitions(s, cfg)


def _apply_minus5_consequences(s, pid, cfg):
    apply_minus5_consequences(s, pid, cfg)



def _consume_action_if_needed(action_type: ActionType, cost_override: Optional[int] = None) -> int:
    return consume_action_cost(action_type, cost_override)


def _check_victory(s, cfg) -> bool:
    return check_victory(s, cfg)


def _check_defeat(s, cfg) -> bool:
    return check_defeat(s, cfg)


def _finalize_step(s, cfg):
    finalize_step(s, cfg, _check_defeat)


def _finalize_and_return(x, cfg):
    return finalize_and_return(x, cfg, _check_defeat)


def _reveal_one(s, room_id: RoomId):
    return legacy_reveal_one(s, room_id)


def _resolve_card_minimal(s, pid: PlayerId, card, cfg, rng: Optional[RNG] = None):
    return legacy_resolve_card_minimal(s, pid, card, cfg, rng)


def _on_player_enters_room(s: GameState, pid: PlayerId, room: RoomId) -> None:
    legacy_on_player_enters_room(s, pid, room)


def _on_monster_enters_room(s: GameState, room: RoomId) -> None:
    legacy_on_monster_enters_room(s, room)


def _resolve_event(s: GameState, pid: PlayerId, event_id: str, cfg: Config, rng: RNG, card_prefix: str = "EVENT"):
    legacy_resolve_event(s, pid, event_id, cfg, rng, card_prefix=card_prefix)


def _update_umbral_flags(s, cfg):
    from engine.systems.rooms import update_umbral_flags
    update_umbral_flags(s, cfg)


def _apply_status_effects_end_of_round(s: GameState) -> None:
    apply_end_of_round_status_effects(s)





def _presence_damage_for_round(round_n: int) -> int:
    return legacy_presence_damage_for_round(round_n)


def _shuffle_all_room_decks(s, rng: RNG):
    legacy_shuffle_all_room_decks(s, rng)


def _expel_players_from_floor(s, floor: int):
    legacy_expel_players_from_floor(s, floor)


def _attract_players_to_floor(s, floor: int):
    legacy_attract_players_to_floor(s, floor)


def _expel_players_from_floor_except_fk(s, floor: int, fk_floor: Optional[int]):
    legacy_expel_players_from_floor_except_fk(s, floor, fk_floor)


def _attract_players_to_floor_except_fk(s, floor: int, fk_floor: Optional[int]):
    legacy_attract_players_to_floor_except_fk(s, floor, fk_floor)


def _roll_stairs(s, rng: RNG):
    legacy_roll_stairs(s, rng)


def _false_king_check(s, rng: RNG, cfg):
    legacy_false_king_check(s, rng, cfg)


def _advance_turn_or_king(s):
    legacy_advance_turn_or_king(s)


def _start_new_round(s, cfg):
    legacy_start_new_round(s)



def step(state: GameState, action: Action, rng: RNG, cfg: Optional[Config] = None) -> GameState:
    cfg = cfg or Config()
    s = state.clone()
    if hasattr(s, "last_sanity_loss_events"):
        s.last_sanity_loss_events = []

    if not isinstance(action.type, ActionType):
        normalized = normalize_action_type(str(action.type))
        action = Action(actor=action.actor, type=ActionType(normalized), data=action.data)

    legal = get_legal_actions(s, action.actor)
    
    # Validación: KING_ENDROUND puede tener cualquier data (se ignora y se usa RNG)
    if action.type == ActionType.KING_ENDROUND and action.actor == "KING":
        # Solo verificar que existe al menos una acción KING_ENDROUND legal
        if not any(a.type == ActionType.KING_ENDROUND for a in legal):
            raise ValueError(f"Illegal action for actor={action.actor}: {action}")
    elif action not in legal:
        raise ValueError(f"Illegal action for actor={action.actor}: {action}")

    s.action_log.append(
        {"round": s.round, "phase": s.phase, "actor": action.actor, "type": action.type.value, "data": action.data}
    )

    # CANON Fix #A: Handle Pending Sacrifice Check
    pending_pid_str = pending_sacrifice_pid(s)
    if pending_pid_str:
        if action.actor != pending_pid_str:
             raise ValueError(f"Pending sacrifice check for {pending_pid_str}, but {action.actor} acted.")
        
        if action.type == ActionType.SACRIFICE:
            # Player chose to SACRIFICE
            # Apply sacrifice cost
            apply_sacrifice_choice(s, PlayerId(pending_pid_str), cfg, action.data)
            # Clear flag, do NOT apply -5 consequences (as sanity is now 0 > -5)
            # p.at_minus5 remains False (or becomes False)
            pop_pending_sacrifice_damage(s, PlayerId(pending_pid_str))
            pop_pending_sacrifice(s)
            return _finalize_and_return(s, cfg)
            
        elif action.type == ActionType.ACCEPT_SACRIFICE:
            # Player chose to accept consequences
            pending_damage = pop_pending_sacrifice_damage(s, PlayerId(pending_pid_str))
            if pending_damage:
                p = s.players[PlayerId(pending_pid_str)]
                apply_sanity_loss(
                    s,
                    p,
                    int(pending_damage.get("amount", 0)),
                    cfg=cfg,
                    source=pending_damage.get("source", "UNKNOWN"),
                    allow_sacrifice=False,
                )
            apply_minus5_consequences(s, PlayerId(pending_pid_str), cfg)
            pop_pending_sacrifice(s)
            return _finalize_and_return(s, cfg)
            
        else:
             raise ValueError(f"Illegal action during sacrifice check: {action.type}. Must be SACRIFICE or ACCEPT_SACRIFICE.")

    if s.phase == "PLAYER":
        return apply_player_action(s, action, rng, cfg)

    if s.phase == "KING" and action.type == ActionType.KING_ENDROUND:
        return resolve_king_phase(s, action, rng, cfg)

    return _finalize_and_return(s, cfg)



def _apply_player_action(s: GameState, action: Action, rng: RNG, cfg: Config) -> GameState:
    return apply_player_action(s, action, rng, cfg)

    # FASE REY (fin de ronda)
    # -------------------------



def _resolve_king_phase(s: GameState, action: Action, rng: RNG, cfg: Config) -> GameState:
    return resolve_king_phase(s, action, rng, cfg)





def _monster_phase(s: GameState, cfg: Config) -> None:
    legacy_monster_phase(s, cfg)


def _move_monsters(s: GameState, cfg: Config) -> None:
    legacy_move_monsters(s, cfg)


from __future__ import annotations

from typing import Optional

from engine.handlers.cards import resolve_card_minimal as _resolve_card_minimal
from engine.handlers.events import resolve_event as _resolve_event
from engine.systems.decks import reveal_one as _reveal_one
from engine.systems.king import (
    current_false_king_floor as _current_false_king_floor,
    sync_crown_holder as _sync_crown_holder,
    presence_damage_for_round as _presence_damage_for_round,
    shuffle_all_room_decks as _shuffle_all_room_decks,
    expel_players_from_floor as _expel_players_from_floor,
    attract_players_to_floor as _attract_players_to_floor,
    expel_players_from_floor_except_fk as _expel_players_from_floor_except_fk,
    attract_players_to_floor_except_fk as _attract_players_to_floor_except_fk,
    false_king_check as _false_king_check,
    end_of_round_checks as _end_of_round_checks,
)
from engine.systems.stairs import roll_stairs as _roll_stairs
from engine.systems.monsters import (
    on_monster_enters_room as _on_monster_enters_room,
    monster_phase as _monster_phase,
    move_monsters as _move_monsters,
)
from engine.systems.rooms import on_player_enters_room as _on_player_enters_room
from engine.systems.turn import (
    advance_turn_or_king as _advance_turn_or_king,
    start_new_round as _start_new_round,
)
from engine.types import PlayerId, RoomId
from engine.rng import RNG
from engine.state import GameState
from engine.config import Config
from engine.setup import normalize_room_type as _normalize_room_type


# Legacy action type aliases (for replay compatibility)
LEGACY_ACTION_TYPE_ALIASES = {
    "MOTEMEY_BUY": "USE_MOTEMEY_BUY",
    "MOTEMEY_BUY_START": "USE_MOTEMEY_BUY_START",
    "MOTEMEY_BUY_CHOOSE": "USE_MOTEMEY_BUY_CHOOSE",
    "MOTEMEY_SELL": "USE_MOTEMEY_SELL",
    "YELLOW_DOORS": "USE_YELLOW_DOORS",
    "TABERNA_ROOMS": "USE_TABERNA_ROOMS",
    "ARMORY_DROP": "USE_ARMORY_DROP",
    "ARMORY_TAKE": "USE_ARMORY_TAKE",
    "SALON_BELLEZA": "USE_SALON_BELLEZA",
    "CAPILLA": "USE_CAPILLA",
    "CAMARA_LETAL": "USE_CAMARA_LETAL_RITUAL",
    "ATTACH_TALE": "USE_ATTACH_TALE",
    "PORTABLE_STAIRS": "USE_PORTABLE_STAIRS",
    "HEALER_HEAL": "USE_HEALER_HEAL",
    "BLUNT": "USE_BLUNT",
}


def normalize_action_type(action_type: str) -> str:
    return LEGACY_ACTION_TYPE_ALIASES.get(action_type, action_type)


def normalize_room_type(room_type: str) -> str:
    return _normalize_room_type(room_type)


def legacy_reveal_one(state: GameState, room_id: RoomId):
    return _reveal_one(state, room_id)


def legacy_resolve_card_minimal(state: GameState, pid: PlayerId, card, cfg: Config, rng: Optional[RNG] = None):
    return _resolve_card_minimal(state, pid, card, cfg, rng)


def legacy_resolve_event(state: GameState, pid: PlayerId, event_id: str, cfg: Config, rng: RNG, card_prefix: str = "EVENT"):
    return _resolve_event(state, pid, event_id, cfg, rng, card_prefix=card_prefix)


def legacy_on_player_enters_room(state: GameState, pid: PlayerId, room: RoomId) -> None:
    _on_player_enters_room(state, pid, room)


def legacy_on_monster_enters_room(state: GameState, room: RoomId) -> None:
    _on_monster_enters_room(state, room)


def legacy_monster_phase(state: GameState, cfg: Config) -> None:
    _monster_phase(state, cfg)


def legacy_move_monsters(state: GameState, cfg: Config) -> None:
    _move_monsters(state, cfg)


def legacy_current_false_king_floor(state: GameState) -> int | None:
    return _current_false_king_floor(state)


def legacy_sync_crown_holder(state: GameState) -> None:
    _sync_crown_holder(state)


def legacy_presence_damage_for_round(round_n: int) -> int:
    return _presence_damage_for_round(round_n)


def legacy_shuffle_all_room_decks(state: GameState, rng: RNG) -> None:
    _shuffle_all_room_decks(state, rng)


def legacy_expel_players_from_floor(state: GameState, floor: int) -> None:
    _expel_players_from_floor(state, floor)


def legacy_attract_players_to_floor(state: GameState, floor: int) -> None:
    _attract_players_to_floor(state, floor)


def legacy_expel_players_from_floor_except_fk(state: GameState, floor: int, fk_floor: int | None) -> None:
    _expel_players_from_floor_except_fk(state, floor, fk_floor)


def legacy_attract_players_to_floor_except_fk(state: GameState, floor: int, fk_floor: int | None) -> None:
    _attract_players_to_floor_except_fk(state, floor, fk_floor)


def legacy_roll_stairs(state: GameState, rng: RNG) -> None:
    _roll_stairs(state, rng)


def legacy_false_king_check(state: GameState, rng: RNG, cfg: Config) -> None:
    _false_king_check(state, rng, cfg)


def legacy_end_of_round_checks(state: GameState, cfg: Config) -> None:
    _end_of_round_checks(state, cfg)


def legacy_advance_turn_or_king(state: GameState) -> None:
    _advance_turn_or_king(state)


def legacy_start_new_round(state: GameState) -> None:
    _start_new_round(state)

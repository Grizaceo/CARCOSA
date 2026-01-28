from __future__ import annotations

from typing import Dict, Iterable, Optional

from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId


def make_room(
    room_id: str,
    cards: Optional[Iterable[str]] = None,
    special_card_id: Optional[str] = None,
    special_revealed: bool = False,
    special_destroyed: bool = False,
) -> RoomState:
    deck = DeckState(cards=list(cards) if cards is not None else [])
    return RoomState(
        room_id=RoomId(room_id),
        deck=deck,
        special_card_id=special_card_id,
        special_revealed=special_revealed,
        special_destroyed=special_destroyed,
    )


def make_player(
    player_id: str,
    room: str,
    sanity: int = 5,
    sanity_max: int = 5,
    role_id: Optional[str] = None,
    keys: int = 0,
    objects: Optional[Iterable[str]] = None,
    object_charges: Optional[Dict[str, int]] = None,
) -> PlayerState:
    player = PlayerState(
        player_id=PlayerId(player_id),
        room=RoomId(room),
        sanity=sanity,
        sanity_max=sanity_max,
        keys=keys,
    )
    if role_id:
        player.role_id = role_id
    if objects:
        player.objects = list(objects)
    if object_charges:
        player.object_charges = dict(object_charges)
    return player


def _to_player_id(value) -> PlayerId:
    return PlayerId(value)


def make_game_state(
    players: Optional[Dict[str, dict]] = None,
    rooms: Optional[Dict[str, dict] | Iterable[str]] = None,
    round: int = 1,
    phase: str = "PLAYER",
    king_floor: int = 1,
    turn_order: Optional[Iterable[str]] = None,
    remaining_actions: Optional[Dict[str, int]] = None,
    turn_pos: int = 0,
    starter_pos: int = 0,
) -> GameState:
    if rooms is None:
        rooms = ["F1_R1"]

    rooms_dict: Dict[RoomId, RoomState] = {}
    if isinstance(rooms, dict):
        for room_id, cfg in rooms.items():
            cfg = cfg or {}
            rooms_dict[RoomId(room_id)] = make_room(room_id, **cfg)
    else:
        for room_id in rooms:
            rooms_dict[RoomId(room_id)] = make_room(room_id)

    if players is None:
        players = {"P1": {"room": "F1_R1"}}

    players_dict: Dict[PlayerId, PlayerState] = {}
    for pid, cfg in players.items():
        cfg = cfg or {}
        room = cfg.get("room", "F1_R1")
        players_dict[PlayerId(pid)] = make_player(
            player_id=pid,
            room=room,
            sanity=cfg.get("sanity", 5),
            sanity_max=cfg.get("sanity_max", 5),
            role_id=cfg.get("role_id"),
            keys=cfg.get("keys", 0),
            objects=cfg.get("objects"),
            object_charges=cfg.get("object_charges"),
        )

    if turn_order is None:
        turn_order = list(players.keys())
    turn_order_ids = [_to_player_id(pid) for pid in turn_order]

    if remaining_actions is None:
        remaining_actions_ids = {pid: 2 for pid in turn_order_ids}
    else:
        remaining_actions_ids = {_to_player_id(pid): count for pid, count in remaining_actions.items()}

    state = GameState(
        round=round,
        players=players_dict,
        rooms=rooms_dict,
        phase=phase,
        king_floor=king_floor,
        turn_order=turn_order_ids,
        remaining_actions=remaining_actions_ids,
        turn_pos=turn_pos,
        starter_pos=starter_pos,
    )
    return state


__all__ = [
    "make_room",
    "make_player",
    "make_game_state",
]

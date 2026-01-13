from __future__ import annotations
from typing import List

from engine.actions import Action, ActionType
from engine.board import neighbors, floor_of, is_corridor, corridor_id
from engine.boxes import active_deck_for_room
from engine.state import GameState
from engine.types import PlayerId, RoomId


def _current_player_id(state: GameState) -> PlayerId:
    return state.turn_order[state.turn_pos]


def get_legal_actions(state: GameState, actor: str) -> List[Action]:
    if state.game_over:
        return []

    if state.phase == "PLAYER":
        pid = _current_player_id(state)
        if actor != str(pid):
            return []

        if state.remaining_actions.get(pid, 0) <= 0:
            return [Action(actor=str(pid), type=ActionType.END_TURN, data={})]

        p = state.players[pid]
        acts: List[Action] = []

        # MOVE a vecinos del nodo actual (misma planta: pasillo <-> habitaciones)
        for nb in neighbors(p.room):
            acts.append(Action(actor=str(pid), type=ActionType.MOVE, data={"to": str(nb)}))

        # MOVE especial: si estás en la habitación que tiene escaleras en tu piso,
        # puedes moverte a la habitación con escalera del piso arriba/abajo (según canon P0).
        f = floor_of(p.room)
        if p.room == state.stairs.get(f):
            if f > 1:
                dest_stair = state.stairs.get(f - 1)
                if dest_stair:
                    acts.append(Action(actor=str(pid), type=ActionType.MOVE, data={"to": str(dest_stair)}))
            if f < 3:
                dest_stair = state.stairs.get(f + 1)
                if dest_stair:
                    acts.append(Action(actor=str(pid), type=ActionType.MOVE, data={"to": str(dest_stair)}))

        # SEARCH solo en habitación con mazo activo
        deck = active_deck_for_room(state, p.room)
        if deck is not None and deck.remaining() > 0:
            acts.append(Action(actor=str(pid), type=ActionType.SEARCH, data={}))

        # MEDITATE no se puede en pasillo del piso del Rey, salvo si el jugador esta en -5.
        in_king_corridor = is_corridor(p.room) and floor_of(p.room) == state.king_floor
        if not in_king_corridor or p.at_minus5:
            acts.append(Action(actor=str(pid), type=ActionType.MEDITATE, data={}))

        acts.append(Action(actor=str(pid), type=ActionType.END_TURN, data={}))
        return acts

    if state.phase == "KING":
        if actor != "KING":
            return []
        # NOTA: El piso se determina por ruleta d4 (RNG), no por acción del policy.
        # Generamos 3 acciones (placeholder) pero el piso se decide aleatoriamente en transition.py.
        acts: List[Action] = []
        for floor in (1, 2, 3):
            acts.append(Action(actor="KING", type=ActionType.KING_ENDROUND, data={}))
        return acts

    return []

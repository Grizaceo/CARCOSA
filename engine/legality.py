from __future__ import annotations
from typing import List

from engine.actions import Action, ActionType
from engine.board import neighbors, floor_of, is_corridor, corridor_id
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
        # puedes moverte al pasillo del piso arriba/abajo (mínimo operativo para simulación).
        f = floor_of(p.room)
        if p.room == state.stairs.get(f):
            if f > 1:
                acts.append(Action(actor=str(pid), type=ActionType.MOVE, data={"to": str(corridor_id(f - 1))}))
            if f < 3:
                acts.append(Action(actor=str(pid), type=ActionType.MOVE, data={"to": str(corridor_id(f + 1))}))

        # SEARCH solo en habitación
        if not is_corridor(p.room):
            r = state.rooms.get(p.room)
            if r and r.deck.remaining() > 0:
                acts.append(Action(actor=str(pid), type=ActionType.SEARCH, data={}))

        # MEDITATE no se puede en pasillo del piso del Rey (regla base)
        if not (is_corridor(p.room) and floor_of(p.room) == state.king_floor):
            acts.append(Action(actor=str(pid), type=ActionType.MEDITATE, data={}))

        # Regla: No puedes meditar en el pasillo del piso donde está el Rey
        if p.room == corridor_id(state.king_floor):
            acts = [a for a in acts if a.type != ActionType.MEDITATE]

        acts.append(Action(actor=str(pid), type=ActionType.END_TURN, data={}))
        return acts

    if state.phase == "KING":
        if actor != "KING":
            return []
        acts: List[Action] = []
        for floor in (1, 2, 3):
            for d6 in (1, 2, 3, 4, 5, 6):
                acts.append(Action(actor="KING", type=ActionType.KING_ENDROUND, data={"floor": floor, "d6": d6}))
        return acts

    return []

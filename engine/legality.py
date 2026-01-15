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

        # MEDITATE no se puede en pasillo del piso del Rey.
        if not (is_corridor(p.room) and floor_of(p.room) == state.king_floor):
            acts.append(Action(actor=str(pid), type=ActionType.MEDITATE, data={}))

        # SACRIFICE: solo si status "SCARED" o sanity <= S_LOSS (si la regla lo permite)
        # Por ahora lo permitimos sisanity -5 (o cerca) para testear
        if p.sanity <= -5 or p.at_minus5:
             acts.append(Action(actor=str(pid), type=ActionType.SACRIFICE, data={}))

        # ESCAPE_TRAPPED: solo si tiene status "TRAPPED"
        if any(st.status_id == "TRAPPED" for st in p.statuses):
             acts.append(Action(actor=str(pid), type=ActionType.ESCAPE_TRAPPED, data={}))

        # ===== B2: MOTEMEY (buy/sell) =====
        # Disponible si actor está en habitación MOTEMEY o evento es activo
        motemey_room_pattern = "_MOTEMEY"
        is_in_motemey = motemey_room_pattern in str(p.room)
        
        if is_in_motemey or state.motemey_event_active:
            # BUY: requiere sanidad >= 2 para poder pagar
            if p.sanity >= 2:
                acts.append(Action(actor=str(pid), type=ActionType.USE_MOTEMEY_BUY, data={"chosen_index": 0}))
            
            # SELL: requiere tener al menos un objeto
            if p.objects:
                for idx, item in enumerate(p.objects):
                    acts.append(Action(actor=str(pid), type=ActionType.USE_MOTEMEY_SELL, data={"item_name": item}))

        # ===== B4: PUERTAS AMARILLO =====
        # Disponible si actor está en habitación PUERTAS y existe al menos otro jugador
        puertas_room_pattern = "_PUERTAS"
        is_in_puertas = puertas_room_pattern in str(p.room)
        other_players = [p2_id for p2_id in state.players if p2_id != pid]
        
        if is_in_puertas and other_players:
            for target_pid in other_players:
                acts.append(Action(actor=str(pid), type=ActionType.USE_YELLOW_DOORS, data={"target_player": str(target_pid)}))

        # ===== B5: PEEK =====
        # Disponible si actor está en habitación PEEK, no ha usado esta ronda, y existen al menos 2 rooms distintos
        peek_room_pattern = "_PEEK"
        is_in_peek = peek_room_pattern in str(p.room)
        peek_used = state.peek_used_this_turn.get(pid, False)
        
        if is_in_peek and not peek_used and len(state.rooms) >= 2:
            # Offrezamos 2 cuartos cualquiera distintos
            room_ids = list(state.rooms.keys())
            for i, room_a in enumerate(room_ids):
                for room_b in room_ids[i+1:]:
                    if room_a != room_b:
                        acts.append(Action(actor=str(pid), type=ActionType.USE_PEEK_ROOMS, data={"room_a": str(room_a), "room_b": str(room_b)}))

        # ===== B6: ARMERÍA =====
        # Disponible si actor está en habitación ARMERÍA y armería no está destruida
        armory_room_pattern = "_ARMERY"
        is_in_armory = armory_room_pattern in str(p.room)
        armory_destroyed = state.flags.get(f"ARMORY_DESTROYED_{p.room}", False)
        
        if is_in_armory and not armory_destroyed:
            # DROP: si tiene objetos y hay espacio (< 2)
            current_storage_count = len(state.armory_storage.get(p.room, []))
            if p.objects and current_storage_count < 2:
                for obj in p.objects:
                    acts.append(Action(actor=str(pid), type=ActionType.USE_ARMORY_DROP, data={"item_name": obj}))
            
            # TAKE: si hay ítems en almacenamiento
            if current_storage_count > 0:
                acts.append(Action(actor=str(pid), type=ActionType.USE_ARMORY_TAKE, data={}))

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

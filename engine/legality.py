from __future__ import annotations
from typing import List, Optional

from engine.actions import Action, ActionType
from engine.board import neighbors, floor_of, is_corridor, corridor_id
from engine.boxes import active_deck_for_room
from engine.state import GameState, RoomState
from engine.types import PlayerId, RoomId


def _get_special_room_type(state: GameState, room_id: RoomId) -> Optional[str]:
    """
    Helper: Retorna el tipo de habitación especial en una ubicación, o None.
    Usa RoomState.special_card_id en lugar de sufijos en RoomId.

    Solo considera una habitación especial como "activa" si:
    - Tiene special_card_id definido
    - Ha sido revelada (special_revealed=True)
    - No ha sido destruida (special_destroyed=False)
    """
    room_state = state.rooms.get(room_id)
    if room_state is None:
        return None
    # Solo considerar si está revelada y no destruida
    if (room_state.special_card_id and
        room_state.special_revealed and
        not room_state.special_destroyed):
        return room_state.special_card_id
    return None


def _current_player_id(state: GameState) -> PlayerId:
    return state.turn_order[state.turn_pos]


def _is_paranoia_move_legal(state: GameState, pid: PlayerId, to_room: RoomId) -> bool:
    """
    FASE 3: Verifica si un movimiento es legal considerando el estado PARANOIA.

    PARANOIA: No puede estar en misma habitación/pasillo que otra Pobre Alma.
    - Si el jugador tiene PARANOIA, no puede entrar donde hay otros
    - Si hay alguien con PARANOIA en la habitación destino, nadie puede entrar
    """
    p = state.players[pid]

    # Si el jugador tiene PARANOIA, no puede entrar donde hay otros
    if any(st.status_id == "PARANOIA" for st in p.statuses):
        for other_pid, other in state.players.items():
            if other_pid != pid and other.room == to_room:
                return False

    # Si hay alguien con PARANOIA en la habitación destino, nadie puede entrar
    for other_pid, other in state.players.items():
        if other_pid != pid and other.room == to_room:
            if any(st.status_id == "PARANOIA" for st in other.statuses):
                return False

    return True


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
            # FASE 3: Filtrar por PARANOIA
            if _is_paranoia_move_legal(state, pid, RoomId(nb)):
                acts.append(Action(actor=str(pid), type=ActionType.MOVE, data={"to": str(nb)}))

        # MOVE especial: si estás en la habitación que tiene escaleras en tu piso,
        # puedes moverte a la habitación con escalera del piso arriba/abajo (según canon P0).
        f = floor_of(p.room)
        if p.room == state.stairs.get(f):
            if f > 1:
                dest_stair = state.stairs.get(f - 1)
                if dest_stair:
                    # FASE 3: Filtrar por PARANOIA
                    if _is_paranoia_move_legal(state, pid, dest_stair):
                        acts.append(Action(actor=str(pid), type=ActionType.MOVE, data={"to": str(dest_stair)}))
            if f < 3:
                dest_stair = state.stairs.get(f + 1)
                if dest_stair:
                    # FASE 3: Filtrar por PARANOIA
                    if _is_paranoia_move_legal(state, pid, dest_stair):
                        acts.append(Action(actor=str(pid), type=ActionType.MOVE, data={"to": str(dest_stair)}))

        # SEARCH solo en habitación con mazo activo
        deck = active_deck_for_room(state, p.room)
        if deck is not None and deck.remaining() > 0:
            acts.append(Action(actor=str(pid), type=ActionType.SEARCH, data={}))

        # MEDITATE no se puede en pasillo del piso del Rey.
        # FASE 3: VANIDAD bloquea MEDITATE
        has_vanidad = any(st.status_id == "VANIDAD" for st in p.statuses)
        if not (is_corridor(p.room) and floor_of(p.room) == state.king_floor) and not has_vanidad:
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
        is_in_motemey = _get_special_room_type(state, p.room) == "MOTEMEY"

        if is_in_motemey or state.motemey_event_active:
            # CORRECCIÓN D: Sistema de elección de 2 pasos
            # Si hay pending_choice para este jugador: solo CHOOSE es legal
            if state.pending_motemey_choice and str(pid) in state.pending_motemey_choice:
                # Paso 2: Elegir carta (0 o 1)
                acts.append(Action(actor=str(pid), type=ActionType.USE_MOTEMEY_BUY_CHOOSE, data={"chosen_index": 0}))
                acts.append(Action(actor=str(pid), type=ActionType.USE_MOTEMEY_BUY_CHOOSE, data={"chosen_index": 1}))
            else:
                # Paso 1: Iniciar compra (requiere sanidad >= 2)
                if p.sanity >= 2 and state.motemey_deck.remaining() >= 2:
                    acts.append(Action(actor=str(pid), type=ActionType.USE_MOTEMEY_BUY_START, data={}))

            # SELL: requiere tener al menos un objeto (siempre disponible)
            if p.objects:
                for idx, item in enumerate(p.objects):
                    acts.append(Action(actor=str(pid), type=ActionType.USE_MOTEMEY_SELL, data={"item_name": item}))

        # ===== B4: PUERTAS AMARILLO =====
        # Disponible si actor está en habitación PUERTAS y existe al menos otro jugador
        is_in_puertas = _get_special_room_type(state, p.room) == "PUERTAS"
        other_players = [p2_id for p2_id in state.players if p2_id != pid]

        if is_in_puertas and other_players:
            for target_pid in other_players:
                acts.append(Action(actor=str(pid), type=ActionType.USE_YELLOW_DOORS, data={"target_player": str(target_pid)}))

        # ===== B5: PEEK =====
        # Disponible si actor está en habitación PEEK, no ha usado esta ronda, y existen al menos 2 rooms distintos
        is_in_peek = _get_special_room_type(state, p.room) == "PEEK"
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
        is_in_armory = _get_special_room_type(state, p.room) == "ARMERY"
        # La destrucción ya está manejada por special_destroyed en _get_special_room_type
        # pero mantenemos compatibilidad con flag por si acaso
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

        # ===== B3: CÁMARA LETAL =====
        # P1 - FASE 1.5.4: Ritual para obtener 7ª llave
        # Disponible si:
        # - Actor está en habitación CÁMARA_LETAL
        # - CAMARA_LETAL_PRESENT (sorteada en setup)
        # - Ritual no completado todavía
        # - Hay exactamente 2 jugadores en la habitación
        # - Habitación no está destruida
        if p.room in state.rooms:
            room_state = state.rooms[p.room]
            is_camara_letal = (room_state.special_card_id == "CAMARA_LETAL")
            camara_letal_present = state.flags.get("CAMARA_LETAL_PRESENT", False)
            ritual_completed = state.flags.get("CAMARA_LETAL_RITUAL_COMPLETED", False)
            room_destroyed = room_state.special_destroyed

            if (is_camara_letal and camara_letal_present and
                not ritual_completed and not room_destroyed):
                # Contar jugadores en la habitación
                players_in_room = [
                    p_id for p_id, player in state.players.items()
                    if player.room == p.room
                ]

                if len(players_in_room) == 2:
                    acts.append(Action(
                        actor=str(pid),
                        type=ActionType.USE_CAMARA_LETAL_RITUAL,
                        data={}
                    ))

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

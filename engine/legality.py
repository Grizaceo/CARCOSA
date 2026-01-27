from __future__ import annotations
from typing import List, Optional

from engine.actions import Action, ActionType
from engine.board import neighbors, floor_of, is_corridor, corridor_id
from engine.boxes import active_deck_for_room
from engine.state import GameState, RoomState
from engine.types import PlayerId, RoomId
from engine.effects.states_canonical import has_status
from engine.objects import is_soulbound
from engine.inventory import get_inventory_limits
from engine.setup import normalize_room_type


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
        return normalize_room_type(room_state.special_card_id)
    return None


def _current_player_id(state: GameState) -> PlayerId:
    return state.turn_order[state.turn_pos]


def _is_movement_blocked(state: GameState, pid: PlayerId) -> bool:
    """
    Verifica si el jugador tiene movimiento bloqueado.
    
    MOVIMIENTO_BLOQUEADO: Aplicado por Reina Helada en turno de entrada.
    Solo afecta a jugadores que estaban presentes cuando entró.
    """
    return pid in state.movement_blocked_players


def _is_paranoia_move_legal(state: GameState, pid: PlayerId, to_room: RoomId) -> bool:
    """
    Verifica si un movimiento es legal considerando el estado PARANOIA.

    PARANOIA: No puede estar en misma habitación/pasillo que otra Pobre Alma.
    - Si el jugador tiene PARANOIA, no puede entrar donde hay otros
    - Si hay alguien con PARANOIA en la habitación destino, nadie puede entrar
    """
    p = state.players[pid]

    # Si el jugador tiene PARANOIA, no puede entrar donde hay otros (habitaciones Y pasillo)
    if has_status(p, "PARANOIA"):
        for other_pid, other in state.players.items():
            if other_pid != pid and other.room == to_room:
                return False

    # Si hay alguien con PARANOIA en la habitación destino, nadie puede entrar
    for other_pid, other in state.players.items():
        if other_pid != pid and other.room == to_room:
            if has_status(other, "PARANOIA"):
                return False

    return True


def get_legal_actions(state: GameState, actor: str) -> List[Action]:
    if state.game_over:
        return []

    # CANON Fix #A: Sacrifice Interrupt
    # Si hay un chequeo de sacrificio pendiente, solo el jugador afectado puede actuar.
    # Debe elegir entre SACRIFICE o ACCEPT_SACRIFICE.
    pending_sacrifice_pid = state.flags.get("PENDING_SACRIFICE_CHECK")
    if pending_sacrifice_pid:
        if actor == pending_sacrifice_pid:
            p = state.players[PlayerId(actor)]
            options = []
            # SACRIFICE options
            _, obj_slots = get_inventory_limits(p)
            if obj_slots > 0:
                # Si al reducir slots habría overflow, permitir elegir qué descartar
                non_soul = [obj for obj in p.objects if not is_soulbound(obj)]
                new_slots = max(0, obj_slots - 1)
                if len(non_soul) > new_slots:
                    for obj in non_soul:
                        options.append(Action(actor=actor, type=ActionType.SACRIFICE, data={"mode": "OBJECT_SLOT", "discard_object_id": obj}))
                else:
                    options.append(Action(actor=actor, type=ActionType.SACRIFICE, data={"mode": "OBJECT_SLOT"}))

            if p.sanity_max is not None and p.sanity_max > -1:
                options.append(Action(actor=actor, type=ActionType.SACRIFICE, data={"mode": "SANITY_MAX"}))

            # Always allow ACCEPT
            options.append(Action(actor=actor, type=ActionType.ACCEPT_SACRIFICE, data={}))
            return options
        else:
            return []

    # Hallway Peek Pending (Check before other actions)
    if state.flags.get("PENDING_HALLWAY_PEEK") == actor:
        acts = []
        p = state.players[PlayerId(actor)]
        current_floor = floor_of(p.room)
        
        # Add PEEK action for each room on this floor
        for i in range(1, 5):
            rid = RoomId(f"F{current_floor}_R{i}")
            if rid in state.rooms:
                 deck = active_deck_for_room(state, rid)
                 if deck and deck.remaining() > 0:
                     acts.append(Action(actor=actor, type=ActionType.PEEK_ROOM_DECK, data={"room_id": str(rid)}))
        
        # Always allow SKIP
        acts.append(Action(actor=actor, type=ActionType.SKIP_PEEK, data={}))
        return acts

    # Motemey pending choice: solo CHOOSE es legal
    if state.pending_motemey_choice and actor in state.pending_motemey_choice:
        acts = [
            Action(actor=actor, type=ActionType.USE_MOTEMEY_BUY_CHOOSE, data={"chosen_index": 0}),
            Action(actor=actor, type=ActionType.USE_MOTEMEY_BUY_CHOOSE, data={"chosen_index": 1}),
            Action(actor=actor, type=ActionType.END_TURN, data={}),
        ]
        # SANIDAD puede descartarse incluso en este estado
        if actor in state.players and has_status(state.players[PlayerId(actor)], "SANIDAD"):
            acts.insert(0, Action(actor=actor, type=ActionType.DISCARD_SANIDAD, data={}))
        return acts

    if state.phase == "PLAYER":
        pid = _current_player_id(state)
        if actor != str(pid):
            return []

        p = state.players[pid]
        if state.remaining_actions.get(pid, 0) <= 0:
            acts = [Action(actor=str(pid), type=ActionType.END_TURN, data={})]
            if has_status(p, "SANIDAD"):
                acts.insert(0, Action(actor=str(pid), type=ActionType.DISCARD_SANIDAD, data={}))
            return acts

        acts: List[Action] = []
        
        # CANON Fix: TRAPPED State blocks ALL actions except Escape
        if has_status(p, "TRAPPED"):
            # Solo permitir ESCAPE_TRAPPED
            acts.append(Action(actor=str(pid), type=ActionType.ESCAPE_TRAPPED, data={}))
            return acts
        # MOVIMIENTO_BLOQUEADO: Reina Helada bloquea movimiento
        movement_allowed = not _is_movement_blocked(state, pid)

        # MOVE a vecinos del nodo actual (misma planta: pasillo <-> habitaciones)
        for nb in neighbors(p.room):
            # MOVIMIENTO_BLOQUEADO y PARANOIA bloquean movimiento
            if movement_allowed and _is_paranoia_move_legal(state, pid, RoomId(nb)):
                acts.append(Action(actor=str(pid), type=ActionType.MOVE, data={"to": str(nb)}))

        # MOVE especial: si estás en la habitación que tiene escaleras en tu piso,
        # puedes moverte a la habitación con escalera del piso arriba/abajo (según canon P0).
        f = floor_of(p.room)
        if p.room == state.stairs.get(f):
            if f > 1:
                dest_stair = state.stairs.get(f - 1)
                if dest_stair:
                    # MOVIMIENTO_BLOQUEADO y PARANOIA bloquean movimiento
                    if movement_allowed and _is_paranoia_move_legal(state, pid, dest_stair):
                        acts.append(Action(actor=str(pid), type=ActionType.MOVE, data={"to": str(dest_stair)}))
            if f < 3:
                dest_stair = state.stairs.get(f + 1)
                if dest_stair:
                    # MOVIMIENTO_BLOQUEADO y PARANOIA bloquean movimiento
                    if movement_allowed and _is_paranoia_move_legal(state, pid, dest_stair):
                        acts.append(Action(actor=str(pid), type=ActionType.MOVE, data={"to": str(dest_stair)}))

        # SEARCH solo en habitación con mazo activo
        deck = active_deck_for_room(state, p.room)
        if deck is not None and deck.remaining() > 0:
            acts.append(Action(actor=str(pid), type=ActionType.SEARCH, data={}))

        # MEDITATE no se puede en pasillo del piso del Rey.
        # Nota: VANIDAD no bloquea MEDITATE, solo el Salón de Belleza
        # TANK: Otros no pueden meditar en la habitación del Tank
        can_meditate = True
        if is_corridor(p.room) and floor_of(p.room) == state.king_floor:
            can_meditate = False
        else:
            # Verificar si hay un Tank en la habitación
            for other_pid, other in state.players.items():
                if other_pid != pid and other.room == p.room:
                    if getattr(other, "role_id", "") == "TANK":
                        can_meditate = False  # Tank bloquea meditación de otros
                        break
        
        if can_meditate:
            acts.append(Action(actor=str(pid), type=ActionType.MEDITATE, data={}))

        # SANIDAD: puede descartarse gratis para eliminar todos los estados
        if has_status(p, "SANIDAD"):
            acts.append(Action(actor=str(pid), type=ActionType.DISCARD_SANIDAD, data={}))

        if any(st.status_id == "TRAPPED" for st in p.statuses):
             acts.append(Action(actor=str(pid), type=ActionType.ESCAPE_TRAPPED, data={}))

        # ===== B2: MOTEMEY (buy/sell) =====
        # Disponible si actor está en habitación MOTEMEY o evento es activo
        is_in_motemey = _get_special_room_type(state, p.room) == "MOTEMEY"

        if is_in_motemey or state.motemey_event_active:
            # Paso 1: Iniciar compra (requiere sanidad >= 2)
            if p.sanity >= 2 and state.motemey_deck.remaining() >= 2:
                acts.append(Action(actor=str(pid), type=ActionType.USE_MOTEMEY_BUY_START, data={}))
                # Legacy one-step buy (compatibilidad con clientes antiguos)
                acts.append(Action(actor=str(pid), type=ActionType.USE_MOTEMEY_BUY, data={}))

            # SELL: requiere tener al menos un objeto (siempre disponible)
            if p.objects:
                for item in p.objects:
                    if not is_soulbound(item):
                        acts.append(Action(actor=str(pid), type=ActionType.USE_MOTEMEY_SELL, data={"item_name": item}))

        # ===== B4: PUERTAS AMARILLO =====
        # Disponible si actor está en habitación PUERTAS y existe al menos otro jugador
        # Usar normalización o ID canónico
        room_type = _get_special_room_type(state, p.room)
        is_in_puertas = room_type == "PUERTAS_AMARILLO"
        other_players = [p2_id for p2_id in state.players if p2_id != pid]

        if is_in_puertas and other_players:
            for target_pid in other_players:
                acts.append(Action(actor=str(pid), type=ActionType.USE_YELLOW_DOORS, data={"target_player": str(target_pid)}))

        # ===== B5: TABERNA =====
        # CANON: Solo habitaciones (NO pasillos), 2 distintas, 1x turno
        room_type = _get_special_room_type(state, p.room)
        is_in_taberna = room_type == "TABERNA"
        taberna_used = state.taberna_used_this_turn.get(pid, False)

        if is_in_taberna and not taberna_used:
            # CANON: Solo habitaciones, NO pasillos
            valid_rooms = [rid for rid in state.rooms.keys() if not is_corridor(rid)]
            if len(valid_rooms) >= 2:
                for i, room_a in enumerate(valid_rooms):
                    for room_b in valid_rooms[i+1:]:
                        if room_a != room_b:
                            acts.append(Action(actor=str(pid), type=ActionType.USE_TABERNA_ROOMS, data={"room_a": str(room_a), "room_b": str(room_b)}))

        # ===== B6: ARMERÍA =====
        # Disponible si actor está en habitación ARMERÍA y armería no está destruida
        room_type = _get_special_room_type(state, p.room)
        is_in_armory = room_type == "ARMERIA"
        # La destrucción ya está manejada por special_destroyed en _get_special_room_type
        # pero mantenemos compatibilidad con flag por si acaso
        armory_destroyed = state.flags.get(f"ARMORY_DESTROYED_{p.room}", False)

        if is_in_armory and not armory_destroyed:
            # CANON: Storage permite hasta 2 ítems en total (objetos y llaves)
            current_storage_count = len(state.armory_storage.get(p.room, []))
            
            # DROP OBJECTS: si tiene objetos y hay espacio (< 2)
            if p.objects and current_storage_count < 2:
                for obj in p.objects:
                    if not is_soulbound(obj):
                        acts.append(Action(actor=str(pid), type=ActionType.USE_ARMORY_DROP, data={"item_name": obj, "item_type": "object"}))

            # DROP KEYS: si tiene llaves y hay espacio (< 2)
            if p.keys > 0 and current_storage_count < 2:
                acts.append(Action(actor=str(pid), type=ActionType.USE_ARMORY_DROP, data={"item_name": "KEY", "item_type": "key"}))

            # TAKE: si hay ítems en almacenamiento
            if current_storage_count > 0:
                acts.append(Action(actor=str(pid), type=ActionType.USE_ARMORY_TAKE, data={}))

        # ===== OBJETOS (contundente / escaleras portÃ¡tiles) =====
        # Contundente: solo si hay monstruo en la sala
        if "BLUNT" in p.objects:
            if any(m.room == p.room for m in state.monsters):
                acts.append(Action(actor=str(pid), type=ActionType.USE_BLUNT, data={}))

        # Escalera portÃ¡til: moverse +/-1 piso (respeta bloqueo de movimiento)
        if "PORTABLE_STAIRS" in p.objects and movement_allowed:
            f = floor_of(p.room)
            if f > 1:
                acts.append(Action(actor=str(pid), type=ActionType.USE_PORTABLE_STAIRS, data={"direction": "DOWN"}))
            if f < 3:
                acts.append(Action(actor=str(pid), type=ActionType.USE_PORTABLE_STAIRS, data={"direction": "UP"}))

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
            is_camara_letal = (normalize_room_type(room_state.special_card_id or "") == "CAMARA_LETAL")
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

        # ===== B1: MONASTERIO DE LOCURA (Capilla) =====
        if p.room in state.rooms:
            room_state = state.rooms[p.room]
            is_monasterio = (normalize_room_type(room_state.special_card_id or "") == "MONASTERIO_LOCURA")
            room_destroyed = room_state.special_destroyed
            if is_monasterio and not room_destroyed:
                acts.append(Action(actor=str(pid), type=ActionType.USE_CAPILLA, data={}))

        # ===== B7: SALÓN DE BELLEZA =====
        if p.room in state.rooms:
            room_state = state.rooms[p.room]
            is_salon = (normalize_room_type(room_state.special_card_id or "") == "SALON_BELLEZA")
            room_destroyed = room_state.special_destroyed
            if is_salon and not room_destroyed:
                # Si tiene VANIDAD ya no puede usarlo (canon check)
                if not has_status(p, "VANIDAD"):
                    acts.append(Action(actor=str(pid), type=ActionType.USE_SALON_BELLEZA, data={}))

        # ===== FASE 1: Habilidad del Healer =====
        # Healer puede sacrificar 1 cordura propia para:
        # - Dar +2 cordura a OTROS
        # - Obtener ILUMINADO o SANIDAD (a elección)
        # Requiere: cordura >= 1, al menos otro jugador
        if getattr(p, "role_id", "") == "HEALER" and p.sanity >= 1:
            other_players = [pid2 for pid2 in state.players if pid2 != pid]
            if len(other_players) > 0:
                acts.append(Action(
                    actor=str(pid),
                    type=ActionType.USE_HEALER_HEAL,
                    data={}  # La elección de estado se hace en el handler
                ))

        # ===== FASE 4: USE_ATTACH_TALE (Unir cuento al libro) =====
        # Requiere: Tener el Libro (BOOK_CHAMBERS) y al menos un Cuento (TALE_*)
        if "BOOK_CHAMBERS" in p.objects or "CHAMBERS_BOOK" in p.objects:
            for obj in p.objects:
                if obj.startswith("TALE_"):
                    # Es un cuento, podemos unirlo
                    acts.append(Action(actor=str(pid), type=ActionType.USE_ATTACH_TALE, data={"tale_id": obj}))

        acts.append(Action(actor=str(pid), type=ActionType.END_TURN, data={}))
        return acts

    if state.phase == "KING":
        if actor != "KING":
            return []
        # NOTA: El piso se determina por ruleta d4 (RNG), no por acción del policy.
        # CANON Fix #H: Single action for King phase.
        # UI/AI solo debe llamar a esta acción única para resolver la fase del Rey.
        return [Action(actor="KING", type=ActionType.KING_ENDROUND, data={})]

    return []

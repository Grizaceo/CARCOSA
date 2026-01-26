from __future__ import annotations
from typing import Optional

from engine.actions import Action, ActionType
from engine.board import corridor_id, floor_of, ruleta_floor, rotate_boxes, rotate_boxes_intra_floor, get_next_move_to_targets, get_next_move_away_from_targets
from engine.boxes import active_deck_for_room, sync_room_decks_from_boxes
from engine.config import Config
from engine.legality import get_legal_actions
from engine.rng import RNG
from engine.state import GameState, StatusInstance, ensure_canonical_rooms
from engine.types import PlayerId, RoomId, CardId
from engine.roles import get_scout_actions, brawler_blunt_free
from engine.objects import use_object, get_effective_sanity_max, get_max_keys_capacity, is_soulbound, OBJECT_CATALOG
from engine.inventory import get_inventory_limits
from engine.inventory import consume_object, add_object
from engine.effects.states_canonical import has_status, decrement_status_durations, remove_all_statuses
from engine.effects.event_utils import add_status

# Flag constant for sacrifice interrupt
PENDING_SACRIFICE_FLAG = "PENDING_SACRIFICE_CHECK"


def _sanity_cap(p) -> int:
    return get_effective_sanity_max(p)


def _heal(p, amount: int) -> None:
    p.sanity = min(p.sanity + amount, _sanity_cap(p))


def _get_base_keys_total(cfg) -> int:
    # Base: 5 en mazos + 1 en Motemey
    return int(getattr(cfg, "KEYS_TOTAL", 6))


def _available_sacrifice_options(p) -> dict:
    # Opciones de sacrificio disponibles
    obj_options = [obj for obj in p.objects if not is_soulbound(obj)]
    can_reduce_sanity = (p.sanity_max is not None and p.sanity_max > -1)
    _, current_slots = get_inventory_limits(p)
    can_reduce_object_slots = current_slots > 0
    return {
        "object_options": obj_options,
        "can_reduce_sanity": can_reduce_sanity,
        "can_reduce_object_slots": can_reduce_object_slots,
        "current_object_slots": current_slots,
    }


def _apply_sacrifice_choice(s: GameState, pid: PlayerId, cfg, choice: dict) -> None:
    p = s.players[pid]
    opts = _available_sacrifice_options(p)

    mode = (choice or {}).get("mode")
    if mode == "OBJECT_SLOT":
        if not opts["can_reduce_object_slots"]:
            raise ValueError("Sacrifice OBJECT_SLOT not available (no object slots to reduce).")

        # Penalidad permanente de slots
        p.object_slots_penalty = max(0, int(getattr(p, "object_slots_penalty", 0)) + 1)

        # Ajustar inventario si excede el nuevo límite
        _, obj_slots = get_inventory_limits(p)
        while True:
            non_soul = [obj for obj in p.objects if not is_soulbound(obj)]
            if len(non_soul) <= obj_slots:
                break
            # Si el jugador eligió qué descartar, priorizarlo
            drop = (choice or {}).get("discard_object_id")
            if drop not in non_soul:
                drop = non_soul[-1]
            p.objects.remove(drop)
            s.discard_pile.append(drop)

    elif mode == "SANITY_MAX":
        if not opts["can_reduce_sanity"]:
            raise ValueError("Sacrifice SANITY_MAX not available (sanity_max already at -1).")
        p.sanity_max = max(-1, int(p.sanity_max) - 1)
        if p.sanity > p.sanity_max:
            p.sanity = p.sanity_max
    else:
        # Si no se indicó modo, decidir solo si hay una opción
        if opts["object_options"] and not opts["can_reduce_sanity"]:
            _apply_sacrifice_choice(s, pid, cfg, {"mode": "OBJECT_SLOT"})
        elif opts["can_reduce_sanity"] and not opts["object_options"]:
            _apply_sacrifice_choice(s, pid, cfg, {"mode": "SANITY_MAX"})
        else:
            raise ValueError("Sacrifice choice requires explicit mode when multiple options exist.")

    # Al sacrificar, la cordura vuelve a 0 inmediatamente
    p.sanity = 0
    p.at_minus5 = False


def apply_sanity_loss(s, player, amount: int, cfg: Config = None, source: str = "GENERIC"):
    """
    Centralized sanity loss.
    - Applies 'VANIDAD' effect: +1 loss if player has VANIDAD.
    """
    if amount <= 0:
        return

    # Check for VANIDAD (+1 damage)
    if has_status(player, "VANIDAD"):
        amount += 1

    player.sanity -= amount

    # Tracking de golpe de gracia
    # Use passed cfg, or fallback to s.config if patched (legacy), or default -5
    limit = -5
    if cfg:
        limit = getattr(cfg, "S_LOSS", -5)
    elif hasattr(s, "config"):
        limit = getattr(s.config, "S_LOSS", -5)
        
    if player.sanity <= limit and amount > 0:
         actual_source = source or "UNKNOWN"
         s.last_sanity_loss_event = f"{actual_source} -> {player.player_id}"


def _get_effective_keys_total(s, cfg) -> int:
    """
    Retorna el total de llaves en juego (pool).
    Base: 6 (5 en mazos + 1 en Motemey).
    Si Cámara Letal está revelada: +1 (solo obtenible vía ritual).
    """
    base = _get_base_keys_total(cfg)
    # Buscar si existe cámara letal revelada
    for room in s.rooms.values():
        if room.special_card_id == "CAMARA_LETAL" and room.special_revealed:
            return base + 1
    return base


def _consume_action_if_needed(action_type: ActionType, cost_override: Optional[int] = None) -> int:
    """
    Determina el costo de acción de un ActionType.
    
    Respeta:
    - Acciones de movimiento/búsqueda/meditación: costo 1
    - Acciones de habitación especial (Motemey, Peek, Armería): costo 0
    - Puertas Amarillas: costo 1
    - SACRIFICE, ESCAPE_TRAPPED: costo 1
    - cost_override: si se pasa, prevalece (para excepciones como DPS)
    
    Returns:
        int: Número de acciones a descontar (0 o 1 usualmente)
    """
    if cost_override is not None:
        return cost_override
    
    # Acciones que NO consumen acción
    free_action_types = {
        ActionType.USE_MOTEMEY_BUY,
        ActionType.USE_MOTEMEY_SELL,
        ActionType.USE_MOTEMEY_BUY_START,
        ActionType.USE_MOTEMEY_BUY_CHOOSE,
        ActionType.USE_TABERNA_ROOMS,
        ActionType.USE_ARMORY_DROP,
        ActionType.USE_ARMORY_TAKE,
        ActionType.DISCARD_SANIDAD,
    }
    
    if action_type in free_action_types:
        return 0
    
    # Acciones que consumen 1
    paid_action_types = {
        ActionType.MOVE,
        ActionType.SEARCH,
        ActionType.MEDITATE,
        ActionType.SACRIFICE,
        ActionType.ESCAPE_TRAPPED,
        ActionType.USE_YELLOW_DOORS,
        ActionType.USE_HEALER_HEAL,
        ActionType.USE_BLUNT,
        ActionType.USE_PORTABLE_STAIRS,
        ActionType.USE_CAMARA_LETAL_RITUAL,
        ActionType.USE_CAPILLA,
        ActionType.USE_SALON_BELLEZA,
    }
    
    if action_type in paid_action_types:
        return 1
    
    # Default: no consume
    return 0


def _clamp_all_sanity(s, cfg):
    # -5 es piso: no se puede bajar más
    for pl in s.players.values():
        if pl.sanity < cfg.S_LOSS:
            pl.sanity = cfg.S_LOSS
        # cap superior (sanity_max) si existe
        cap = _sanity_cap(pl)
        if pl.sanity > cap:
            pl.sanity = cap


def _cap_monsters(s, cfg):
    cap = int(getattr(cfg, "MAX_MONSTERS_ON_BOARD", 0) or 0)
    if cap <= 0:
        return
    if isinstance(s.monsters, list):
        if len(s.monsters) > cap:
            s.monsters = s.monsters[:cap]
    else:
        try:
            if int(s.monsters) > cap:
                s.monsters = cap
        except (TypeError, ValueError):
            return


def _check_victory(s, cfg) -> bool:
    """
    Condición de VICTORIA canónica:
    - Todos los jugadores en UMBRAL_NODE
    - Con >= KEYS_TO_WIN llaves colectivas
    
    Se verifica al final de cada ronda.
    """
    if s.game_over:
        return False
    
    # Verificar que todos estén en UMBRAL_NODE
    all_in_umbral = all(
        str(p.room) == str(cfg.UMBRAL_NODE) for p in s.players.values()
    )
    if not all_in_umbral:
        return False
    
    # Contar llaves colectivas
    total_keys = sum(p.keys for p in s.players.values())
    if total_keys < int(cfg.KEYS_TO_WIN):
        return False
    
    # ¡Victoria!
    s.game_over = True
    s.outcome = "WIN"
    return True


def _check_defeat(s, cfg) -> bool:
    """
    Condiciones de DERROTA canónicas:
    1. Todos los jugadores en -5 cordura
    2. Solo quedan <= 3 llaves en juego
    """
    if s.game_over:
        return False
    
    # Condición 1: Todos en -5
    all_at_minus5 = all(
        p.sanity <= cfg.S_LOSS for p in s.players.values()
    )
    if all_at_minus5:
        s.game_over = True
        source = s.last_sanity_loss_event or "UNKNOWN"
        s.outcome = f"LOSE_ALL_MINUS5 ({source})"
        return True
    
    # Condición 2: <= KEYS_LOSE_THRESHOLD llaves en juego
    # Solo aplica si se han destruido llaves (keys_destroyed > 0)
    if s.keys_destroyed > 0:
        keys_total = _get_effective_keys_total(s, cfg)
        keys_threshold = getattr(cfg, "KEYS_LOSE_THRESHOLD", 3)
        keys_available = keys_total - s.keys_destroyed
        
        if keys_available <= keys_threshold:
            s.game_over = True
            s.outcome = "LOSE_KEYS_DESTROYED"
            return True
    
    return False


def _finalize_step(s, cfg):
    # clamp de cordura (siempre)
    _clamp_all_sanity(s, cfg)
    _cap_monsters(s, cfg)
    
    # === CONDICIONES CANÓNICAS DE FIN DE JUEGO ===
    # Nota: Victoria se verifica típicamente al fin de ronda, 
    # pero aquí hacemos check por seguridad
    if not s.flags.get(PENDING_SACRIFICE_FLAG):
        _check_defeat(s, cfg)

    # pérdida por agotamiento de mazos (modo simulación)
    if (not s.game_over) and getattr(cfg, "LOSE_ON_DECK_EXHAUSTION", False):
        if s.boxes:
            remaining = sum(box.deck.remaining() for box in s.boxes.values())
        else:
            remaining = 0
            for rid, room in s.rooms.items():
                if str(rid).endswith("_P"):  # pasillos
                    continue
                remaining += room.deck.remaining()
        if remaining <= 0:
            s.game_over = True
            s.outcome = "LOSE_DECK"

    # timeout por rondas (modo simulación)
    max_rounds = int(getattr(cfg, "MAX_ROUNDS", 0) or 0)
    if (not s.game_over) and max_rounds > 0 and s.round > max_rounds:
        s.game_over = True
        s.outcome = getattr(cfg, "TIMEOUT_OUTCOME", "TIMEOUT")


def _finalize_and_return(x, cfg):
    _finalize_step(x, cfg)
    return x


def _reveal_one(s, room_id: RoomId):
    room = s.rooms.get(room_id)
    if room is None:
        return None
    deck = active_deck_for_room(s, room_id)
    if deck is None or deck.remaining() <= 0:
        return None
    card = deck.cards[deck.top]
    deck.top += 1
    room.revealed += 1
    return card


def _resolve_card_minimal(s, pid: PlayerId, card, cfg, rng: Optional[RNG] = None):
    """
    Resolver efectos mínimos de cartas.
    - "KEY" → jugador gana una llave (si no excede límite)
    - "MONSTER:<id>" → monstruo entra en el tablero
    - "STATE:<id>" → status al jugador
    - "CROWN" → activa bandera de corona y crea Falso Rey en piso del jugador
    """
    s_str = str(card)
    p = s.players[pid]

    def _grant_object(obj_id: str) -> None:
        # Usar add_object para respetar slots; si no cabe, se descarta el nuevo
        if not add_object(s, pid, obj_id, discard_choice=None):
            s.discard_pile.append(obj_id)
    
    if s_str == "KEY":
        # Ganador de llave: cap por KEYS_TOTAL - keys_destroyed
        # Y cap por capacidad de rol (Canon)
        keys_in_hand = sum(pl.keys for pl in s.players.values())
        keys_in_game = max(0, _get_base_keys_total(cfg) - s.keys_destroyed)
        
        # Check global limit
        if keys_in_hand >= keys_in_game:
            # No more keys available in pool -> devolver carta al fondo
            deck = active_deck_for_room(s, p.room)
            if deck is not None:
                deck.put_bottom(card)
            return

        # Check Role Capacity
        role_capacity = get_max_keys_capacity(p)
        
        if p.keys < role_capacity:
            p.keys += 1
        else:
            # Capacity full: Return valid Key card to bottom of the deck
            # Find deck for current room
            from engine.boxes import active_deck_for_room
            deck = active_deck_for_room(s, p.room)
            if deck is not None:
                # Put EXACTLY "KEY" back
                deck.put_bottom(card)  # card is "KEY" or CardId("KEY")
        return

    if s_str.startswith("OBJECT:"):
        obj_id = s_str.split(":", 1)[1]
        if obj_id == "CROWN":
            # Dejar que lo maneje la lógica especial más abajo
            s_str = "CROWN"
        elif obj_id in OBJECT_CATALOG:
            _grant_object(obj_id)
            return

    if s_str in OBJECT_CATALOG and s_str != "CROWN":
        _grant_object(s_str)
        return
    
    if s_str.startswith("MONSTER:"):
        mid = s_str.split(":", 1)[1]

        # CANON Fix #9: Tue-Tue Logic
        # - Nunca spawna como monstruo
        # - Efecto acumulativo:
        #   1ª Revelación: -1 cordura (aplica Vanidad)
        #   2ª Revelación: -2 cordura (aplica Vanidad)
        #   3ª+ Revelación: FIJAR cordura en -5 (ignora Vanidad/protección, es set estricto)
        if mid == "TUE_TUE":
            s.tue_tue_revelations += 1
            rev = s.tue_tue_revelations
            
            if rev == 1:
                apply_sanity_loss(s, p, 1, source="TUE_TUE_1")
            elif rev == 2:
                apply_sanity_loss(s, p, 2, source="TUE_TUE_2")
            else:
                # Rev >= 3: Fix to -5
                # Asumimos -5 es cfg.S_LOSS, hardcoded per canon request "directamente en -5"
                p.sanity = -5
                # Note: No trigger _apply_minus5_transitions here explicitly? 
                # It will trigger at end of turn/step via check, OR we should rely on usual checks.
                # Usually manual set requires manual check? 
                # _apply_minus5_transitions checks condition p.sanity <= S_LOSS. So it will trigger there.
            
            return

        # CANON Fix (2026-01-25): Lógica de ARAÑA (SPIDER)
        # Al aparecer: TRAPPED por 3 turnos al jugador que la reveló.
        elif mid == "ARAÑA" or mid == "SPIDER":
            add_status(p, "TRAPPED", duration=3, metadata={"source_monster_id": mid})
        
        # Solo agregar si no hemos alcanzado el cap
        
        # Solo agregar si no hemos alcanzado el cap
        cap = int(getattr(cfg, "MAX_MONSTERS_ON_BOARD", 0) or 0)
        if cap <= 0 or len(s.monsters) < cap:
            from engine.state import MonsterState
            monster_room = p.room
            s.monsters.append(MonsterState(monster_id=mid, room=monster_room))

            # P1 - FASE 1.5.3: Hook destrucción de habitación especial cuando monstruo entra
            _on_monster_enters_room(s, monster_room)
            
            # REINA HELADA: Al ser revelada, bloquea movimiento de jugadores en el piso
            # Solo afecta a jugadores presentes en ese momento (no a los que entren después)
            if mid == "REINA_HELADA" or mid == "ICE_QUEEN" or mid == "FROZEN_QUEEN":
                # REINA HELADA: Aparece en el pasillo del piso (Canon P0)
                # Correction: Force room to corridor
                from engine.board import corridor_id
                monster_room = corridor_id(floor_of(p.room))
                # Update the MonsterState we just appended (it was appended with p.room)
                s.monsters[-1].room = monster_room
                
                monster_floor = floor_of(monster_room)
                # Agregar a movement_blocked_players todos los jugadores en este piso
                for other_pid, other in s.players.items():
                    if floor_of(other.room) == monster_floor:
                        if other_pid not in s.movement_blocked_players:
                            s.movement_blocked_players.append(other_pid)

            # DUENDE / GOBLIN Logic: Roba objetos y se teletransporta
            if "DUENDE" in mid or "GOBLIN" in mid:
                # 1. Robar objetos
                if p.objects:
                    # Canon: Roba objetos (asumimos todos por "borrar objetos")
                    p.objects = []
                    s.flags[f"GOBLIN_HAS_LOOT_{mid}"] = True
                
                # 2. Teleport a otro piso (misma habitación relativa)
                if rng:
                    current_floor = floor_of(monster_room)
                    floors = [f for f in (1, 2, 3) if f != current_floor]
                    if floors:
                        new_floor = rng.choice(floors)
                        # Reconstruir RoomId: Fx_Ry
                        parts = str(monster_room).split("_") # e.g. ["F1", "R1"]
                        if len(parts) >= 2:
                             suffix = parts[1]
                             new_room_id = RoomId(f"F{new_floor}_{suffix}")
                             
                             # Actualizar posición del monstruo
                             s.monsters[-1].room = new_room_id
                             _on_monster_enters_room(s, new_room_id)
                             
            # VIEJO / SACK Logic: Atrapa y se lleva al jugador
            if "VIEJO" in mid or "SACK" in mid:
                # 1. Atrapado
                # Usar TRAPPED genérico (duración 2 o custom?) 
                # Canon dice "atrapa", asumimos status TRAPPED.
                # Duración por defecto o 3? Canon table says Generic TRAPPED depends on source.
                # Asignamos 3 para ser seguros/difícil.
                p.statuses.append(StatusInstance(status_id="TRAPPED", remaining_rounds=3, metadata={"source_monster_id": mid}))
                s.flags[f"SACK_HAS_VICTIM_{mid}"] = True
                
                # 2. Teleport + Carry
                if rng:
                    current_floor = floor_of(monster_room)
                    floors = [f for f in (1, 2, 3) if f != current_floor]
                    if floors:
                        new_floor = rng.choice(floors)
                        parts = str(monster_room).split("_")
                        if len(parts) >= 2:
                             suffix = parts[1]
                             new_room_id = RoomId(f"F{new_floor}_{suffix}")
                             
                             # Mover Monstruo
                             s.monsters[-1].room = new_room_id
                             _on_monster_enters_room(s, new_room_id)
                             
                             # Mover Jugador
                             p.room = new_room_id
                             _on_player_enters_room(s, pid, new_room_id)
    
    if s_str.startswith("STATE:"):
        sid = s_str.split(":", 1)[1]
        
        # CANON Fix #B: Duración de TRAPPED = 3 turnos
        if sid in ("TRAPPED", "TRAPPED_SPIDER"):
            duration = 3
        else:
            duration = 2
            
        p.statuses.append(StatusInstance(status_id=sid, remaining_rounds=duration))
        return
    
    if s_str == "CROWN":
        # Falso Rey aparece en el piso del jugador que tomó la corona (canon P0)
        if not s.flags.get("CROWN_YELLOW"):
            s.flags["CROWN_YELLOW"] = True
            s.flags["CROWN_HOLDER"] = str(pid)
            if "CROWN" not in p.soulbound_items:
                p.soulbound_items.append("CROWN")
            # Piso inicial del Falso Rey (cuando se revela CROWN)
            s.false_king_floor = floor_of(p.room)
            s.false_king_round_appeared = s.round
            s.false_king_round_appeared = s.round
        return

    # FASE 0.5: Presagios (Omens)
    if s_str.startswith("OMEN:"):
        omen_id = s_str.split(":", 1)[1]
        
        # Incrementar contador de presagios revelados
        # Nota: count es "cuántos YA han sido revelados ANTES de este" + 1?
        # Usamos flag incremental.
        flag_name = f"OMEN_REVEALED_COUNT_{omen_id}"
        count = s.flags.get(flag_name, 0)
        s.flags[flag_name] = count + 1
        
        # Dispatch
        # 0-1 copias (count 0 o 1 -> Total 1 o 2 actual?)
        # Si count=0, es la 1ª. Si count=1, es la 2ª.
        # Regla: "0-1: Invoca... 2+: Invoca..."
        # Interpretamos: Si es la 1ª o 2ª copia (indices 0, 1), efecto A.
        # Si es la 3ª+ (indice 2+), efecto B.
        is_early = (count < 2)
        
        from engine.state import MonsterState

        # Helper para spawn (Nearest empty)
        def find_spawn_room(start_room):
            # Prioridad: Mismo piso (R1-R4) -> Pasillo mismo piso -> Otros pasillos -> Otras rooms
            # Sin jugadores.
            occupied = {pl.room for pl in s.players.values()}
            current_floor_num = floor_of(start_room)
            
            # 1. Rooms same floor
            candidates = []
            for r in range(1, 5):
                rid = RoomId(f"F{current_floor_num}_R{r}")
                if rid not in occupied:
                    candidates.append(rid)
            if candidates: return candidates[0] # Cualquiera sirve, tomamos primera
            
            # 2. Corridor same floor
            cid = RoomId(f"F{current_floor_num}_P")
            if cid not in occupied:
                return cid
                
            # 3. Other corridors
            for f in range(1, 4):
                if f == current_floor_num: continue
                cid = RoomId(f"F{f}_P")
                if cid not in occupied:
                    return cid
                    
            # 4. Other rooms
            for f in range(1, 4):
                if f == current_floor_num: continue
                for r in range(1, 5):
                    rid = RoomId(f"F{f}_R{r}")
                    if rid not in occupied:
                         return rid
            
            # Fallback: Current room
            return start_room

        spawn_pos = find_spawn_room(p.room)
        
        if omen_id == "ARAÑA":
            if is_early:
                # Invoca SPIDER. Si ya existe, descarta carta (no spawn).
                exists = any("SPIDER" in m.monster_id or "ARAÑA" in m.monster_id for m in s.monsters)
                if not exists:
                    s.monsters.append(MonsterState(monster_id="MONSTER:SPIDER", room=spawn_pos))
                    _on_monster_enters_room(s, spawn_pos)
            else:
                s.monsters.append(MonsterState(monster_id="MONSTER:BABY_SPIDER", room=spawn_pos))
                _on_monster_enters_room(s, spawn_pos)
                
        elif omen_id == "DUENDE":
            if is_early:
                exists = any("DUENDE" in m.monster_id for m in s.monsters)
                if not exists:
                    s.monsters.append(MonsterState(monster_id="MONSTER:DUENDE", room=spawn_pos))
                    _on_monster_enters_room(s, spawn_pos)
            else:
                # Pierde 1 objeto (si tiene)
                if p.objects:
                    p.objects.pop() 

        elif omen_id == "REINA_HELADA":
            if is_early:
                exists = any("REINA_HELADA" in m.monster_id for m in s.monsters)
                if not exists:
                    # Reina aparece en PASILLO del piso
                    c_id = RoomId(f"F{floor_of(spawn_pos)}_P")
                    s.monsters.append(MonsterState(monster_id="MONSTER:REINA_HELADA", room=c_id))
                    _on_monster_enters_room(s, c_id)
            else:
                # ICE_SERVANT
                s.monsters.append(MonsterState(monster_id="MONSTER:ICE_SERVANT", room=spawn_pos))
                _on_monster_enters_room(s, spawn_pos)

        elif omen_id == "TUE_TUE":
            if is_early:
                s.monsters.append(MonsterState(monster_id="MONSTER:TUE_TUE", room=spawn_pos))
                _on_monster_enters_room(s, spawn_pos)
            else:
                # Cordura = 0
                p.sanity = 0

        # Omen se consume (no vuelve al mazo, se asume 'discarded' fuera de juego o bottom)
        # Eventos vuelven al bottom. Presagios suelen ser únicos o eventos persistentes.
        # Canon: "descarta la carta".
        # Si la ponemos en bottom, volverá a salir.
        # Si la descartamos (removemos), no vuelve.
        # Asumiremos Bottom para mantener ciclicidad del mazo si se acaba?
        # "Si ya existe ... descarta la carta" -> implies it is removed from play?
        # Pero si ponemos en bottom, volverá a salir y count aumentará.
        # Vamos a poner en bottom para consistencia con Eventos.
        from engine.boxes import active_deck_for_room
        deck = active_deck_for_room(s, p.room)
        if deck:
            deck.put_bottom(CardId(s_str))
        
        return

    # FASE 0: Resolución de eventos
    if s_str.startswith("EVENT:") or s_str.startswith("EVENTS:"):
        prefix = s_str.split(":", 1)[0]
        event_id = s_str.split(":", 1)[1]
        _resolve_event(s, pid, event_id, cfg, rng, card_prefix=prefix)
        return


def _on_player_enters_room(s: GameState, pid: PlayerId, room: RoomId) -> None:
    """
    P1 - FASE 1.5.2: Hook cuando un jugador entra a una habitación.
    """
    if room not in s.rooms:
        return
        
    # FASE 1: Habilidad PSYCHIC - Scry 2
    # Ver/reordenar 2 cartas top.
    # Heurística: Monstruo al fondo (-2), Otros arriba (-1).
    p = s.players[pid]
    if getattr(p, "role_id", "") == "PSYCHIC":
        deck = active_deck_for_room(s, room)
        if deck and deck.remaining() >= 2:
            c1 = deck.cards[deck.top]
            c2 = deck.cards[deck.top + 1]
            
            # Score descending (High = Top)
            s1 = -2 if str(c1).startswith("MONSTER") else -1
            s2 = -2 if str(c2).startswith("MONSTER") else -1
            
            if s2 > s1:
                # c2 es mejor, poner c2 primero
                deck.cards[deck.top] = c2
                deck.cards[deck.top + 1] = c1

    room_state = s.rooms[room]

    # Si hay una carta especial boca abajo, revelarla
    if (room_state.special_card_id is not None and
        not room_state.special_revealed and
        not room_state.special_destroyed):

        room_state.special_revealed = True
        # Log o tracking de revelación
        s.flags[f"SPECIAL_REVEALED_{room}_{room_state.special_card_id}"] = s.round


def _on_monster_enters_room(s: GameState, room: RoomId) -> None:
    """
    P1 - FASE 1.5.3: Hook cuando un monstruo entra a una habitación.

    Si la habitación tiene una habitación especial activa (no destruida), la destruye.
    Según P1: cuando un monstruo entra, la habitación especial se destruye, pero el nodo
    y su mazo permanecen intactos.

    ESPECÍFICO: Para Armería, además vacía su almacenamiento.
    """
    if room not in s.rooms:
        return

    room_state = s.rooms[room]

    # Si hay una habitación especial no destruida, destruirla
    if (room_state.special_card_id is not None and
        not room_state.special_destroyed):

        # Marcar como destruida
        room_state.special_destroyed = True

        # ESPECÍFICO: Armería vacía su almacenamiento
        # CANON Fix #D: Unificar IDs (ARMERY/ARMERIA)
        if room_state.special_card_id in ("ARMERY", "ARMERIA"):
            if room in s.armory_storage:
                s.armory_storage[room] = []

        # LEGACY: Mantener flag para compatibilidad con tests existentes
        if room_state.special_card_id in ("ARMERY", "ARMERIA"):
            s.flags[f"ARMORY_DESTROYED_{room}"] = True


def _resolve_event(s: GameState, pid: PlayerId, event_id: str, cfg: Config, rng: RNG, card_prefix: str = "EVENT"):
    """
    Resuelve un evento por su ID.

    Convención: Total = d6 + cordura_actual (clamp mínimo 0)
    """
    from engine.types import CardId
    p = s.players[pid]

    # Protección Amarillo: inmunidad a eventos "amarillo" por 1 ronda
    prot_flag = s.flags.get(f"PROTECCION_AMARILLO_{pid}", 0)
    amarillo_events = {
        "FURIA_AMARILLO",
        "GOLPE_AMARILLO",
        "REFLEJO_AMARILLO",
        "ESPEJO_AMARILLO",
        "DIVAN_AMARILLO",
    }
    if event_id in amarillo_events and prot_flag > s.round:
        # Evento se ignora pero la carta vuelve al fondo
        deck = active_deck_for_room(s, p.room)
        if deck is not None:
            deck.put_bottom(CardId(f"{card_prefix}:{event_id}"))
        return

    # Calcular Total (usado por muchos eventos)
    d6 = rng.randint(1, 6)
    
    # FASE 1: High Roller Ability (Double Roll)
    # Automáticamente usa la habilidad en el primer evento del turno
    if getattr(p, "role_id", "") == "HIGH_ROLLER" and not p.double_roll_used_this_turn:
        d6_2 = rng.randint(1, 6)
        d6 += d6_2
        p.double_roll_used_this_turn = True
        
    total = max(0, d6 + p.sanity)

    # Dispatch por event_id
    if event_id == "REFLEJO_AMARILLO" or event_id == "GOLPE_AMARILLO":
        _event_golpe_amarillo(s, pid, cfg)
    elif event_id == "ESPEJO_AMARILLO":
        _event_espejo_amarillo(s, pid, cfg)
    elif event_id == "HAY_CADAVER":
        _event_hay_cadaver(s, pid, total, cfg, rng)
    elif event_id == "COMIDA_SERVIDA":
        _event_comida_servida(s, pid, total, cfg, rng)
    elif event_id == "DIVAN_AMARILLO":
        _event_divan_amarillo(s, pid, total, cfg)
    elif event_id == "CAMBIA_CARAS":
        _event_cambia_caras(s, pid, total, cfg)
    elif event_id == "FURIA_AMARILLO":
        _event_furia_amarillo(s, pid, total, cfg, rng)
    elif event_id == "ASCENSOR":
        _event_ascensor(s, pid, total, cfg, rng)
    elif event_id == "TRAMPILLA":
        _event_trampilla(s, pid, total, cfg, rng)
    elif event_id == "EVENTO_MOTEMEY":
        # Dispara el diálogo de Motemey inmediatamente
        _event_motemey_trigger(s, pid, cfg)

    # Evento vuelve al fondo del mazo (convención)
    # CORRECCIÓN: Usar put_bottom() para no duplicar la carta
    # La carta ya fue extraída del mazo por _reveal_one (avanzó deck.top)
    deck = active_deck_for_room(s, p.room)
    if deck is not None:
        deck.put_bottom(CardId(f"{card_prefix}:{event_id}"))


# Funciones placeholder para los 7 eventos existentes
# Se implementarán en FASE 2

# Implementación Canónica de Eventos (2026-01-25)
# =================================================

def _event_golpe_amarillo(s: GameState, pid: PlayerId, cfg: Config) -> None:
    """Golpe de Amarillo (ex Reflejo): Pierdes 2 de cordura."""
    p = s.players[pid]
    apply_sanity_loss(s, p, 2, source="GOLPE_AMARILLO")


def _event_espejo_amarillo(s: GameState, pid: PlayerId, cfg: Config) -> None:
    """Espejo de Amarillo: invierte la cordura (cordura × -1)."""
    p = s.players[pid]
    p.sanity = -p.sanity


def _event_hay_cadaver(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Hay un cadáver: según Total.
    0-2: Pierdes turno siguiente
    3-4: -1 cordura
    5+: Obtienes objeto contundente
    """
    p = s.players[pid]

    if total <= 2:
        # Pierdes turno: flag para saltar próximo turno
        s.flags[f"SKIP_TURN_{pid}"] = True
    elif total <= 4:
        apply_sanity_loss(s, p, 1, source="HAY_CADAVER")
    else:  # total >= 5
        # Obtener objeto contundente
        if not add_object(s, pid, "BLUNT", discard_choice=None):
            s.discard_pile.append("BLUNT")


def _event_comida_servida(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Una comida servida: según Total.
    0: -3 cordura
    1-2: Estado Envenenado (Canon: Sangrado -> Envenenado)
    3-6: +2 cordura
    7+: Trae otro jugador a tu habitación, ambos +2 cordura
    """
    from engine.effects.event_utils import add_status
    p = s.players[pid]

    if total == 0:
        apply_sanity_loss(s, p, 3, source="COMIDA_SERVIDA")
    elif total <= 2:
        # Canon: 1-2 -> ENVENENADO (antes llamado Sangrado)
        add_status(p, "ENVENENADO", duration=2)
    elif total <= 6:
        _heal(p, 2)
    else:  # total >= 7
        # Traer otro jugador (aleatorio)
        other_pids = [pid2 for pid2 in s.players if pid2 != pid]
        if other_pids:
            target_pid = rng.choice(other_pids)
            s.players[target_pid].room = p.room
            _on_player_enters_room(s, target_pid, p.room)
            
            # Ambos +2 cordura
            _heal(p, 2)
            target = s.players[target_pid]
            _heal(target, 2)


def _event_divan_amarillo(s: GameState, pid: PlayerId, total: int, cfg: Config) -> None:
    """
    Un diván de Amarillo: según Total.
    0-3: Quita todos los estados
    4-7: Quita estados + 1 cordura
    8+: Obtiene estado Sanidad
    """
    from engine.effects.event_utils import add_status, remove_all_statuses
    p = s.players[pid]

    if total <= 3:
        remove_all_statuses(p)
    elif total <= 7:
        remove_all_statuses(p)
        _heal(p, 1)
    else:  # total >= 8
        add_status(p, "SANIDAD", duration=2)


def _event_cambia_caras(s: GameState, pid: PlayerId, total: int, cfg: Config) -> None:
    """
    Cambia caras: según Total.
    0-3: Swap con jugador a la derecha (orden turno +1, ej 1->2)
    4+: Swap con jugador a la izquierda (orden turno -1, ej 1->4)
    """
    from engine.effects.event_utils import swap_positions, get_player_by_turn_offset

    if len(s.turn_order) < 2:
        return  # No hay con quién intercambiar

    # Canon: "Si le sale al 2, izquierda es 1, derecha es 3"
    # Derecha (+1 en idx?): 1 -> 2 -> 3 -> 4 -> 1
    # Izquierda (-1 en idx): 1 -> 4 -> 3 -> 2 -> 1
    
    offset = 1 if total <= 3 else -1
    target_pid = get_player_by_turn_offset(s, pid, offset)
    swap_positions(s, pid, target_pid)


def _event_furia_amarillo(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    La furia de Amarillo: según Total.
    0: Dobla efecto del Rey PERMANENTEMENTE
    1-4: Rey se mueve al piso del jugador activo (+ daño llegada)
    5+: Aturde al Rey 1 ronda
    """
    p = s.players[pid]

    if total == 0:
        # Canon: "Permanentemente"
        s.flags["KING_DAMAGE_DOUBLE_PERMANENT"] = True
    elif total <= 4:
        # Mover Rey al piso del jugador
        player_floor = floor_of(p.room)
        s.king_floor = player_floor
        
        # Daño de llegada (inmediato)
        # Asumimos daño standard de fin de ronda (HOUSE_LOSS) o presencia?
        # Canon dice "vuelve a hacer el daño de llegada". 
        # Interpretación: Daño de presencia del rey en ese piso.
        dmg = cfg.HOUSE_LOSS_PER_ROUND
        if s.flags.get("KING_DAMAGE_DOUBLE_PERMANENT"):
            dmg *= 2
        elif s.flags.get("KING_DAMAGE_DOUBLE_UNTIL", 0) > s.round:
            dmg *= 2
            
        # Aplicar a todos en el piso
        for pl in s.players.values():
             if floor_of(pl.room) == player_floor:
                 apply_sanity_loss(s, pl, dmg, source="KING_ARRIVAL")
                 
    else: # total >= 5
        # Aturde al Rey 1 ronda
        # Implementado via flag que skipea su fase o reduce daño?
        # Asumiremos skip fase King
        s.king_vanished_turns = 1


def _event_ascensor(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Ascensor:
    0: Fin turno
    1-3: Subir 1 piso (F1->F2->F3->F1)
    4-6: Subir 2 pisos (F1->F3->F2->F1)
    """
    p = s.players[pid]
    current_floor = floor_of(p.room)
    suffix = str(p.room).split("_")[1] # e.g. R1, P

    if total == 0:
        s.remaining_actions[pid] = 0
    elif total <= 3:
        # Subir 1
        new_floor = (current_floor % 3) + 1
        new_rid = RoomId(f"F{new_floor}_{suffix}")
        p.room = new_rid
        _on_player_enters_room(s, pid, new_rid)
    else:
        # Subir 2
        new_floor = ((current_floor + 1) % 3) + 1
        new_rid = RoomId(f"F{new_floor}_{suffix}")
        p.room = new_rid
        _on_player_enters_room(s, pid, new_rid)


def _event_trampilla(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Trampilla:
    0: Fin turno
    1-3: Baja 2 pisos (= Subir 1)
    4-6: Baja 1 piso (= Subir 2)
    """
    p = s.players[pid]
    current_floor = floor_of(p.room)
    suffix = str(p.room).split("_")[1]

    if total == 0:
        s.remaining_actions[pid] = 0
    elif total <= 3:
        # Baja 2 (equivale a subir 1 en mod 3)
        new_floor = (current_floor % 3) + 1
        new_rid = RoomId(f"F{new_floor}_{suffix}")
        p.room = new_rid
        _on_player_enters_room(s, pid, new_rid)
    else:
        # Baja 1 (equivale a subir 2 en mod 3, o restar 1)
        # F2 -> F1, F3 -> F2, F1 -> F3
        vals = {1: 3, 2: 1, 3: 2} # Mapping bajar 1
        new_floor = vals[current_floor]
        new_rid = RoomId(f"F{new_floor}_{suffix}")
        p.room = new_rid
        _on_player_enters_room(s, pid, new_rid)


def _event_motemey_trigger(s: GameState, pid: PlayerId, cfg: Config) -> None:
    """
    Evento Motemey: Abre tienda inmediatamente.
    Funciona igual que la habitación: Compra (2 san) o Venta (gratis).
    """
    # Trigger UI dialog via flag/state machine
    # En engine actual, usamos active_deck_for_room o similar.
    # Necesitamos poner el juego en modo "MOTEMEY_CHOICE" intermedio?
    # O simplemente logear que puede hacerlo? 
    # El engine soporta State machine updates.
    
    # Marcamos que el jugador actual está en evento Motemey
    s.motemey_event_active = True
    # Esto debería bloquear otras acciones hasta resolver la compra/venta
    # Asumimos que el Loop principal chequeará esto y pedirá input


def _update_umbral_flags(s, cfg):
    for p in s.players.values():
        p.at_umbral = str(p.room) == str(cfg.UMBRAL_NODE)


def _apply_minus5_transitions(s, cfg):
    """
    P0.4: Event on crossing to -5.
    - Destroy keys and objects when crossing to <= -5
    - Others lose 1 sanity when someone crosses
    - Maintain 1 action while at -5; restore 2 when leaving to -4
    - Event fires only once on crossing (tracked via at_minus5 flag)
    """
    for pid, p in s.players.items():
        if p.sanity <= cfg.S_LOSS:  # At or below -5
            if not p.at_minus5:  # Just crossed into -5
                # CANON Fix #A: Interrupt check
                # Check directly in step() via flag.
                # If flag is already set, we are waiting for user.
                # If not set, set it now.
                if s.flags.get(PENDING_SACRIFICE_FLAG) != str(pid):
                     s.flags[PENDING_SACRIFICE_FLAG] = str(pid)
                
                # Do NOT apply effects here. They are applied in step() upon ACCEPT_SACRIFICE.
                # Effects moved to _apply_minus5_consequences(s, pid, cfg)
            
            # CANON: NO reducir acciones por estar en -5 (eliminado)
        else:  # Above -5
            if p.at_minus5:  # Just left -5
                p.at_minus5 = False


def _apply_minus5_consequences(s, pid, cfg):
    """Aux helper to apply the actual consequences of being at -5."""
    p = s.players[pid]
    # Destroy keys and objects, track globally
    s.keys_destroyed += p.keys
    p.keys = 0
    p.objects = []
    
    # Other players lose 1 sanity
    for other_pid, other in s.players.items():
        if other_pid != pid:
            apply_sanity_loss(s, other, 1, source="MINUS_5_TRANSITION")
    
    # Mark as in -5 state (consequences accepted)
    p.at_minus5 = True


def _apply_status_effects_end_of_round(s: GameState) -> None:
    """
    FASE 3: Aplica efectos de estados al final de ronda, ANTES del tick de duración.

    Estados implementados:
    - ENVENENADO/SANGRADO: Reduce sanity_max en 1 (efecto PERMANENTE)
    - MALDITO: Todas las Pobres Almas en el mismo piso pierden 1 cordura
    - SANIDAD: El jugador recupera 1 cordura (también en end_of_turn)
    """
    from engine.board import floor_of
    from engine.effects.states_canonical import has_status

    # ENVENENADO (alias SANGRADO): Reduce sanity_max en 1 (permanente)
    # Canon: La reducción de max es permanente incluso después de que expire el estado
    for p in s.players.values():
        if has_status(p, "ENVENENADO"):
            if p.sanity_max is not None and p.sanity_max > -5:
                p.sanity_max -= 1
                # Ajustar cordura actual si excede el nuevo máximo
                if p.sanity > p.sanity_max:
                    p.sanity = p.sanity_max

    # MALDITO: Afecta a otros jugadores en el mismo piso
    for pid, p in s.players.items():
        if has_status(p, "MALDITO"):
            player_floor = floor_of(p.room)
            for other_pid, other in s.players.items():
                if other_pid != pid and floor_of(other.room) == player_floor:
                    other.sanity -= 1

    # SANIDAD: Recupera 1 cordura (también aplica en end_of_turn, aquí por compatibilidad)
    for p in s.players.values():
        if has_status(p, "SANIDAD"):
            _heal(p, 1)




def _current_false_king_floor(s) -> Optional[int]:
    _sync_crown_holder(s)
    holder_id = s.flags.get("CROWN_HOLDER") if s.flags else None
    if not holder_id:
        return s.false_king_floor
    holder = s.players.get(PlayerId(holder_id))
    if holder is None:
        return s.false_king_floor
    return floor_of(holder.room)


def _sync_crown_holder(s) -> None:
    if s.flags is None:
        return
    holder_id = s.flags.get("CROWN_HOLDER")
    if holder_id:
        holder = s.players.get(PlayerId(holder_id))
        if holder is not None and "CROWN" not in holder.soulbound_items:
            holder.soulbound_items.append("CROWN")
        if not s.flags.get("CROWN_YELLOW"):
            s.flags["CROWN_YELLOW"] = True
        return
    for pid, player in s.players.items():
        if player is None:
            continue
        if "CROWN" in player.soulbound_items:
            s.flags["CROWN_HOLDER"] = str(pid)
            s.flags["CROWN_YELLOW"] = True
            return

def _advance_turn_or_king(s):
    order = s.turn_order
    if not order:
        s.phase = "KING"
        return

    # Find next player with remaining actions.
    start = s.turn_pos
    n = len(order)
    for i in range(1, n + 1):
        pos = (start + i) % n
        pid = order[pos]
        if s.remaining_actions.get(pid, 0) > 0:
            s.turn_pos = pos
            
            # CANON Fix #C: PEEK/TABERNA reset on player turn start
            # Reset EARLIER turn use if any (though usually clean)
            # Ensure fresh flags for this player
            if pid in s.taberna_used_this_turn:
                del s.taberna_used_this_turn[pid]
            if pid in s.peek_used_this_turn:
                del s.peek_used_this_turn[pid]
                
            return

    s.phase = "KING"


def _presence_damage_for_round(round_n: int) -> int:
    """
    Damage per round from King presence (P0.5).
    Canon table (confirmed):
    - Rounds 1-3: 1 damage
    - Rounds 4-6: 2 damage
    - Rounds 7-9: 3 damage
    - Rounds 10+: 4 damage
    """
    if round_n <= 3:
        return 1
    elif round_n <= 6:
        return 2
    elif round_n <= 9:
        return 3
    else:
        return 4


def _shuffle_all_room_decks(s, rng: RNG):
    if s.boxes:
        decks = [box.deck for box in s.boxes.values()]
    else:
        decks = [room.deck for room in s.rooms.values()]
    for deck in decks:
        if deck.remaining() > 1:
            tail = deck.cards[deck.top :]
            rng.shuffle(tail)
            deck.cards[deck.top :] = tail


def _expel_players_from_floor(s, floor: int):
    """
    P0.2: Expel players from King's floor to adjacent floor's stair room.
    Floor mapping (canon):
    - F1 -> F2 (move to stair room in F2)
    - F2 -> F1 (move to stair room in F1)
    - F3 -> F2 (move to stair room in F2)
    """
    # Determine destination floor
    if floor == 1:
        dest_floor = 2
    elif floor == 2:
        dest_floor = 1
    elif floor == 3:
        dest_floor = 2
    else:
        return  # Invalid floor
    
    # Move players to stair room in destination floor
    stair_room = s.stairs.get(dest_floor)
    if stair_room is None:
        return  # No stair initialized (shouldn't happen)
    
    for p in s.players.values():
        if floor_of(p.room) == floor:
            p.room = stair_room


def _attract_players_to_floor(s, floor: int):
    """
    Attract (atraer) all players to the corridor of the specified floor.
    P0.4b: Exception: don't move players on the floor of the crown holder.
    """
    target = corridor_id(floor)
    fk_floor = _current_false_king_floor(s)
    for p in s.players.values():
        # Don't move if player is on the false king floor
        if fk_floor is not None and floor_of(p.room) == fk_floor:
            continue
        p.room = target


def _expel_players_from_floor_except_fk(s, floor: int, fk_floor: Optional[int]):
    """
    CANON: Expel players but skip those on False King floor.
    """
    if floor == 1:
        dest_floor = 2
    elif floor == 2:
        dest_floor = 1
    elif floor == 3:
        dest_floor = 2
    else:
        return
    
    stair_room = s.stairs.get(dest_floor)
    if stair_room is None:
        return
    
    for p in s.players.values():
        if floor_of(p.room) == floor:
            # CANON: Skip if on FK floor
            if fk_floor is not None and floor_of(p.room) == fk_floor:
                continue
            p.room = stair_room


def _attract_players_to_floor_except_fk(s, floor: int, fk_floor: Optional[int]):
    """
    CANON: Attract players but skip those on False King floor.
    """
    target = corridor_id(floor)
    for p in s.players.values():
        # CANON: Skip if on FK floor
        if fk_floor is not None and floor_of(p.room) == fk_floor:
            continue
        p.room = target


def _roll_stairs(s, rng: RNG):
    """Reroll stairs (1d4 per floor) at end of round."""
    from engine.board import room_from_d4, FLOORS
    for floor in range(1, FLOORS + 1):
        roll = rng.randint(1, 4)
        s.stairs[floor] = room_from_d4(floor, roll)


def _false_king_check(s, rng: RNG, cfg):
    """
    P0: Check de Falso Rey al final de ronda.
    total = d6 + cordura_actual (clamp mínimo 0)
    umbral = cordura_max + 2 + (rondas desde aparición)
    Si total <= umbral: aplicar solo daño por presencia en piso del Falso Rey.
    """
    fk_floor = _current_false_king_floor(s)
    if fk_floor is None:
        return

    holder_id = s.flags.get("CROWN_HOLDER")
    if not holder_id:
        return

    holder = s.players.get(PlayerId(holder_id))
    if holder is None:
        return

    if s.false_king_round_appeared is None:
        s.false_king_round_appeared = s.round

    rounds_since = max(0, s.round - s.false_king_round_appeared)
    sanity_max = _sanity_cap(holder)
    threshold = int(sanity_max) + 1 + int(rounds_since)
    total = rng.randint(1, 6) + max(0, int(holder.sanity))

    if total <= threshold:
        pres = _presence_damage_for_round(s.round)
        for p in s.players.values():
            if floor_of(p.room) == fk_floor:
                apply_sanity_loss(s, p, pres, source="FALSE_KING_PRESENCE")


def _end_of_round_checks(s, cfg):
    if s.game_over:
        return

    # Delegar la decisión de derrota a la función especializada
    if not s.flags.get(PENDING_SACRIFICE_FLAG) and _check_defeat(s, cfg):
        return  # Outcome ya seteado por _check_defeat
    _check_victory(s, cfg)





def _start_new_round(s, cfg):
    order = s.turn_order
    if not order:
        s.phase = "PLAYER"
        return

    s.starter_pos = (s.starter_pos + 1) % len(order)
    s.turn_pos = s.starter_pos
    s.phase = "PLAYER"

    # CANON Fix #C: Flags de Taberna/Peek se resetean PER PLAYER al inicio de SU turno.
    # Aquí inicia el turno del starter, así que reseteamos solo al starter.
    initial_pid = order[s.turn_pos]
    if initial_pid in s.taberna_used_this_turn:
        del s.taberna_used_this_turn[initial_pid]
    if initial_pid in s.peek_used_this_turn:
        del s.peek_used_this_turn[initial_pid]

    # REINA HELADA: Limpiar bloqueo de movimiento (solo dura el turno de entrada)
    s.movement_blocked_players = []
    
    # REINA HELADA: Encontrar el piso donde está la Reina (para ACCION_REDUCIDA)
    reina_floors = set()
    for monster in s.monsters:
        if monster.monster_id in ("REINA_HELADA", "ICE_QUEEN", "FROZEN_QUEEN", "MONSTER:ICE_SERVANT"):
            # Solo aplicar si la Reina no está stuneada
            if monster.stunned_remaining_rounds <= 0:
                reina_floors.add(floor_of(monster.room))

    for pid in order:
        p = s.players[pid]
        
        # Check SKIP_TURN (Stun effect)
        skip_flag = f"SKIP_TURN_{pid}"
        if s.flags.get(skip_flag, False):
            s.flags[skip_flag] = False
            s.remaining_actions[pid] = 0
            # Reset flags
            p.double_roll_used_this_turn = False
            p.free_move_used_this_turn = False
            continue

        # Reset flags de turno
        p.double_roll_used_this_turn = False
        p.free_move_used_this_turn = False

        actions = 2
        # Scout: +1 acción base
        # Scout: +1 acción base REMOVED (now handled via free move cost reduction)
        # actions = get_scout_actions(p, actions)

        if s.limited_action_floor_next is not None:
            if floor_of(p.room) == s.limited_action_floor_next:
                actions = min(actions, 1)
        
        # CANON Fix #G: Estar en -5 NO quita acciones (siempre 2 base)
        # if p.sanity <= cfg.S_LOSS:
        #     actions = min(actions, 1)
        
        # REINA HELADA (turnos posteriores): Jugadores en piso de Reina solo tienen 1 acción
        if floor_of(s.players[pid].room) in reina_floors:
            actions = min(actions, 1)

        # B1: ILUMINADO otorga +1 acción (usar ID canónico "ILUMINADO" o alias "ILLUMINATED")
        from engine.effects.states_canonical import has_status
        p = s.players[pid]
        if has_status(p, "ILUMINADO"):
            actions += 1

        s.remaining_actions[pid] = actions

    s.limited_action_floor_next = None


def step(state: GameState, action: Action, rng: RNG, cfg: Optional[Config] = None) -> GameState:
    cfg = cfg or Config()
    s = state.clone()

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
    pending_pid_str = s.flags.get(PENDING_SACRIFICE_FLAG)
    if pending_pid_str:
        if action.actor != pending_pid_str:
             raise ValueError(f"Pending sacrifice check for {pending_pid_str}, but {action.actor} acted.")
        
        if action.type == ActionType.SACRIFICE:
            # Player chose to SACRIFICE
            # Apply sacrifice cost
            p = s.players[PlayerId(pending_pid_str)]
            _apply_sacrifice_choice(s, PlayerId(pending_pid_str), cfg, action.data)
            # Clear flag, do NOT apply -5 consequences (as sanity is now 0 > -5)
            # p.at_minus5 remains False (or becomes False)
            del s.flags[PENDING_SACRIFICE_FLAG]
            return _finalize_and_return(s, cfg)
            
        elif action.type == ActionType.ACCEPT_SACRIFICE:
            # Player chose to accept consequences
            _apply_minus5_consequences(s, PlayerId(pending_pid_str), cfg)
            del s.flags[PENDING_SACRIFICE_FLAG]
            return _finalize_and_return(s, cfg)
            
        else:
             raise ValueError(f"Illegal action during sacrifice check: {action.type}. Must be SACRIFICE or ACCEPT_SACRIFICE.")

    if s.phase == "PLAYER":
        pid = PlayerId(action.actor)
        p = s.players[pid]

        # CANON: No hay auto-escape. Escape es manual via ESCAPE_TRAPPED action.

        if action.type == ActionType.MOVE:
            to = RoomId(action.data["to"])
            previous_floor = floor_of(p.room)
            new_floor = floor_of(to)
            
            p.room = to

            # FASE 1: Scout Stair Risk
            # Si cambia de piso (usa escalera) y es Scout: Check STUN
            if previous_floor != new_floor and getattr(p, "role_id", "") == "SCOUT":
                # Check Stun: d6 + cordura < 3 -> Pierde próximo turno
                d6 = rng.randint(1, 6)
                if d6 + p.sanity < 3:
                     s.flags[f"SKIP_TURN_{pid}"] = True

            # P1 - FASE 1.5.2: Hook revelación de habitación especial
            # Mecánica de cadena (LIFO): primero se revela la habitación especial, luego la carta del mazo
            _on_player_enters_room(s, pid, to)

            # Revelar primera carta del mazo (regla general)
            card = _reveal_one(s, to)
            if card is not None:
                _resolve_card_minimal(s, pid, card, cfg, rng)

        elif action.type == ActionType.SEARCH:
            card = _reveal_one(s, p.room)
            if card is not None:
                _resolve_card_minimal(s, pid, card, cfg, rng)

        elif action.type == ActionType.MEDITATE:
            # CANON: +1 base, +2 si es pasillo (total +2)
            from engine.board import is_corridor
            heal = 2 if is_corridor(p.room) else 1
            _heal(p, heal)

        elif action.type == ActionType.DISCARD_SANIDAD:
            # SANIDAD: descartar para limpiar todos los estados
            remove_all_statuses(p)

        # SACRIFICE (Manual trigger outside of interrupt - e.g. preemptive?)
        # Canon fix A makes sacrifice a response.
        # But maybe we keep it as an action if user wants to do it before hitting -5?
        # User request A says: "SACRIFICE should be an interrupt decision".
        # If we keep it here, it duplicates logic.
        # But if we remove it, player can't self-sacrifice at will?
        # Let's keep it but ensure it clears flag if it was somehow active (covered above).
        # This block is for "Standard Action Phase", so pending flag is NOT active here.
        elif action.type == ActionType.SACRIFICE:
            _apply_sacrifice_choice(s, pid, cfg, action.data)

        elif action.type == ActionType.ESCAPE_TRAPPED:
            # A5: Intento de liberarse del estado TRAPPED
            # CANON: d6 + cordura >= 3 para éxito.
            d6 = rng.randint(1, 6)
            total = d6 + p.sanity
            
            # Log attempt
            s.action_log.append({"event": "ESCAPE_ATTEMPT", "d6": d6, "sanity": p.sanity, "total": total, "success": total >= 3})

            if total >= 3:
                # Éxito: remover TRAPPED
                # Buscar metadata para source monster antes de borrar
                trapped_st = None
                for st in p.statuses:
                     if st.status_id in ("TRAPPED", "TRAPPED_SPIDER"):
                         trapped_st = st
                         break
                
                # Remover status (usando helper o filtro)
                p.statuses = [st for st in p.statuses if st.status_id not in ("TRAPPED", "TRAPPED_SPIDER")]
                
                # Aplicar STUN 1 turno al monstruo fuente
                if trapped_st and trapped_st.metadata.get("source_monster_id"):
                    mid = trapped_st.metadata["source_monster_id"]
                    for monster in s.monsters:
                        if monster.monster_id == mid:
                            if "YELLOW_KING" not in monster.monster_id:
                                monster.stunned_remaining_rounds = 1
                            break
                else:
                    # Fallback por si no hay metadata: Stun a monstruos en la sala
                    for monster in s.monsters:
                        if monster.room == p.room:
                            monster.stunned_remaining_rounds = 1

                # Éxito: el costo de acción se descuenta en bloque general (paid_action_types)
            else:
                # Fracaso: termina turno inmediatamente (override del costo normal)
                s.remaining_actions[pid] = 0
                return _finalize_and_return(s, cfg)

        elif action.type == ActionType.END_TURN:
            s.remaining_actions[pid] = 0
            # Evento Motemey no debe persistir entre turnos
            s.motemey_event_active = False

        # ===== B2: MOTEMEY (buy/sell) =====
        elif action.type == ActionType.USE_MOTEMEY_BUY:
            # DEPRECATED: Mantener compatibilidad con código viejo
            # Compra: -2 sanidad, ofrece 2 cartas, elige 1
            # Supuesto: no consume acción (es acción de habitación)
            if p.sanity >= 2:
                apply_sanity_loss(s, p, 2, source="MOTEMEY_BUY")
                deck = s.motemey_deck
                # Ofertar 2 cartas
                if deck.remaining() >= 2:
                    card1 = deck.cards[deck.top]
                    card2 = deck.cards[deck.top + 1]
                    deck.top += 2

                    # Elige la 1ª (data["chosen_index"] = 0 o 1)
                    chosen_idx = int(action.data.get("chosen_index", 0))
                    chosen = card1 if chosen_idx == 0 else card2
                    rejected = card2 if chosen_idx == 0 else card1

                    # Elegida al inventario, rechazada al final del mazo
                    chosen_str = str(chosen)
                    if chosen_str == "KEY":
                        keys_in_hand = sum(pl.keys for pl in s.players.values())
                        keys_in_game = max(0, _get_base_keys_total(cfg) - s.keys_destroyed)
                        if keys_in_hand < keys_in_game and p.keys < get_max_keys_capacity(p):
                            p.keys += 1
                        else:
                            # No se puede tomar -> devolver al mazo
                            deck.put_bottom(chosen)
                    else:
                        if not add_object(s, pid, chosen_str, discard_choice=action.data.get("discard_choice")):
                            # No cabe -> devolver al mazo
                            deck.put_bottom(chosen)

                    deck.put_bottom(rejected)
            # Evento Motemey no debe persistir
            s.motemey_event_active = False

        # CORRECCIÓN D: Motemey - Sistema de elección de 2 pasos
        elif action.type == ActionType.USE_MOTEMEY_BUY_START:
            # Paso 1: Cobra -2 cordura, extrae 2 cartas, guarda en pending_choice
            apply_sanity_loss(s, p, 2, source="MOTEMEY_BUY")
            deck = s.motemey_deck

            if deck.remaining() >= 2:
                card1 = deck.draw_top()
                card2 = deck.draw_top()

                # Guardar cartas ofertadas en pending_choice
                if s.pending_motemey_choice is None:
                    s.pending_motemey_choice = {}
                s.pending_motemey_choice[str(pid)] = [card1, card2]

        elif action.type == ActionType.USE_MOTEMEY_BUY_CHOOSE:
            # Paso 2: Jugador elige carta (index 0 o 1)
            if s.pending_motemey_choice and str(pid) in s.pending_motemey_choice:
                cards = s.pending_motemey_choice[str(pid)]
                chosen_idx = int(action.data.get("chosen_index", 0))

                if 0 <= chosen_idx < len(cards):
                    chosen = cards[chosen_idx]
                    rejected = cards[1 - chosen_idx]

                    # Elegida al inventario
                    chosen_str = str(chosen)
                    
                    if chosen_str == "KEY":
                        # Logic for Key in Motemey Buy (pool base, no extra por Cámara Letal)
                        keys_in_hand = sum(pl.keys for pl in s.players.values())
                        keys_in_game = max(0, _get_base_keys_total(cfg) - s.keys_destroyed)
                        if keys_in_hand >= keys_in_game:
                            # No hay llaves disponibles -> devolver al mazo
                            s.motemey_deck.put_bottom(chosen)
                        else:
                            role_limit = get_max_keys_capacity(p)
                            if p.keys < role_limit:
                                p.keys += 1
                            else:
                                # Full of keys -> devolver al mazo
                                s.motemey_deck.put_bottom(chosen)
                    else:
                        # Logic for Objects
                        # Usar add_object para respetar límites
                        if not add_object(s, pid, chosen_str, discard_choice=action.data.get("discard_choice")):
                            # Fallo al agregar. Deberíamos revertir o manejar error.
                            pass

                    # Rechazada vuelve al fondo del mazo de Motemey
                    s.motemey_deck.put_bottom(rejected)

                    # Limpiar pending_choice
                    del s.pending_motemey_choice[str(pid)]
                    if len(s.pending_motemey_choice) == 0:
                        s.pending_motemey_choice = None
                    # Evento Motemey consumido
                    s.motemey_event_active = False

        elif action.type == ActionType.USE_MOTEMEY_SELL:
            # Venta: objeto normal +1, tesoro +3, clamped a sanity_max
            item_name = action.data.get("item_name", "")
            if item_name in p.objects and not is_soulbound(item_name):
                p.objects.remove(item_name)
                # Determinar si es tesoro (TREASURE_*) u objeto
                if str(item_name).startswith("TREASURE"):
                    _heal(p, 3)
                else:
                    _heal(p, 1)
                # Evento Motemey consumido
                s.motemey_event_active = False

        # ===== B4: PUERTAS AMARILLO (teleport) =====
        elif action.type == ActionType.USE_YELLOW_DOORS:
            # Teleporta a habitación del objetivo, objetivo pierde -1 sanidad
            target_id = PlayerId(action.data.get("target_player", ""))
            if target_id in s.players:
                target = s.players[target_id]
                # Actor teleportado a habitación del target
                p.room = target.room
                # Target pierde -1 sanidad
                apply_sanity_loss(s, target, 1, source="YELLOW_DOORS")
                # Reveal card en la habitación destino (on_enter)
                card = _reveal_one(s, p.room)
                if card is not None:
                    _resolve_card_minimal(s, pid, card, cfg, rng)

        # ===== B5: TABERNA (mirar 2 habitaciones) =====
        elif action.type == ActionType.USE_TABERNA_ROOMS:
            # CANON: Pagar 1 cordura, mirar 2 habitaciones, registrar peek
            apply_sanity_loss(s, p, 1, source="TABERNA")
            s.taberna_used_this_turn[pid] = True
            
            # CANON Fix #7: Registrar peek para determinismo/replay
            room_a = RoomId(action.data.get("room_a", ""))
            room_b = RoomId(action.data.get("room_b", ""))
            
            # Obtener carta top de cada habitación (sin extraer)
            from engine.boxes import active_deck_for_room
            deck_a = active_deck_for_room(s, room_a)
            deck_b = active_deck_for_room(s, room_b)
            
            card_a = deck_a.cards[deck_a.top] if deck_a and deck_a.remaining() > 0 else None
            card_b = deck_b.cards[deck_b.top] if deck_b and deck_b.remaining() > 0 else None
            
            # Registrar en state para replay
            # CANON Fix #C: Serializar last_peek
            # Note: s.last_peek needs to be added to GameState to be persistent.
            # For now we set it, ensure GameState has the field.
            s.last_peek = [{"room": str(room_a), "card": str(card_a)}, {"room": str(room_b), "card": str(card_b)}]

        # ===== B6: ARMERÍA (drop/take) =====
        elif action.type == ActionType.USE_ARMORY_DROP:
            # CANON: Dejar objeto en armeria (max 2 objetos)
            item_name = action.data.get("item_name", "")
            armory_room = p.room
            
            if armory_room not in s.armory_storage:
                s.armory_storage[armory_room] = []
            
            if len(s.armory_storage[armory_room]) < 2:
                if item_name in p.objects and not is_soulbound(item_name):
                    # DROP objeto
                    p.objects.remove(item_name)
                    s.armory_storage[armory_room].append(item_name)
        elif action.type == ActionType.USE_ARMORY_TAKE:
            # CANON: Tomar objeto de armeria
            armory_room = p.room
            if armory_room in s.armory_storage and len(s.armory_storage[armory_room]) > 0:
                item = s.armory_storage[armory_room].pop()
                if isinstance(item, dict):
                    # Compatibilidad con almacenamiento legacy
                    item_name = item.get("value", "")
                    if item.get("type") == "key":
                        p.keys += item.get("value", 1)
                    else:
                        if not add_object(s, pid, item_name, discard_choice=action.data.get("discard_choice")):
                            s.armory_storage[armory_room].append(item)
                else:
                    if not add_object(s, pid, item, discard_choice=action.data.get("discard_choice")):
                        s.armory_storage[armory_room].append(item)
        elif action.type == ActionType.USE_CAPILLA:
            # d6 + 2 de sanación
            d6 = rng.randint(1, 6)
            heal_amount = d6 + 2
            _heal(p, heal_amount)
            
            # Riesgo: Si d6 es 1, obtiene PARANOIA
            if d6 == 1:
                add_status(p, "PARANOIA")

        # ===== B7: SALÓN DE BELLEZA (Vanidad) =====
        elif action.type == ActionType.USE_SALON_BELLEZA:
            # Incrementar uso global
            s.salon_belleza_uses += 1
            
            # Efecto base: Protección (Imnunidad a eventos de Amarillo por 1 ronda)
            # Implementado como flag temporal o estado
            # Usaremos flag para simplificar
            s.flags[f"PROTECCION_AMARILLO_{pid}"] = s.round + 1
            
            # Cada 3er uso (global): VANIDAD
            # CANON Fix: Vanidad desde el 3er uso en adelante (>= 3)
            # User request: "el tercer jugador que activa... y los siguientes... recibiran vanidad"
            if s.salon_belleza_uses >= 3:
                add_status(p, "VANIDAD")

        # ===== B3: CÁMARA LETAL (ritual) =====
        # P1 - FASE 1.5.4: Ritual para obtener 7ª llave
        elif action.type == ActionType.USE_CAMARA_LETAL_RITUAL:
            if not s.flags.get("CAMARA_LETAL_RITUAL_COMPLETED", False):
                players_in_room = [
                    p_id for p_id, player in s.players.items()
                    if player.room == p.room
                ]

                if len(players_in_room) == 2:
                    # Lanzar D6 para determinar costo
                    d6 = rng.randint(1, 6)
                    key_recipient = pid # El actor recibe la llave por defecto

                    # Determinar costos según D6
                    costs = [0, 0]
                    if d6 in [1, 2]:
                        # Un jugador paga 7 (el otro 0). Actor paga 7 por defecto (riesgo)
                        costs = [7, 0]
                    elif d6 in [3, 4]:
                        # Reparto fijo: 3 y 4. Actor paga 4 (riesgo)
                        costs = [4, 3]
                    elif d6 in [5, 6]:
                        # Reparto libre: suma 7. Reparto equitativo 4, 3 para automatizar
                        costs = [4, 3]
                    
                    # Aplicar daño
                    # targets: [actor, otro]
                    # Encontrar al otro jugador
                    other_pids = [pid2 for pid2 in players_in_room if pid2 != pid]
                    if other_pids:
                        other_pid = other_pids[0]
                        targets = [pid, other_pid]
                        
                        for i, target_pid in enumerate(targets):
                            dmg = costs[i]
                            tp = s.players[target_pid]
                            if tp.sanity_max is not None:
                                apply_sanity_loss(s, tp, dmg, source="CAMARA_LETAL")
                            else:
                                 apply_sanity_loss(s, tp, dmg, source="CAMARA_LETAL")

                        # Éxito del ritual
                        s.flags["CAMARA_LETAL_RITUAL_COMPLETED"] = True
                        
                        # Otorgar llave
                        recipient = s.players[key_recipient]
                        keys_in_hand = sum(pl.keys for pl in s.players.values())
                        if keys_in_hand < _get_effective_keys_total(s, cfg) - s.keys_destroyed:
                             recipient.keys += 1
                        
                        # Marcar ritual como completado
                        s.flags["CAMARA_LETAL_D6"] = d6  # Para tracking



        # ===== FASE 4: Libro Chambers + Cuentos =====
        elif action.type == ActionType.USE_ATTACH_TALE:
             # Unir cuento al libro
             # Requisitos: Tener libro y tener el cuento
             # Asumimos que la acción es válida (legality checkeado o invocado por UI que sabe)
             # Pero verificaremos posesión del cuento.
             # Libro puede estar en otro, pero simplificamos a que el actor lo tiene o está en la misma room.
             # Para simplificar: el actor tiene el cuento.
             tale_id = action.data.get("tale_id")
             if tale_id in p.objects:
                 # Consumir cuento
                 p.objects.remove(tale_id)
                 
                 # Incrementar contador
                 s.chambers_tales_attached += 1
                 s.flags[f"TALE_ATTACHED_{tale_id}"] = True
                 
                 # Check Vanish (4to cuento)
                 if s.chambers_tales_attached >= 4:
                     s.king_vanished_turns = 4
                     s.action_log.append({"event": "KING_VANISHED", "turns": 4})

        # ===== FASE 1: ACCIONES DE ROLES =====
        elif action.type == ActionType.USE_HEALER_HEAL:
            # Healer: -1 propia -> +2 otros + Estado
            apply_sanity_loss(s, p, 1, source="HEALER_ABILITY")
            status_choice = action.data.get("status_choice", "SANIDAD")
            
            others = [op for opid, op in s.players.items() if opid != pid]
            for op in others:
                _heal(op, 2)
                # Duraciones default definidas en states_canonical
                add_status(op, status_choice)

        elif action.type == ActionType.USE_BLUNT:
            # Brawler/General: Usar objeto contundente
            use_object(s, pid, "BLUNT", cfg, rng)

        elif action.type == ActionType.USE_PORTABLE_STAIRS:
            # Escalera Portátil: Moverse +/- 1 piso
            direction = action.data.get("direction", "UP")
            current = floor_of(p.room)
            target = current + 1 if direction == "UP" else current - 1
            
            if 1 <= target <= 3:
                # Consumir objeto
                if consume_object(s, pid, "PORTABLE_STAIRS"):
                    p.room = corridor_id(target)
                    # Trigger entry hooks
                    _on_player_enters_room(s, pid, p.room)
                    card = _reveal_one(s, p.room)
                    if card is not None:
                        _resolve_card_minimal(s, pid, card, cfg, rng)

        # Descuento de acciones respetando free actions y overrides de roles
        cost_override = None
        if action.type == ActionType.USE_BLUNT:
            if brawler_blunt_free(p):
                cost_override = 0
                
        cost = _consume_action_if_needed(action.type, cost_override=cost_override)

        # FASE 1: Scout Free Move Logic
        # Si es Scout, es MOVER, y no ha usado su movimiento gratis: Costo 0
        if action.type == ActionType.MOVE and getattr(p, "role_id", "") == "SCOUT":
             if not p.free_move_used_this_turn:
                 cost = 0
                 p.free_move_used_this_turn = True

        if cost > 0:
            s.remaining_actions[pid] = max(0, s.remaining_actions.get(pid, 0) - cost)

        _update_umbral_flags(s, cfg)
        _apply_minus5_transitions(s, cfg)

        if s.remaining_actions.get(pid, 0) <= 0:
            if action.type == ActionType.END_TURN:
                _advance_turn_or_king(s)

        return _finalize_and_return(s, cfg)
    # FASE REY (fin de ronda)
    # -------------------------
    if s.phase == "KING" and action.type == ActionType.KING_ENDROUND:
        # PASO 1: Casa (configurable) a todos
        for p in s.players.values():
            apply_sanity_loss(s, p, cfg.HOUSE_LOSS_PER_ROUND, source="HOUSE_LOSS")

        # Verificar Vanish
        king_active = True
        if s.king_vanished_turns > 0:
            s.king_vanished_turns -= 1
            king_active = False
            # Log de vanish skip?
        
        if king_active:
            # PASO 2: Ruleta d4 para determinar nuevo piso (canon P0)
            d4 = rng.randint(1, 4)
            rng.last_king_d4 = d4  # Track for logging
            new_floor = ruleta_floor(s.king_floor, d4)

            # Excepción: si cae en piso del Falso Rey, repetir HASTA QUE sea distinto (canon P0)
            fk_floor = _current_false_king_floor(s)
            while fk_floor is not None and new_floor == fk_floor:
                d4 = rng.randint(1, 4)
                rng.last_king_d4 = d4
                new_floor = ruleta_floor(s.king_floor, d4)
                fk_floor = _current_false_king_floor(s)
            
            s.king_floor = new_floor

            # PASO 3: Daño por presencia del Rey (en piso NUEVO, después de llegar)
            if s.round >= cfg.KING_PRESENCE_START_ROUND:
                pres = _presence_damage_for_round(s.round)
                for p in s.players.values():
                    if floor_of(p.room) == s.king_floor:
                        apply_sanity_loss(s, p, pres, source="KING_PRESENCE")

            # PASO 4: Efecto d6 aleatorio
            # CANON: Falso Rey y jugadores en su piso son INMUNES a TODO d6
            d6 = rng.randint(1, 6)
            rng.last_king_d6 = d6  # Track for logging
            fk_floor = _current_false_king_floor(s)
            
            if d6 == 1:
                # Rotación intra-floor (variante engine)
                s.flags["king_d6_intra_rotation"] = True
            elif d6 == 2:
                # -1 cordura (excepto piso FK)
                for p in s.players.values():
                    if fk_floor is None or floor_of(p.room) != fk_floor:
                        apply_sanity_loss(s, p, 1, source="KING_D6_2")
            elif d6 == 3:
                s.limited_action_floor_next = s.king_floor
            elif d6 == 4:
                # Expulsar (excepto piso FK)
                _expel_players_from_floor_except_fk(s, s.king_floor, fk_floor)
            elif d6 == 5:
                # Atraer (excepto piso FK)
                _attract_players_to_floor_except_fk(s, s.king_floor, fk_floor)
            elif d6 == 6:
                # Descartar objeto (excepto piso FK)
                for p in s.players.values():
                    if fk_floor is None or floor_of(p.room) != fk_floor:
                        discardable = [obj for obj in p.objects if not is_soulbound(obj)]
                        if discardable:
                            p.objects.remove(discardable[-1])


        # PASO 4.4: FASE DE MONSTRUOS (Ataque/Stun)
        _monster_phase(s, cfg)

        # PASO 4.5: Aplicar efectos de estados al final de ronda (ANTES de tick)
        _apply_status_effects_end_of_round(s)

        # PASO 5: Tick estados (decremento de duraciones)
        for p in s.players.values():
            decrement_status_durations(p)

        # Check defeat finally
        if not s.flags.get(PENDING_SACRIFICE_FLAG):
            _check_defeat(s, cfg)

        # PASO 6: Check del Falso Rey
        _false_king_check(s, rng, cfg)

        _update_umbral_flags(s, cfg)
        _apply_minus5_transitions(s, cfg)
        _roll_stairs(s, rng)
        if s.flags.get("king_d6_intra_rotation"):
            s.box_at_room = rotate_boxes_intra_floor(s.box_at_room)
            # Consumir flag
            s.flags["king_d6_intra_rotation"] = False
        else:
            s.box_at_room = rotate_boxes(s.box_at_room)
        ensure_canonical_rooms(s)
        sync_room_decks_from_boxes(s)

        _end_of_round_checks(s, cfg)

        s.round += 1
        if not s.game_over:
            _start_new_round(s, cfg)

        return _finalize_and_return(s, cfg)


def _monster_phase(s: GameState, cfg: Config) -> None:
    """
    Fase de Monstruos (Fin de Ronda):
    1. Movimiento de monstruos (si no están STUNNED).
    2. Ataque básico (1 daño cordura) a jugadores en la misma habitación.
    3. Decremento de STUN (si están STUNNED no atacan ni mueven en este turno).
    """
    # 1. Movimiento
    _move_monsters(s, cfg)

    # 2. Ataque y Gestión de STUN
    for m in s.monsters:
        if m.stunned_remaining_rounds > 0:
            m.stunned_remaining_rounds -= 1
        else:
            # Ataca a todos los jugadores en su habitación
            # CANON: 1 daño de cordura
            for p in s.players.values():
                if p.room == m.room:
                    # Excepción: TUE_TUE y otros no atacan pasivamente, solo on reveal. 
                    # Pero el usuario no lo especificó para fin de ronda.
                    # Asumimos que TUE-TUE es inerte físicamente (solo reveal).
                    # Araña, Duende, Viejo son físicos.
                    mid = m.monster_id
                    if "TUE_TUE" not in mid:
                        apply_sanity_loss(s, p, 1, source=f"MONSTER_ATTACK_{mid}")


def _move_monsters(s: GameState, cfg: Config) -> None:
    """
    Lógica de movimiento de monstruos (AI).
    """
    from engine.board import get_next_move_to_targets, is_corridor
    
    player_rooms = {p.room for p in s.players.values()}
    
    for m in s.monsters:
        # Si está stuneado, no se mueve
        if m.stunned_remaining_rounds > 0:
            continue

        # ID Normalizado
        mid = m.monster_id
        
        # Lógica por tipo
        # ----------------------------------------------------
        
        # 1. ARAÑA (SPIDER): Hunt if no players present
        if "SPIDER" in mid or "ARAÑA" in mid:
            # Si ya está en una habitación con jugador, no se mueve (ataca)
            if m.room in player_rooms:
                continue
            
            # Mover hacia el objetivo más cercano
            next_room = get_next_move_to_targets(m.room, player_rooms)
            if next_room != m.room:
                m.room = next_room
                _on_monster_enters_room(s, next_room)
                
        # 2. DUENDE (GOBLIN): Flee closer if no loot, flee away if loot?
        # Canon: "si tiene objetos se aleja de los jugadores y sino se acerca"
        elif "DUENDE" in mid or "GOBLIN" in mid:
            has_loot = s.flags.get(f"GOBLIN_HAS_LOOT_{mid}", False)
            if has_loot:
                # Flee logic: maximizar distancia
                from engine.board import get_next_move_away_from_targets
                next_room = get_next_move_away_from_targets(m.room, player_rooms)
            else:
                # Hunt logic: acercarse para robar
                if m.room in player_rooms:
                    continue # Ya está ahí para robar (on reveal robó, pero quizás quiere robar a otros?)
                next_room = get_next_move_to_targets(m.room, player_rooms)
            
            if next_room != m.room:
                m.room = next_room
                _on_monster_enters_room(s, next_room)
        
        # 3. VIEJO DEL SACO (SACK): 
        # "Si tiene un jugador atrapado se aleja de los jugadores y si no tiene, se acerca"
        elif "VIEJO" in mid or "SACK" in mid:
            has_victim = s.flags.get(f"SACK_HAS_VICTIM_{mid}", False)
            # Verificar si la víctima sigue atrapada?
            # Asumimos flag es source of truth o revisamos TRAPPED status check?
            # Por simplicidad usamos flag, aunque si escapa deberíamos limpiar flag.
            
            if has_victim:
                from engine.board import get_next_move_away_from_targets
                next_room = get_next_move_away_from_targets(m.room, player_rooms)
            else:
                if m.room in player_rooms:
                    continue
                next_room = get_next_move_to_targets(m.room, player_rooms)
            
            if next_room != m.room:
                m.room = next_room
                _on_monster_enters_room(s, next_room)

        # 4. REINA HELADA: Estática (bloquea piso on reveal)
        elif "REINA" in mid or "HELADA" in mid:
            pass

        # 5. TUE-TUE: Inamovible (solo reveal mechanics)
        else:
            # Comportamiento Default: Hunt (Zombie, etc)
            if m.room in player_rooms:
                continue
            next_room = get_next_move_to_targets(m.room, player_rooms)
            if next_room != m.room:
                m.room = next_room
                _on_monster_enters_room(s, next_room)

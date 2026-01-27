from __future__ import annotations
from typing import Optional

from engine.actions import Action, ActionType
from engine.board import corridor_id, floor_of, ruleta_floor, rotate_boxes, rotate_boxes_intra_floor, get_next_move_to_targets, get_next_move_away_from_targets, is_corridor
from engine.boxes import active_deck_for_room, sync_room_decks_from_boxes
from engine.config import Config
from engine.legality import get_legal_actions
from engine.rng import RNG
from engine.state import GameState, StatusInstance, ensure_canonical_rooms
from engine.types import PlayerId, RoomId, CardId
from engine.roles import get_scout_actions, brawler_blunt_free
from engine.objects import use_object, is_soulbound, OBJECT_CATALOG
from engine.inventory import get_inventory_limits
from engine.rules.actions_cost import consume_action_cost
from engine.handlers.special_rooms import handle_special_room_action
from engine.rules.sanity import sanity_cap
from engine.rules.sacrifice import available_sacrifice_options
from engine.rules.victory_defeat import can_win, can_lose_all_minus5, can_lose_keys_destroyed
from engine.inventory import consume_object
from engine.systems.sanity import heal_player, apply_sanity_loss
from engine.systems.player import apply_player_action
from engine.systems.king import resolve_king_phase
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
)
from engine.effects.states_canonical import has_status, decrement_status_durations, remove_all_statuses
from engine.effects.event_utils import add_status

# Flag constant for sacrifice interrupt
PENDING_SACRIFICE_FLAG = "PENDING_SACRIFICE_CHECK"


def _sanity_cap(p) -> int:
    return sanity_cap(p)


def _heal(p, amount: int) -> None:
    heal_player(p, amount)



def _available_sacrifice_options(p) -> dict:
    return available_sacrifice_options(p)


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



def _consume_action_if_needed(action_type: ActionType, cost_override: Optional[int] = None) -> int:
    return consume_action_cost(action_type, cost_override)


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
    if not can_win(s, cfg):
        return False

    # Victoria!
    s.game_over = True
    s.outcome = "WIN"
    return True


def _check_defeat(s, cfg) -> bool:
    """
    Condiciones de DERROTA canónicas:
    1. Todos los jugadores en -5 cordura
    2. Solo quedan <= 3 llaves en juego
    """
    # Condicion 1: Todos en -5
    if can_lose_all_minus5(s, cfg):
        s.game_over = True
        source = s.last_sanity_loss_event or "UNKNOWN"
        s.outcome = f"LOSE_ALL_MINUS5 ({source})"
        return True

    # Condicion 2: <= KEYS_LOSE_THRESHOLD llaves en juego
    # Solo aplica si se han destruido llaves (keys_destroyed > 0)
    if can_lose_keys_destroyed(s, cfg):
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
                last_round = getattr(p, "last_minus5_round", -1)
                if last_round == s.round:
                    p.at_minus5 = True
                    p.last_minus5_round = s.round
                    continue
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
    p.last_minus5_round = s.round


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
        return apply_player_action(s, action, rng, cfg)

    if s.phase == "KING" and action.type == ActionType.KING_ENDROUND:
        return resolve_king_phase(s, action, rng, cfg)

    return _finalize_and_return(s, cfg)



def _apply_player_action(s: GameState, action: Action, rng: RNG, cfg: Config) -> GameState:
    pid = PlayerId(action.actor)
    p = s.players[pid]

    # CANON: No hay auto-escape. Escape es manual via ESCAPE_TRAPPED action.

    if action.type == ActionType.MOVE:
        to = RoomId(action.data["to"])
        from_room = p.room # Capture before update
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
    
        # CANON Rule: Hallway Peeking (Room -> Hallway on same floor)
        # Si aplica, se dispara el flag y NO se revela carta en el pasillo.
        if not is_corridor(from_room) and is_corridor(to) and previous_floor == new_floor:
             s.flags["PENDING_HALLWAY_PEEK"] = str(pid)
        else:
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

    # Hallway Peek Actions
    elif action.type == ActionType.PEEK_ROOM_DECK:
         target_room = RoomId(action.data["room_id"])
         # Verificar que es una habitación válida del piso actual
         if floor_of(target_room) != floor_of(p.room) or is_corridor(target_room):
             raise ValueError("Invalid room for peek")
         
         deck = active_deck_for_room(s, target_room)
         if deck and deck.remaining() > 0:
             card = deck.cards[deck.top]
             # No revelamos (no incrementamos revealed count ni loopeamos efectos)
             # Solo "mirar y devolver".
             # El usuario lo verá en el log o UI.
             s.action_log.append({"event": "PEEK_RESULT", "room": str(target_room), "card": str(card)})
     
         # Clear flag
         if s.flags.get("PENDING_HALLWAY_PEEK") == str(pid):
             del s.flags["PENDING_HALLWAY_PEEK"]
         
    elif action.type == ActionType.SKIP_PEEK:
         # Just clear flag
         if s.flags.get("PENDING_HALLWAY_PEEK") == str(pid):
             del s.flags["PENDING_HALLWAY_PEEK"]

    # Acciones de habitaciones especiales
    elif handle_special_room_action(s, pid, action, rng, cfg):
        pass



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



def _resolve_king_phase(s: GameState, action: Action, rng: RNG, cfg: Config) -> GameState:
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
        fk_floor = legacy_current_false_king_floor(s)
        while fk_floor is not None and new_floor == fk_floor:
            d4 = rng.randint(1, 4)
            rng.last_king_d4 = d4
            new_floor = ruleta_floor(s.king_floor, d4)
            fk_floor = legacy_current_false_king_floor(s)
    
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
        fk_floor = legacy_current_false_king_floor(s)
    
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

    legacy_end_of_round_checks(s, cfg)

    s.round += 1
    if not s.game_over:
        _start_new_round(s, cfg)

    return _finalize_and_return(s, cfg)





def _monster_phase(s: GameState, cfg: Config) -> None:
    legacy_monster_phase(s, cfg)


def _move_monsters(s: GameState, cfg: Config) -> None:
    legacy_move_monsters(s, cfg)


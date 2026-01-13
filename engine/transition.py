from __future__ import annotations
from typing import Optional

from engine.actions import Action, ActionType
from engine.board import corridor_id, floor_of, ruleta_floor, rotate_boxes
from engine.boxes import active_deck_for_room, sync_room_decks_from_boxes
from engine.config import Config
from engine.legality import get_legal_actions
from engine.rng import RNG
from engine.state import GameState, StatusInstance
from engine.types import PlayerId, RoomId

def _clamp_all_sanity(s, cfg):
    # -5 es piso: no se puede bajar más
    for pl in s.players.values():
        if pl.sanity < cfg.S_LOSS:
            pl.sanity = cfg.S_LOSS
        # cap superior (sanity_max) si existe
        if getattr(pl, "sanity_max", None) is not None and pl.sanity > pl.sanity_max:
            pl.sanity = pl.sanity_max


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


def _finalize_step(s, cfg):
    # clamp de cordura (siempre)
    _clamp_all_sanity(s, cfg)
    _cap_monsters(s, cfg)

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
    
    if s_str == "KEY":
        # Ganador de llave: cap por KEYS_TOTAL - keys_destroyed
        keys_in_hand = sum(pl.keys for pl in s.players.values())
        keys_in_game = max(0, cfg.KEYS_TOTAL - s.keys_destroyed)
        if keys_in_hand < keys_in_game:
            p.keys += 1
        return
    
    if s_str.startswith("MONSTER:"):
        mid = s_str.split(":", 1)[1]
        # Solo agregar si no hemos alcanzado el cap
        cap = int(getattr(cfg, "MAX_MONSTERS_ON_BOARD", 0) or 0)
        if cap <= 0 or len(s.monsters) < cap:
            from engine.state import MonsterState
            s.monsters.append(MonsterState(monster_id=mid, room=p.room))
        return
    
    if s_str.startswith("STATE:"):
        sid = s_str.split(":", 1)[1]
        p.statuses.append(StatusInstance(status_id=sid, remaining_rounds=2))
        return
    
    if s_str == "CROWN":
        # Falso Rey aparece en el piso del jugador que tomó la corona (canon P0)
        if not s.flags.get("CROWN_YELLOW"):
            s.flags["CROWN_YELLOW"] = True
            s.flags["CROWN_HOLDER"] = str(pid)
            # Piso inicial del Falso Rey (cuando se revela CROWN)
            s.false_king_floor = floor_of(p.room)
            s.false_king_round_appeared = s.round
        return


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
                # Destroy keys and objects, track globally
                s.keys_destroyed += p.keys
                p.keys = 0
                p.objects = []
                
                # Other players lose 1 sanity
                for other_pid, other in s.players.items():
                    if other_pid != pid:
                        other.sanity -= 1
                
                # Mark as in -5 state
                p.at_minus5 = True
            
            # Maintain 1 action per turn while at -5
            s.remaining_actions[pid] = min(1, s.remaining_actions.get(pid, 2))
        else:  # Above -5
            if p.at_minus5:  # Just left -5
                # Restore to 2 actions
                p.at_minus5 = False
                s.remaining_actions[pid] = 2


def _current_false_king_floor(s) -> Optional[int]:
    holder_id = s.flags.get("CROWN_HOLDER") if s.flags else None
    if not holder_id:
        return s.false_king_floor
    holder = s.players.get(PlayerId(holder_id))
    if holder is None:
        return s.false_king_floor
    return floor_of(holder.room)

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
    sanity_max = holder.sanity_max if holder.sanity_max is not None else holder.sanity
    threshold = int(sanity_max) + 2 + int(rounds_since)
    total = rng.randint(1, 6) + max(0, int(holder.sanity))

    if total <= threshold:
        pres = _presence_damage_for_round(s.round)
        for p in s.players.values():
            if floor_of(p.room) == fk_floor:
                p.sanity -= pres


def _end_of_round_checks(s, cfg):
    if s.game_over:
        return

    if s.players and all(p.sanity <= cfg.S_LOSS for p in s.players.values()):
        s.game_over = True
        s.outcome = "LOSE"
        return

    keys_in_game = int(cfg.KEYS_TOTAL) - int(getattr(s, "keys_destroyed", 0))
    if keys_in_game <= int(cfg.KEYS_LOSE_THRESHOLD):
        s.game_over = True
        s.outcome = "LOSE"
        return

    total_keys = sum(p.keys for p in s.players.values())
    if total_keys >= int(cfg.KEYS_TO_WIN) and all(p.at_umbral for p in s.players.values()):
        s.game_over = True
        s.outcome = "WIN"


def _start_new_round(s, cfg):
    order = s.turn_order
    if not order:
        s.phase = "PLAYER"
        return

    s.starter_pos = (s.starter_pos + 1) % len(order)
    s.turn_pos = s.starter_pos
    s.phase = "PLAYER"

    for pid in order:
        actions = 2
        if s.limited_action_floor_next is not None:
            if floor_of(s.players[pid].room) == s.limited_action_floor_next:
                actions = min(actions, 1)
        if s.players[pid].sanity <= cfg.S_LOSS:
            actions = min(actions, 1)
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

    # -------------------------
    # FASE JUGADOR
    # -------------------------
    if s.phase == "PLAYER":
        pid = PlayerId(action.actor)
        p = s.players[pid]
        cost = 0

        if action.type == ActionType.MOVE:
            cost = 1
            to = RoomId(action.data["to"])
            p.room = to
            card = _reveal_one(s, to)
            if card is not None:
                _resolve_card_minimal(s, pid, card, cfg, rng)

        elif action.type == ActionType.SEARCH:
            cost = 1
            card = _reveal_one(s, p.room)
            if card is not None:
                _resolve_card_minimal(s, pid, card, cfg, rng)

        elif action.type == ActionType.MEDITATE:
            cost = 1
            p.sanity = min(p.sanity + 1, p.sanity_max or p.sanity)

        elif action.type == ActionType.END_TURN:
            s.remaining_actions[pid] = 0

        if cost > 0:
            s.remaining_actions[pid] = max(0, s.remaining_actions.get(pid, 0) - cost)

        _update_umbral_flags(s, cfg)
        _apply_minus5_transitions(s, cfg)

        if s.remaining_actions.get(pid, 0) <= 0:
            _advance_turn_or_king(s)

        return _finalize_and_return(s, cfg)

    # -------------------------
    # FASE REY (fin de ronda)
    # -------------------------
    if s.phase == "KING" and action.type == ActionType.KING_ENDROUND:
        # PASO 1: Casa (configurable) a todos
        for p in s.players.values():
            p.sanity -= cfg.HOUSE_LOSS_PER_ROUND

        if s.king_vanish_ends > 0:
            s.king_vanish_ends -= 1
        else:
            # PASO 3: Ruleta d4 para determinar nuevo piso (canon P0)
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

            # PASO 2: Daño por presencia del Rey (en piso NUEVO, después de llegar)
            if s.round >= cfg.KING_PRESENCE_START_ROUND:
                pres = _presence_damage_for_round(s.round)
                for p in s.players.values():
                    if floor_of(p.room) == s.king_floor:
                        p.sanity -= pres

            # PASO 4: Efecto d6 aleatorio
            d6 = rng.randint(1, 6)
            rng.last_king_d6 = d6  # Track for logging
            if d6 == 1:
                _shuffle_all_room_decks(s, rng)
            elif d6 == 2:
                for p in s.players.values():
                    p.sanity -= 1
            elif d6 == 3:
                s.limited_action_floor_next = s.king_floor
            elif d6 == 4:
                _expel_players_from_floor(s, s.king_floor)
            elif d6 == 5:
                _attract_players_to_floor(s, s.king_floor)
            elif d6 == 6:
                for p in s.players.values():
                    if p.objects:
                        p.objects.pop()

        # PASO 5: Tick estados (decremento de duraciones)
        for p in s.players.values():
            for st in p.statuses:
                st.remaining_rounds -= 1
            p.statuses = [st for st in p.statuses if st.remaining_rounds > 0]

        # PASO 6: Check del Falso Rey
        _false_king_check(s, rng, cfg)

        _update_umbral_flags(s, cfg)
        _apply_minus5_transitions(s, cfg)
        _roll_stairs(s, rng)
        s.box_at_room = rotate_boxes(s.box_at_room)
        sync_room_decks_from_boxes(s)

        _end_of_round_checks(s, cfg)

        s.round += 1
        if not s.game_over:
            _start_new_round(s, cfg)

        return _finalize_and_return(s, cfg)

    raise ValueError(f"Invalid phase/action combination: phase={s.phase}, action={action}")

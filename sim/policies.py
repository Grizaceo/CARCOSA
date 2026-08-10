from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any
import json
import inspect
from pathlib import Path

from engine.actions import Action, ActionType
from engine.config import Config
from engine.boxes import active_deck_for_room
from engine.legality import get_legal_actions
from engine.rng import RNG
from engine.state import GameState
from engine.tension import king_utility
from engine.transition import step
from engine.types import RoomId, PlayerId

from engine.board import floor_of, neighbors, is_corridor, corridor_id
from sim.memory import (
    PRIORITY_EVENT,
    PRIORITY_KEY,
    PRIORITY_MONSTER,
    PRIORITY_OMEN,
    PRIORITY_TREASURE,
    card_priority,
)
from sim.pathing import bfs_next_step
from engine.inventory import get_inventory_limits, get_object_count, get_key_count
from engine.objects import is_soulbound


def _get_active_actor(state: GameState) -> str:
    # 1. Check Interrupts
    pending = state.flags.get("PENDING_SACRIFICE_CHECK")
    if isinstance(pending, list):
        pending = pending[0] if pending else None
    if pending:
        return str(pending)
    # 2. Normal Turn
    pid = state.turn_order[state.turn_pos]
    return str(pid)


class PlayerPolicy:
    def choose(self, state: GameState, rng: RNG) -> Action:
        raise NotImplementedError


class KingPolicy:
    def choose(self, state: GameState, rng: RNG) -> Action:
        raise NotImplementedError


def _keys_total(state: GameState) -> int:
    return sum(p.keys for p in state.players.values())


_POLICY_PARAMS_CACHE: Optional[Dict[str, Any]] = None


def _load_policy_params() -> Dict[str, Any]:
    global _POLICY_PARAMS_CACHE
    if _POLICY_PARAMS_CACHE is not None:
        return _POLICY_PARAMS_CACHE
    path = Path(__file__).with_name("policy_params.json")
    if not path.exists():
        _POLICY_PARAMS_CACHE = {}
        return _POLICY_PARAMS_CACHE
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            _POLICY_PARAMS_CACHE = json.load(f) or {}
    except Exception:
        _POLICY_PARAMS_CACHE = {}
    return _POLICY_PARAMS_CACHE


def refresh_policy_params() -> None:
    global _POLICY_PARAMS_CACHE
    _POLICY_PARAMS_CACHE = None


def _pick_first(actions: List[Action], t: ActionType) -> Optional[Action]:
    for a in actions:
        if a.type == t:
            return a
    return None


def _pick_use_object(actions: List[Action], object_id: str) -> Optional[Action]:
    for a in actions:
        if a.type == ActionType.USE_OBJECT and a.data.get("object_id") == object_id:
            return a
    return None


def _pick_move_to_corridor(actions: List[Action], floor: int) -> Optional[Action]:
    target = corridor_id(floor)
    for a in actions:
        if a.type == ActionType.MOVE and a.data.get("to") == str(target):
            return a
    return None


def _temp_stairs_dest(
    state: GameState, room: RoomId, target_floor: int
) -> Optional[RoomId]:
    f = floor_of(room)
    if target_floor == f:
        return None
    step = 1 if target_floor > f else -1
    suffix = str(room).split("_", 1)[1]
    dest = RoomId(f"F{f + step}_{suffix}")
    return dest if dest in state.rooms else None


def _temp_stairs_active_for_pid(state: GameState, room: RoomId, pid: PlayerId) -> bool:
    key = f"TEMP_STAIRS_{room}"
    flag = state.flags.get(key)
    if isinstance(flag, dict):
        return flag.get("round") == state.round and flag.get("pid") == str(pid)
    return False


def _room_remaining(state: GameState, rid: RoomId) -> int:
    rs = state.rooms.get(rid)
    if not rs:
        return 0
    return rs.deck.remaining()


def _best_room_global(state: GameState) -> Optional[RoomId]:
    best: Optional[Tuple[int, str, RoomId]] = None  # (remaining, tie_break, rid)
    for rid, room in state.rooms.items():
        s = str(rid)
        if s.endswith("_P"):
            continue
        rem = room.deck.remaining()
        if rem <= 0:
            continue
        cand = (rem, s, rid)
        if best is None or cand > best:
            best = cand
    return best[2] if best else None


def _best_room_global_filtered(
    state: GameState, avoid_floor: Optional[int] = None
) -> Optional[RoomId]:
    best: Optional[Tuple[int, str, RoomId]] = None  # (remaining, tie_break, rid)
    for rid, room in state.rooms.items():
        s = str(rid)
        if s.endswith("_P"):
            continue
        if avoid_floor is not None and floor_of(rid) == avoid_floor:
            continue
        rem = room.deck.remaining()
        if rem <= 0:
            continue
        cand = (rem, s, rid)
        if best is None or cand > best:
            best = cand
    return best[2] if best else None


def _pick_move_to(actions: List[Action], dest: RoomId) -> Optional[Action]:
    dest_str = str(dest)
    for a in actions:
        if a.type == ActionType.MOVE and a.data.get("to") == dest_str:
            return a
    return None


ARMORY_STREAK_LIMIT = 2
STALL_KEY_STEPS = 24

_POLICY_TRACKING = {}


def _policy_flags(state: GameState) -> dict:
    return _POLICY_TRACKING.setdefault(id(state), {})


def _policy_update_stall(state: GameState, keys_total: int) -> int:
    flags = _policy_flags(state)
    last = int(flags.get("POLICY_LAST_KEYS_TOTAL", keys_total))
    steps = int(flags.get("POLICY_NO_KEY_STEPS", 0))
    if keys_total > last:
        steps = 0
    else:
        steps += 1
    flags["POLICY_LAST_KEYS_TOTAL"] = keys_total
    flags["POLICY_NO_KEY_STEPS"] = steps
    return steps


def _policy_armory_streak(state: GameState, pid: PlayerId) -> int:
    flags = _policy_flags(state)
    return int(flags.get(f"POLICY_ARMORY_STREAK_{pid}", 0))


def _policy_record_action(state: GameState, pid: PlayerId, action: Action) -> None:
    flags = _policy_flags(state)
    if action.type in (ActionType.USE_ARMORY_DROP, ActionType.USE_ARMORY_TAKE):
        flags[f"POLICY_ARMORY_STREAK_{pid}"] = (
            int(flags.get(f"POLICY_ARMORY_STREAK_{pid}", 0)) + 1
        )
    else:
        flags[f"POLICY_ARMORY_STREAK_{pid}"] = 0
    flags[f"POLICY_LAST_ACTION_{pid}"] = action.type.value


def _choose_sacrifice_action(
    acts: List[Action], state: GameState, pid: PlayerId, cfg: Config
) -> Optional[Action]:
    """
    Decide entre SACRIFICE y ACCEPT_SACRIFICE con foco en evitar destruccion de llaves.
    - Si el jugador lleva llaves, prioriza SACRIFICE.
    - Si el equipo esta fragil, prioriza SACRIFICE para evitar cascadas.
    - Si no hay riesgo, puede ACCEPT para evitar penalidades permanentes.
    """
    p = state.players[pid]
    sac_actions = [a for a in acts if a.type == ActionType.SACRIFICE]
    acc_action = _pick_first(acts, ActionType.ACCEPT_SACRIFICE)
    if not sac_actions:
        return acc_action

    team_critical = sum(1 for pl in state.players.values() if pl.sanity <= -4)
    other_key_critical = any(
        (pl.player_id != pid and pl.keys > 0 and pl.sanity <= -4)
        for pl in state.players.values()
    )
    close_to_win = _keys_total(state) >= max(0, cfg.KEYS_TO_WIN - 1)

    prefer_sacrifice = True

    # Solo ACEPTAR el -5 si el costo de sacrificar es demasiado alto
    # (ej. max_sanity <= 0 y no hay items basura) y no llevamos llaves.
    if p.keys == 0 and p.sanity_max <= 0 and p.object_slots_penalty >= 2:
        if not team_critical >= 1 and not other_key_critical and not close_to_win:
            prefer_sacrifice = False

    if not prefer_sacrifice and acc_action is not None:
        return acc_action

    def _sacrifice_cost(a: Action) -> float:
        mode = a.data.get("mode")
        if mode == "OBJECT_SLOT":
            drop = a.data.get("discard_object_id")
            if not drop:
                return 0.25
            cost = 1.0
            if str(drop).startswith("TREASURE"):
                cost += 2.0
            if is_soulbound(str(drop)):
                cost += 3.0
            return cost
        if mode == "SANITY_MAX":
            base = 1.5
            if p.sanity_max is not None and p.sanity_max <= 0:
                base += 1.5
            return base
        return 2.0

    return min(sac_actions, key=_sacrifice_cost)


def _peek_card_value(card_id: str) -> float:
    priority = card_priority(card_id)
    if priority == PRIORITY_KEY:
        return 4.0
    if priority == PRIORITY_MONSTER:
        return 2.0
    if priority == PRIORITY_TREASURE:
        return 1.5
    if priority in (PRIORITY_EVENT, PRIORITY_OMEN):
        return 0.8
    return 0.5


def _choose_hallway_peek_action(
    acts: List[Action],
    state: GameState,
    team_memory=None,
) -> Optional[Action]:
    """Si hay interrupt de hallway peek, selecciona la mejor sala a observar."""
    peek_actions = [a for a in acts if a.type == ActionType.PEEK_ROOM_DECK]
    skip_action = _pick_first(acts, ActionType.SKIP_PEEK)

    if not peek_actions:
        return skip_action

    best_action = None
    best_score = float("-inf")

    for action in peek_actions:
        room_raw = action.data.get("room_id")
        if not room_raw:
            continue
        room = RoomId(room_raw)
        deck = active_deck_for_room(state, room)
        if deck is None or deck.remaining() <= 0 or deck.top >= len(deck.cards):
            continue

        card = str(deck.cards[deck.top])
        base = _peek_card_value(card)
        rem = deck.remaining()
        novelty = 1.0

        if team_memory is not None:
            known_cards = team_memory.get_card_info(str(room))
            if any(
                c.card_id == card and c.position_in_deck == deck.top
                for c in known_cards
            ):
                novelty = 0.25
            elif known_cards:
                novelty = 0.7

        score = (base * novelty) + (0.05 * rem)
        if score > best_score:
            best_score = score
            best_action = action

    if best_action is not None:
        return best_action
    return skip_action


def _choose_forced_action(
    acts: List[Action],
    state: GameState,
    pid: PlayerId,
    rng: RNG,
    cfg: Config,
    team_memory=None,
) -> Optional[Action]:
    # Hallway peek interrupt: solo PEEK/SKIP son legales
    peek_choice = _choose_hallway_peek_action(acts, state, team_memory=team_memory)
    if peek_choice is not None:
        return peek_choice

    # Pending sacrifice: only SACRIFICE/ACCEPT are legal
    if _pick_first(acts, ActionType.ACCEPT_SACRIFICE):
        choice = _choose_sacrifice_action(acts, state, pid, cfg)
        return choice if choice is not None else rng.choice(acts)

    # TRAPPED: only ESCAPE_TRAPPED (and maybe SACRIFICE) are legal
    if any(a.type == ActionType.ESCAPE_TRAPPED for a in acts):
        allowed = {
            ActionType.ESCAPE_TRAPPED,
            ActionType.SACRIFICE,
            ActionType.END_TURN,
            ActionType.DISCARD_SANIDAD,
        }
        if all(a.type in allowed for a in acts):
            a = _pick_first(acts, ActionType.ESCAPE_TRAPPED)
            return a if a is not None else rng.choice(acts)

    return None


def _choose_special_action(
    acts: List[Action],
    state: GameState,
    pid: PlayerId,
    rng: RNG,
    cfg: Config,
    avoid_armory: bool = False,
    armory_streak: int = 0,
    avoid_salon: bool = False,
    key_progress_only: bool = False,
    risk_averse: bool = False,
) -> Optional[Action]:
    p = state.players[pid]

    # Reacción inmediata: BLUNT si hay monstruo en la sala
    if any(m.room == p.room for m in state.monsters):
        a = _pick_first(acts, ActionType.USE_BLUNT)
        if a:
            return a

    # Motemey: si hay elección pendiente, resolver
    choose = [a for a in acts if a.type == ActionType.USE_MOTEMEY_BUY_CHOOSE]
    if choose:
        return rng.choice(choose)

    # Motemey: comprar si hay espacio o falta llaves
    buy = _pick_first(acts, ActionType.USE_MOTEMEY_BUY_START)
    if buy and not risk_averse:
        key_slots, obj_slots = get_inventory_limits(p)
        if get_object_count(p) < obj_slots or get_key_count(p) < key_slots:
            if p.sanity >= 2:
                return buy

    # Motemey: vender si cordura baja
    if not key_progress_only and p.sanity <= 1:
        sell_actions = [a for a in acts if a.type == ActionType.USE_MOTEMEY_SELL]
        # Preferir no tesoros
        for a in sell_actions:
            item = a.data.get("item_name", "")
            if not str(item).startswith("TREASURE"):
                return a
        if sell_actions:
            return sell_actions[0]

    # Taberna: usar si cordura suficiente y faltan llaves
    taberna_actions = [a for a in acts if a.type == ActionType.USE_TABERNA_ROOMS]
    if taberna_actions and p.sanity >= 2 and not risk_averse:
        if _keys_total(state) < cfg.KEYS_TO_WIN:
            # Elegir la combinación con más cartas restantes
            best = None
            best_score = -1
            for a in taberna_actions:
                ra = RoomId(a.data.get("room_a"))
                rb = RoomId(a.data.get("room_b"))
                score = _room_remaining(state, ra) + _room_remaining(state, rb)
                if score > best_score:
                    best_score = score
                    best = a
            if best:
                return best

    armory_blocked = armory_streak >= ARMORY_STREAK_LIMIT or avoid_armory

    # Armeria: tomar si hay espacio
    take = _pick_first(acts, ActionType.USE_ARMORY_TAKE)
    if take and not armory_blocked and not key_progress_only and not risk_averse:
        key_slots, obj_slots = get_inventory_limits(p)
        if get_object_count(p) < obj_slots or get_key_count(p) < key_slots:
            return take

    # Armeria: dejar objeto si esta al limite
    drop_actions = [a for a in acts if a.type == ActionType.USE_ARMORY_DROP]
    if (
        drop_actions
        and not armory_blocked
        and not key_progress_only
        and not risk_averse
    ):
        _, obj_slots = get_inventory_limits(p)
        if get_object_count(p) >= obj_slots:
            for a in drop_actions:
                if a.data.get("item_type") == "object":
                    item = a.data.get("item_name", "")
                    if not str(item).startswith("TREASURE") and not is_soulbound(item):
                        return a
            # fallback: cualquier drop de objeto
            for a in drop_actions:
                if a.data.get("item_type") == "object":
                    return a

    # Puertas Amarillo: si falta poco para ganar, teletransportar al umbral
    if _keys_total(state) >= cfg.KEYS_TO_WIN and RoomId(cfg.UMBRAL_NODE) != p.room:
        doors_actions = [a for a in acts if a.type == ActionType.USE_YELLOW_DOORS]
        if doors_actions:
            umbral = RoomId(cfg.UMBRAL_NODE)
            for a in doors_actions:
                target = PlayerId(a.data.get("target_player"))
                if target in state.players and state.players[target].room == umbral:
                    return a
            return doors_actions[0]

    # Cámara Letal: intentar ritual si faltan llaves y cordura suficiente
    if _keys_total(state) < cfg.KEYS_TO_WIN and p.sanity >= 3 and not risk_averse:
        a = _pick_first(acts, ActionType.USE_CAMARA_LETAL_RITUAL)
        if a:
            return a

    # Capilla: curar si cordura baja
    if not key_progress_only and p.sanity <= 1:
        a = _pick_first(acts, ActionType.USE_CAPILLA)
        if a:
            return a

    # Salón de belleza: protección solo si no hay Capilla disponible
    if not key_progress_only and not avoid_salon and p.sanity <= 1:
        if not _pick_first(acts, ActionType.USE_CAPILLA):
            a = _pick_first(acts, ActionType.USE_SALON_BELLEZA)
            if a:
                return a

    # Healer: curar aliados muy bajos
    a = _pick_first(acts, ActionType.USE_HEALER_HEAL)
    if a:
        for other_pid, other in state.players.items():
            if other_pid != pid and other.sanity <= 0:
                return a

    # Libro + Cuentos
    a = _pick_first(acts, ActionType.USE_ATTACH_TALE)
    if a:
        return a

    return None


def _danger_score(state: GameState, pid: PlayerId) -> int:
    p = state.players[pid]
    score = 0
    if any(m.room == p.room for m in state.monsters):
        score += 2
    near = set(neighbors(p.room))
    if any(m.room in near for m in state.monsters):
        score += 1
    pfloor = floor_of(p.room)
    if pfloor == state.king_floor:
        score += 1
    if state.false_king_floor is not None and pfloor == state.false_king_floor:
        score += 1
    return score


def _danger_score_room(state: GameState, room: RoomId) -> int:
    score = 0
    if any(m.room == room for m in state.monsters):
        score += 2
    near = set(neighbors(room))
    if any(m.room in near for m in state.monsters):
        score += 1
    pfloor = floor_of(room)
    if pfloor == state.king_floor:
        score += 1
    if state.false_king_floor is not None and pfloor == state.false_king_floor:
        score += 1
    return score


def _team_fragility(state: GameState) -> Tuple[int, int]:
    low = sum(1 for p in state.players.values() if p.sanity <= -3)
    critical = sum(1 for p in state.players.values() if p.sanity <= -4)
    return low, critical


_DEBUFF_WEIGHTS = {
    "TRAPPED": 3.0,
    "TRAPPED_SPIDER": 3.0,
    "MALDITO": 2.0,
    "CURSE": 2.0,
    "BLEED": 2.0,
    "SANGRADO": 2.0,
    "ENVENENADO": 2.0,
    "PARANOIA": 1.5,
    "STUN": 1.0,
    "VANIDAD": 1.0,
}


def _debuff_score_player(p) -> float:
    score = 0.0
    for st in getattr(p, "statuses", []):
        weight = _DEBUFF_WEIGHTS.get(getattr(st, "status_id", ""), 0.0)
        stacks = getattr(st, "stacks", 1) or 1
        score += weight * stacks
    return score


def _team_debuff_max(state: GameState) -> float:
    if not state.players:
        return 0.0
    return max(_debuff_score_player(p) for p in state.players.values())


def _min_sanity_player(state: GameState) -> Tuple[PlayerId, int]:
    min_pid = None
    min_sanity = 999
    for pid, p in state.players.items():
        if p.sanity < min_sanity:
            min_sanity = p.sanity
            min_pid = pid
    return min_pid, min_sanity


def _king_exposure(state: GameState) -> float:
    if not state.players:
        return 0.0
    total = len(state.players)
    on_floor = sum(
        1 for p in state.players.values() if floor_of(p.room) == state.king_floor
    )
    return on_floor / total


def _king_risk(state: GameState, min_sanity: int) -> float:
    exposure = _king_exposure(state)
    multiplier = 1 + max(0, -2 - int(min_sanity))
    return exposure * multiplier


@dataclass
class GoalDirectedPlayerPolicy(PlayerPolicy):
    """
    Anti-stall policy:
    - MEDITATE solo si estás en riesgo real (<= -2) o si no hay progreso posible.
    - SEARCH solo si el mazo del nodo actual tiene cartas restantes.
    - Exploración GLOBAL: BFS al room con más cartas restantes.
    - Con llaves suficientes: BFS al Umbral y luego END_TURN (no seguir explorando).
    """

    cfg: Config = Config()
    # Umbral base de “meditar por seguridad” (más estricto que <=1)
    meditate_critical: int = -2
    # Diferencia mínima de cartas para cambiar a otro piso
    move_for_better_delta: int = 2
    # Mínimo de cartas locales para preferir SEARCH
    search_local_min_remaining: int = 1
    # Margen de uso de VIAL vs umbral de meditar
    vial_margin: int = 1
    # Endgame: forzar umbral agresivamente
    endgame_force_umbral: bool = True
    # Huir del piso del Rey si sanidad <= este valor
    king_flee_sanity: int = 2
    # Ronda a partir de la cual el Rey hace daño severo (4/ronda)
    king_flee_round_threshold: int = 9
    # Bonus adicional al umbral de meditar en late game
    late_game_meditate_bonus: int = 2
    # No buscar si cordura por debajo de este valor
    search_sanity_min: int = -1

    def __post_init__(self) -> None:
        params = _load_policy_params()
        if not isinstance(params, dict):
            self._role_sanity_bias: Dict[str, int] = {}
            self._team_memory = None
            self._bot_memories = None
            return
        self.meditate_critical = int(
            params.get("meditate_critical", self.meditate_critical)
        )
        self.move_for_better_delta = int(
            params.get("move_for_better_delta", self.move_for_better_delta)
        )
        self.search_local_min_remaining = int(
            params.get("search_local_min_remaining", self.search_local_min_remaining)
        )
        self.vial_margin = int(params.get("vial_margin", self.vial_margin))
        self.endgame_force_umbral = bool(
            params.get("endgame_force_umbral", self.endgame_force_umbral)
        )
        self.king_flee_sanity = int(
            params.get("king_flee_sanity", self.king_flee_sanity)
        )
        self.king_flee_round_threshold = int(
            params.get("king_flee_round_threshold", self.king_flee_round_threshold)
        )
        self.late_game_meditate_bonus = int(
            params.get("late_game_meditate_bonus", self.late_game_meditate_bonus)
        )
        self.search_sanity_min = int(
            params.get("search_sanity_min", self.search_sanity_min)
        )
        self._role_sanity_bias = dict(params.get("role_sanity_bias", {}))
        # Sistema de memoria (se configura desde runner.py)
        self._team_memory = None
        self._bot_memories = None

    def set_memory(self, team_memory, bot_memories) -> None:
        """Configura el sistema de memoria para la policy."""
        self._team_memory = team_memory
        self._bot_memories = bot_memories

    def _get_known_key_rooms(self) -> list:
        """Retorna habitaciones donde se sabe que hay llaves."""
        if self._team_memory is None:
            return []
        return self._team_memory.get_key_rooms()

    def _get_threat_rooms(self) -> list:
        """Retorna habitaciones con amenazas conocidas."""
        if self._team_memory is None:
            return []
        return self._team_memory.get_threat_rooms()

    def _role_bias(self, role_id: Optional[str]) -> int:
        """Retorna el bias de umbral de meditación por rol (positivo = más conservador)."""
        if not role_id or not self._role_sanity_bias:
            return 0
        return int((self._role_sanity_bias or {}).get(str(role_id), 0))

    def _preferred_floor(self, pid: PlayerId, state: GameState) -> int:
        """Asigna un piso preferido a cada jugador para evitar clustering."""
        sorted_pids = sorted(str(p) for p in state.players.keys())
        idx = sorted_pids.index(str(pid)) if str(pid) in sorted_pids else 0
        floors = [1, 2, 3, 2]  # P1→F1, P2→F2(Umbral), P3→F3, P4→F2
        return floors[idx % 4]

    def _best_room_for_player(
        self, state: GameState, pid: PlayerId, need_keys: bool = False
    ) -> Optional[RoomId]:
        """Mejor habitación para explorar.

        Por defecto prioriza el piso asignado al jugador (división de trabajo),
        pero si faltan llaves para ganar (need_keys) y el piso asignado no tiene
        cartas restantes, considera TODOS los pisos (cross-floor) para obligar al
        bot a usar las escaleras en vez de quedarse atrapado en su piso.
        """
        preferred = self._preferred_floor(pid, state)
        best_preferred: Optional[Tuple[int, str, RoomId]] = None
        best_global: Optional[Tuple[int, str, RoomId]] = None
        for rid, room in state.rooms.items():
            s = str(rid)
            if s.endswith("_P"):
                continue
            rem = room.deck.remaining()
            if rem <= 0:
                continue
            cand = (rem, s, rid)
            if floor_of(rid) == preferred:
                if best_preferred is None or cand > best_preferred:
                    best_preferred = cand
            if best_global is None or cand > best_global:
                best_global = cand
        # Si falta llegar a KEYS_TO_WIN y el piso asignado está agotado,
        # soltar la restricción de piso y permitir cruzar a otro piso.
        if need_keys and best_preferred is None and best_global is not None:
            return best_global[2]
        # Prefer assigned floor if it has cards, else fallback global
        if best_preferred is not None:
            return best_preferred[2]
        return best_global[2] if best_global else None

    def choose(self, state: GameState, rng: RNG) -> Action:
        actor = _get_active_actor(state)
        if actor not in ("KING",):
            pid = PlayerId(actor)
            p = state.players[pid]
        else:
            return Action(actor=actor, type=ActionType.END_TURN, data={})

        acts = get_legal_actions(state, actor)
        if not acts:
            return Action(actor=actor, type=ActionType.END_TURN, data={})

        def finalize(a: Action) -> Action:
            _policy_record_action(state, pid, a)
            return a

        keys_total = _keys_total(state)
        umbral = RoomId(self.cfg.UMBRAL_NODE)
        need_keys = keys_total < self.cfg.KEYS_TO_WIN

        stall_steps = _policy_update_stall(state, keys_total)
        armory_streak = _policy_armory_streak(state, pid)
        avoid_armory = stall_steps >= STALL_KEY_STEPS

        forced = _choose_forced_action(
            acts, state, pid, rng, self.cfg, team_memory=self._team_memory
        )
        if forced is not None:
            return finalize(forced)

        danger = _danger_score(state, pid)
        role_bias = self._role_bias(getattr(p, "role_id", None))
        late_game = state.round > self.king_flee_round_threshold
        on_king_floor = floor_of(p.room) == state.king_floor
        meditate_threshold = self.meditate_critical + role_bias
        key_carrier = p.keys > 0
        team_low, team_critical = _team_fragility(state)
        if danger > 0:
            meditate_threshold += 1
        if danger >= 2:
            meditate_threshold += 1
        if team_critical >= 1:
            meditate_threshold += 1
        if key_carrier:
            meditate_threshold += 1

        # === FACTORES DE RIESGO ===

        # Factor: Piso del Rey -> más riesgo si estás en su piso
        if on_king_floor:
            meditate_threshold += 2  # Muy crítico en piso del Rey siempre

        # Factor: Late game - el Rey hace 4 daño/ronda, ser muy conservador
        if late_game:
            meditate_threshold += self.late_game_meditate_bonus

        # Factor: TALE en mano -> proteger valor similar a llaves
        has_tale = any("TALE" in obj for obj in p.objects)
        if has_tale:
            meditate_threshold += 1

        # Factor: Capacidad de sacrificio restante -> si no puede sacrificar, meditar más urgente
        can_sacrifice = p.object_slots_penalty < 2 and (p.sanity_max or 5) > -3
        if not can_sacrifice and p.sanity <= 0:
            meditate_threshold += 2  # Sin sacrificio disponible, urgente meditar

        meditate_threshold = min(
            meditate_threshold, 1
        )  # Cap: meditar si sanity <= 1 en peor caso

        carrier_caution = key_carrier and (danger > 0 or team_critical > 0)

        # 0) Reacción inmediata: BLUNT si hay monstruo en la sala
        if any(m.room == p.room for m in state.monsters):
            a = _pick_first(acts, ActionType.USE_BLUNT)
            if a:
                return finalize(a)

        # 0.5) Objetos gratuitos (priorizar evitar MEDITATE)
        vial = _pick_use_object(acts, "VIAL")
        if vial:
            sanity_max = p.sanity_max or p.sanity
            if p.sanity < sanity_max and (
                p.sanity <= meditate_threshold + self.vial_margin or danger > 0
            ):
                return finalize(vial)

        compass = _pick_use_object(acts, "COMPASS")
        if compass and not is_corridor(p.room) and danger > 0:
            return finalize(compass)

        # Si ya hay escalera temporal activa en esta sala, usarla para cambiar piso
        if _temp_stairs_active_for_pid(state, p.room, pid):
            move_actions = [a for a in acts if a.type == ActionType.MOVE]
            if move_actions:
                # Preferir mover hacia el piso objetivo (Umbral o mejor room global)
                target_floor = (
                    floor_of(umbral) if keys_total >= self.cfg.KEYS_TO_WIN else None
                )
                if target_floor is None:
                    goal = _best_room_global(state)
                    if goal is not None:
                        target_floor = floor_of(goal)
                if target_floor is not None and target_floor != floor_of(p.room):
                    best = None
                    best_delta = 999
                    for a in move_actions:
                        to = RoomId(a.data.get("to"))
                        if to in state.rooms:
                            delta = abs(target_floor - floor_of(to))
                            if delta < best_delta:
                                best_delta = delta
                                best = a
                    if best:
                        return finalize(best)

        # 0.7) Huir del piso del Rey cuando el daño es severo o la cordura está baja
        if on_king_floor and p.sanity <= self.king_flee_sanity:
            move_acts = [a for a in acts if a.type == ActionType.MOVE]
            if move_acts:
                # 1. Salida directa a otro piso
                exits = [
                    a
                    for a in move_acts
                    if floor_of(RoomId(a.data.get("to"))) != state.king_floor
                ]
                if exits:
                    safest = min(
                        exits,
                        key=lambda a: _danger_score_room(
                            state, RoomId(a.data.get("to"))
                        ),
                    )
                    return finalize(safest)
                # 2. Si no hay salida directa, moverse hacia un corredor para escapar luego
                corridor_moves = [
                    a for a in move_acts if is_corridor(RoomId(a.data.get("to")))
                ]
                if corridor_moves:
                    return finalize(rng.choice(corridor_moves))
                # 3. Sino, a la habitación menos peligrosa
                safest_room = min(
                    move_acts,
                    key=lambda a: _danger_score_room(state, RoomId(a.data.get("to"))),
                )
                return finalize(safest_room)

        # 1) Panico extremo: meditar si existe
        if p.sanity <= self.cfg.PLAYER_SANITY_PANIC:
            a = _pick_first(acts, ActionType.MEDITATE)
            if a:
                return finalize(a)

        # 2) Supervivencia inmediata si hay peligro alto
        if danger > 0 and p.sanity <= meditate_threshold:
            a = _pick_first(acts, ActionType.MEDITATE)
            if a:
                return finalize(a)

        # 2.8) Endgame: con llaves suficientes, priorizar umbral agresivamente
        if (
            self.endgame_force_umbral
            and keys_total >= self.cfg.KEYS_TO_WIN
            and p.room != umbral
        ):
            doors_actions = [a for a in acts if a.type == ActionType.USE_YELLOW_DOORS]
            if doors_actions:
                for a in doors_actions:
                    target = PlayerId(a.data.get("target_player"))
                    if target in state.players and state.players[target].room == umbral:
                        return finalize(a)
                return finalize(doors_actions[0])

            stairs = _pick_use_object(acts, "TREASURE_STAIRS")
            if stairs and not _temp_stairs_active_for_pid(state, p.room, pid):
                dest = _temp_stairs_dest(state, p.room, floor_of(umbral))
                if dest is not None:
                    return finalize(stairs)

            nxt = bfs_next_step(state, p.room, umbral)
            if nxt is not None:
                for a in acts:
                    if a.type == ActionType.MOVE and a.data.get("to") == str(nxt):
                        return finalize(a)

            # Si no hay camino claro, moverse aleatoriamente (pero no SEARCH)
            move_actions = [a for a in acts if a.type == ActionType.MOVE]
            if move_actions:
                return finalize(rng.choice(move_actions))

            # En endgame, NUNCA buscar a menos que sea una llave segura, es mejor terminar turno
            return finalize(Action(actor=actor, type=ActionType.END_TURN, data={}))

        # 2.5) Guardrail para portadores de llaves en riesgo: curar o escapar primero
        if carrier_caution:
            safe_special = _choose_special_action(
                acts,
                state,
                pid,
                rng,
                self.cfg,
                avoid_armory=True,
                armory_streak=armory_streak,
                avoid_salon=False,
                key_progress_only=False,
                risk_averse=True,
            )
            if safe_special:
                return finalize(safe_special)

            move_actions = [a for a in acts if a.type == ActionType.MOVE]
            if move_actions:
                best = min(
                    move_actions,
                    key=lambda a: _danger_score_room(state, RoomId(a.data.get("to"))),
                )
                if _danger_score_room(state, RoomId(best.data.get("to"))) < danger:
                    return finalize(best)

        # 2.9) MEMORIA DE EQUIPO: Priorizar habitaciones con llaves conocidas
        known_key_rooms = self._get_known_key_rooms()
        known_threat_rooms = set(self._get_threat_rooms())
        if known_key_rooms and need_keys and p.sanity > meditate_threshold:
            prioritized_key_rooms = [
                room for room in known_key_rooms if room not in known_threat_rooms
            ]
            if not prioritized_key_rooms:
                prioritized_key_rooms = known_key_rooms

            for key_room_str in prioritized_key_rooms:
                key_room = RoomId(key_room_str)
                # Si ya estoy en la habitación con llave conocida, hacer SEARCH
                if p.room == key_room:
                    a = _pick_first(acts, ActionType.SEARCH)
                    if a:
                        return finalize(a)
                # Si puedo moverme hacia la habitación con llave
                nxt = bfs_next_step(state, p.room, key_room)
                if nxt is not None:
                    if (
                        str(nxt) in known_threat_rooms
                        and len(prioritized_key_rooms) > 1
                    ):
                        continue
                    for a in acts:
                        if a.type == ActionType.MOVE and a.data.get("to") == str(nxt):
                            return finalize(a)

        # 3) Progreso de llaves: specials de progreso primero
        if need_keys and p.sanity > meditate_threshold and not carrier_caution:
            key_special = _choose_special_action(
                acts,
                state,
                pid,
                rng,
                self.cfg,
                avoid_armory=avoid_armory,
                armory_streak=armory_streak,
                avoid_salon=True,
                key_progress_only=True,
                risk_averse=False,
            )
            if key_special:
                return finalize(key_special)

            goal = self._best_room_for_player(state, pid, need_keys=need_keys)
            current_rem = _room_remaining(state, p.room)
            same_floor_goal = goal is not None and floor_of(goal) == floor_of(p.room)
            search_allowed = (
                current_rem >= self.search_local_min_remaining
            ) or same_floor_goal

            if goal is not None and floor_of(goal) != floor_of(p.room):
                if not search_allowed:
                    stairs = _pick_use_object(acts, "TREASURE_STAIRS")
                    if stairs and not _temp_stairs_active_for_pid(state, p.room, pid):
                        dest = _temp_stairs_dest(state, p.room, floor_of(goal))
                        if dest is not None:
                            return finalize(stairs)
                    nxt = bfs_next_step(state, p.room, goal)
                    if nxt is not None:
                        for a in acts:
                            if a.type == ActionType.MOVE and a.data.get("to") == str(
                                nxt
                            ):
                                return finalize(a)
                    corridor_move = _pick_move_to_corridor(acts, floor_of(p.room))
                    if corridor_move:
                        return finalize(corridor_move)
                else:
                    goal_rem = _room_remaining(state, goal)
                    move_for_better = goal_rem > 0 and (
                        current_rem == 0
                        or goal_rem >= current_rem + self.move_for_better_delta
                    )
                    if move_for_better:
                        stairs = _pick_use_object(acts, "TREASURE_STAIRS")
                        if stairs and not _temp_stairs_active_for_pid(
                            state, p.room, pid
                        ):
                            dest = _temp_stairs_dest(state, p.room, floor_of(goal))
                            if dest is not None:
                                return finalize(stairs)
                        nxt = bfs_next_step(state, p.room, goal)
                        if nxt is not None:
                            for a in acts:
                                if a.type == ActionType.MOVE and a.data.get(
                                    "to"
                                ) == str(nxt):
                                    return finalize(a)

            if (
                search_allowed
                and _room_remaining(state, p.room) > 0
                and (danger == 0 or p.sanity > meditate_threshold)
                and p.sanity >= self.search_sanity_min
            ):
                a = _pick_first(acts, ActionType.SEARCH)
                if a:
                    return finalize(a)

        # 4) Especiales generales (evitar salon cuando estamos en progreso)
        avoid_salon = need_keys and p.sanity > meditate_threshold
        risk_averse = carrier_caution or team_critical >= 1
        if keys_total < self.cfg.KEYS_TO_WIN:
            special = _choose_special_action(
                acts,
                state,
                pid,
                rng,
                self.cfg,
                avoid_armory=avoid_armory,
                armory_streak=armory_streak,
                avoid_salon=avoid_salon,
                key_progress_only=False,
                risk_averse=risk_averse,
            )
            if special:
                return finalize(special)

        # 5) Si ya hay llaves suficientes: converger a Umbral
        if keys_total >= self.cfg.KEYS_TO_WIN:
            if p.room == umbral:
                if p.sanity <= meditate_threshold:
                    a = _pick_first(acts, ActionType.MEDITATE)
                    if a:
                        return finalize(a)
                return finalize(Action(actor=actor, type=ActionType.END_TURN, data={}))

            if danger > 0 and p.sanity <= meditate_threshold:
                a = _pick_first(acts, ActionType.MEDITATE)
                if a:
                    return finalize(a)

            stairs = _pick_use_object(acts, "TREASURE_STAIRS")
            if stairs and not _temp_stairs_active_for_pid(state, p.room, pid):
                dest = _temp_stairs_dest(state, p.room, floor_of(umbral))
                if dest is not None:
                    return finalize(stairs)

            nxt = bfs_next_step(state, p.room, umbral)
            if nxt is not None:
                for a in acts:
                    if a.type == ActionType.MOVE and a.data.get("to") == str(nxt):
                        return finalize(a)

            move_actions = [a for a in acts if a.type == ActionType.MOVE]
            return (
                finalize(rng.choice(move_actions))
                if move_actions
                else finalize(Action(actor=actor, type=ActionType.END_TURN, data={}))
            )

        # 6) Falta llaves: SEARCH si hay cartas y no esta estancado por riesgo
        if (
            need_keys
            and _room_remaining(state, p.room) > 0
            and (danger == 0 or p.sanity > meditate_threshold)
            and not carrier_caution
        ):
            goal = _best_room_global(state)
            current_rem = _room_remaining(state, p.room)
            same_floor_goal = goal is not None and floor_of(goal) == floor_of(p.room)
            search_allowed = (
                current_rem >= self.search_local_min_remaining
            ) or same_floor_goal

            if goal is not None and floor_of(goal) != floor_of(p.room):
                if not search_allowed:
                    a = _pick_use_object(acts, "TREASURE_STAIRS")
                    if a and not _temp_stairs_active_for_pid(state, p.room, pid):
                        dest = _temp_stairs_dest(state, p.room, floor_of(goal))
                        if dest is not None:
                            return finalize(a)
                    nxt = bfs_next_step(state, p.room, goal)
                    if nxt is not None:
                        for a in acts:
                            if a.type == ActionType.MOVE and a.data.get("to") == str(
                                nxt
                            ):
                                return finalize(a)
                    corridor_move = _pick_move_to_corridor(acts, floor_of(p.room))
                    if corridor_move:
                        return finalize(corridor_move)
                else:
                    goal_rem = _room_remaining(state, goal)
                    move_for_better = goal_rem > 0 and (
                        current_rem == 0
                        or goal_rem >= current_rem + self.move_for_better_delta
                    )
                    if move_for_better:
                        a = _pick_use_object(acts, "TREASURE_STAIRS")
                        if a and not _temp_stairs_active_for_pid(state, p.room, pid):
                            dest = _temp_stairs_dest(state, p.room, floor_of(goal))
                            if dest is not None:
                                return finalize(a)
                        nxt = bfs_next_step(state, p.room, goal)
                        if nxt is not None:
                            for a in acts:
                                if a.type == ActionType.MOVE and a.data.get(
                                    "to"
                                ) == str(nxt):
                                    return finalize(a)

            if search_allowed and _room_remaining(state, p.room) > 0:
                a = _pick_first(acts, ActionType.SEARCH)
                if a:
                    return finalize(a)

        # 7) Si estas critico o en peligro, meditar
        if p.sanity <= meditate_threshold:
            a = _pick_first(acts, ActionType.MEDITATE)
            if a:
                return finalize(a)

        # 8) Exploracion GLOBAL: ir al room con mas cartas restantes
        goal = _best_room_global(state)
        if goal is not None and p.room != goal:
            stairs = _pick_use_object(acts, "TREASURE_STAIRS")
            if stairs and not _temp_stairs_active_for_pid(state, p.room, pid):
                dest = _temp_stairs_dest(state, p.room, floor_of(goal))
                if dest is not None:
                    return finalize(stairs)

            nxt = bfs_next_step(state, p.room, goal)
            if nxt is not None:
                for a in acts:
                    if a.type == ActionType.MOVE and a.data.get("to") == str(nxt):
                        return finalize(a)

        # 9) Si no hay rooms con cartas restantes, meditar si ayuda, si no END_TURN
        a = _pick_first(acts, ActionType.MEDITATE)
        if a and p.sanity < (p.sanity_max or p.sanity):
            return finalize(a)

        move_actions = [a for a in acts if a.type == ActionType.MOVE]
        if move_actions:
            return finalize(rng.choice(move_actions))
        elif acts:
            return finalize(rng.choice(acts))

        return finalize(Action(actor=actor, type=ActionType.END_TURN, data={}))


@dataclass
class HabitanteDeCarcosaPolicy(GoalDirectedPlayerPolicy):
    """
    PolÃ­tica humana base: menos meditaciÃ³n, mÃ¡s movimiento y exploraciÃ³n,
    pero con foco en ganar y sin tests artificiales.
    """

    cfg: Config = Config()
    meditate_critical: int = -4
    move_for_better_delta: int = 1
    search_local_min_remaining: int = 0
    vial_margin: int = 2
    endgame_force_umbral: bool = True

    def __post_init__(self) -> None:
        # Mantener parámetros fijos (no cargar policy_params.json).
        # Pero sí debemos inicializar los atributos privados que usa choose(),
        # igual que la clase padre, para no romper en runtime.
        self._role_sanity_bias = {}
        self._team_memory = None
        self._bot_memories = None


@dataclass
class HeuristicKingPolicy(KingPolicy):
    cfg: Config = Config()

    def choose(self, state: GameState, rng: RNG) -> Action:
        acts = get_legal_actions(state, "KING")
        if not acts:
            # Should not happen in canonical simulation
            return None

        # Gate: permitir WIN cuando sea alcanzable desde cierto umbral,
        # o cuando se acumulan "win_ready_hits".
        umbral = RoomId(self.cfg.UMBRAL_NODE)
        total_keys = _keys_total(state)
        all_umbral = all(
            (pl.at_umbral or pl.room == umbral) for pl in state.players.values()
        )
        ready_now = (total_keys >= self.cfg.KEYS_TO_WIN) and all_umbral

        hits = int(state.flags.get("win_ready_hits", 0)) if state.flags else 0
        if ready_now:
            hits += 1
            state.flags["win_ready_hits"] = hits

        allow_win = (state.round >= self.cfg.KING_ALLOW_WIN_START_ROUND) or (
            hits >= self.cfg.KING_ALLOW_WIN_AFTER_READY_HITS
        )

        if allow_win:
            win_candidates = []
            for a in acts:
                s2 = step(state, a, rng.fork(f"king_eval_win:{a.data}"), self.cfg)
                if s2.game_over and s2.outcome == "WIN":
                    win_candidates.append(a)
            if win_candidates:
                return win_candidates[0]

        best = None
        best_u = -1e18

        for a in acts:
            s2 = step(state, a, rng.fork(f"king_eval:{a.data}"), self.cfg)
            u = king_utility(s2, self.cfg)

            if s2.game_over and s2.outcome == "LOSE":
                continue

            min_sanity = (
                min(p.sanity for p in s2.players.values()) if s2.players else 999
            )
            if min_sanity <= self.cfg.S_LOSS:
                if state.round < self.cfg.KING_KILL_AVOID_START_ROUND:
                    continue
                fade = max(1, self.cfg.KING_KILL_AVOID_FADE_ROUNDS)
                t = (state.round - self.cfg.KING_KILL_AVOID_START_ROUND) / fade
                alpha = max(0.0, min(1.0, t))
                u -= (1.0 - alpha) * self.cfg.KING_KILL_AVOID_PENALTY

            if u > best_u:
                best_u = u
                best = a

        # Fallback to random choice if no 'best' found (e.g. all lose)
        return best if best is not None else rng.choice(acts)


@dataclass
class RandomKingPolicy(KingPolicy):
    cfg: Config = Config()

    def choose(self, state: GameState, rng: RNG) -> Action:
        acts = get_legal_actions(state, "KING")
        if not acts:
            return None
        d4 = rng.randint(1, 4)
        d6 = rng.randint(1, 6)
        return Action(
            actor="KING", type=ActionType.KING_ENDROUND, data={"d4": d4, "d6": d6}
        )


@dataclass
class CowardPolicy(PlayerPolicy):
    """
    Política Miedosa ("The Coward"):
    - Medita agresivamente si Sanity < Max.
    - Evita habitaciones con monstruos.
    - Nunca se sacrifica.
    """

    cfg: Config = Config()

    def choose(self, state: GameState, rng: RNG) -> Action:
        actor = _get_active_actor(state)
        if actor not in ("KING",):
            pid = PlayerId(actor)
            p = state.players[pid]
        else:
            return Action(actor=actor, type=ActionType.END_TURN, data={})

        acts = get_legal_actions(state, actor)
        if not acts:
            return Action(actor=actor, type=ActionType.END_TURN, data={})

        forced = _choose_forced_action(acts, state, pid, rng, self.cfg)
        if forced is not None:
            return forced

        # 1. Self-Preservation: Meditate if ANY damage taken
        if p.sanity < (p.sanity_max or 5):
            a = _pick_first(acts, ActionType.MEDITATE)
            if a:
                return a

        # 2. Avoid Sacrificing (Accept if forced, but prefer Accept over Sacrifice??)
        # Actually logic says if pending sacrifice check, only valid actions are SACRIFICE or ACCEPT_SACRIFICE.
        # Coward chooses ACCEPT_SACRIFICE (live with consequences) rather than resetting to 0 sanity?
        # A4: Sacrifice resets to 0. Accept means you live (with consequences? wait)
        # Wait, A4 says Sacrifice sets sanity=0 and max-=1. Accept applies minus5 consequences (loss of items + ?)
        # Usually Sacrifice is "Save the Group". Coward saves SELF.
        # If Accept leads to death, they might Sacrifice.
        # If forced choice:
        sac_acts = [
            a
            for a in acts
            if a.type in (ActionType.SACRIFICE, ActionType.ACCEPT_SACRIFICE)
        ]
        if sac_acts:
            # Prefer ACCEPT_SACRIFICE unless it kills instantly?
            # For simplicity: Coward never Sacrifices voluntarily.
            a = _pick_first(acts, ActionType.ACCEPT_SACRIFICE)
            if a:
                return a
            return acts[0]

        # 3. Heuristica humana: usar especiales si aplica
        special = _choose_special_action(acts, state, pid, rng, self.cfg)
        if special:
            return special

        # 4. Safe Exploration
        # Move away from King/Monsters?
        # Simple for now: Random movement but avoid King's floor
        move_acts = [a for a in acts if a.type == ActionType.MOVE]
        safe_moves = []
        for a in move_acts:
            target_room = RoomId(a.data["to"])
            if floor_of(target_room) != state.king_floor:
                safe_moves.append(a)

        if safe_moves:
            return rng.choice(safe_moves)
        elif move_acts:
            return rng.choice(move_acts)

        return rng.choice(acts)


@dataclass
class BerserkerPolicy(PlayerPolicy):
    """
    Política Agresiva ("The Berserker"):
    - Nunca medita voluntariamente.
    - Siempre SEARCH si hay cartas.
    - Siempre SACRIFICE si está disponible.
    - Busca monstruos o items.
    """

    cfg: Config = Config()

    def choose(self, state: GameState, rng: RNG) -> Action:
        actor = _get_active_actor(state)
        acts = get_legal_actions(state, actor)
        if not acts:
            return Action(actor=actor, type=ActionType.END_TURN, data={})

        if actor in state.players:
            forced = _choose_forced_action(acts, state, PlayerId(actor), rng, self.cfg)
            if forced is not None:
                return forced

        # 1. ALWAYS SACRIFICE (Heroic/Crazy)
        a = _pick_first(acts, ActionType.SACRIFICE)
        if a:
            return a

        # 2. SEARCH Priority
        a = _pick_first(acts, ActionType.SEARCH)
        if a:
            return a

        # 3. Special Rooms (Motemey, Armory, etc)
        special_acts = [a for a in acts if "USE_" in a.type.value]
        if special_acts:
            return rng.choice(special_acts)

        # 4. Aggressive Movement (Random for now, ortowards unexplored)
        return rng.choice(acts)


@dataclass
class SpeedrunnerPolicy(PlayerPolicy):
    """
    Política Speedrunner:
    - Optimiza ruta a llaves y luego a Umbral.
    - Ignora todo lo demás (monstruos, loot extra, meditar).
    - Solo medita si es CRÍTICO para no morir antes de llegar.
    """

    cfg: Config = Config()

    def choose(self, state: GameState, rng: RNG) -> Action:
        actor = _get_active_actor(state)
        # Verify valid player actor
        if actor not in state.players:
            return Action(actor=actor, type=ActionType.END_TURN, data={})

        pid = PlayerId(actor)
        p = state.players[pid]
        acts = get_legal_actions(state, actor)
        if not acts:
            return Action(actor=actor, type=ActionType.END_TURN, data={})

        forced = _choose_forced_action(acts, state, pid, rng, self.cfg)
        if forced is not None:
            return forced

        keys_total = _keys_total(state)
        umbral = RoomId(self.cfg.UMBRAL_NODE)

        # 1. Emergency Meditate (Don't die on split)
        if p.sanity <= -2:
            a = _pick_first(acts, ActionType.MEDITATE)
            if a:
                return a

        # 2. Win condition
        if keys_total >= self.cfg.KEYS_TO_WIN:
            if p.room == umbral:
                return Action(actor=actor, type=ActionType.END_TURN, data={})
            nxt = bfs_next_step(state, p.room, umbral)
            if nxt:
                for a in acts:
                    if a.type == ActionType.MOVE and a.data.get("to") == str(nxt):
                        return a

        # 3. Hunt Keys (Best Room Global)
        goal = _best_room_global(state)
        if goal and p.room != goal:
            nxt = bfs_next_step(state, p.room, goal)
            if nxt:
                for a in acts:
                    if a.type == ActionType.MOVE and a.data.get("to") == str(nxt):
                        return a
        elif _room_remaining(state, p.room) > 0:
            a = _pick_first(acts, ActionType.SEARCH)
            if a:
                return a

        return rng.choice(acts)


@dataclass
class RandomPolicy(PlayerPolicy):
    """
    Política Aleatoria (Baseline):
    - Elige cualquier acción legal con probabilidad uniforme.
    """

    cfg: Config = Config()

    def choose(self, state: GameState, rng: RNG) -> Action:
        actor = _get_active_actor(state)
        acts = get_legal_actions(state, actor)
        if not acts:
            return Action(actor=actor, type=ActionType.END_TURN, data={})
        return rng.choice(acts)


class BCNNPlayerPolicy(PlayerPolicy):
    """
    Behavioral Cloning Neural Network policy.
    Loads a pre-trained CarcosaPolicyNet checkpoint and its companion
    action_mapping.json, then selects actions by masking illegal types
    and returning the legal action whose type has the highest logit.

    The companion mapping file is looked up as:
        <checkpoint_stem>.action_mapping.json
    in the same directory as the .pt file.
    """

    def __init__(self, cfg: Config = None):
        import json
        import torch
        import numpy as np
        from pathlib import Path as _Path
        from train.model import CarcosaPolicyNet

        self.cfg = cfg or Config()
        self._torch = torch
        self._np = np
        self._goal_fallback = GoalDirectedPlayerPolicy(self.cfg)

        # Locate checkpoint relative to repo root
        checkpoint_path = (
            _Path(__file__).parent.parent / "models_bc" / "bc_mlp_all_best.pt"
        )
        checkpoint = torch.load(str(checkpoint_path), map_location="cpu")

        obs_dim = checkpoint.get("obs_dim", 10)
        num_actions = checkpoint.get("num_actions")
        hidden_sizes = checkpoint.get("hidden_sizes") or [128, 128, 64]

        # Load the companion action mapping: action_type_string → model_index
        mapping_path = checkpoint_path.with_suffix(".action_mapping.json")
        if mapping_path.exists():
            with open(mapping_path, encoding="utf-8") as _f:
                raw_mapping = json.load(_f)
        else:
            # Hardcoded fallback consistent with all known training runs
            raw_mapping = {
                "MOVE": 0,
                "ACCEPT_SACRIFICE": 1,
                "MEDITATE": 2,
                "END_TURN": 3,
                "USE_HEALER_HEAL": 4,
            }

        # Build reverse map: model_index → ActionType (only for indices 0..num_actions-1)
        if num_actions is None:
            num_actions = max(raw_mapping.values()) + 1
        self._index_to_action_type: Dict[int, ActionType] = {}
        for type_str, idx in raw_mapping.items():
            if idx < num_actions:
                try:
                    self._index_to_action_type[idx] = ActionType(type_str)
                except ValueError:
                    pass  # Unknown action type string — skip

        self._model = CarcosaPolicyNet(obs_dim, num_actions, hidden_sizes=hidden_sizes)
        self._model.load_state_dict(checkpoint["model_state_dict"])
        self._model.eval()

    def _get_obs(self, state: GameState):
        """Replicate CarcosaEnv._get_obs() exactly."""
        import numpy as np
        from engine.tension import compute_features, tension_T

        features = compute_features(state, self.cfg)
        tension = tension_T(state, self.cfg, features=features)

        obs = np.array(
            [
                features.get("P_sanity", 0.0),
                features.get("P_keys", 0.0),
                features.get("P_mon", 0.0),
                features.get("P_umbral", 0.0),
                features.get("P_debuff", 0.0),
                features.get("P_king_risk", 0.0),
                features.get("P_crown", 0.0),
                features.get("P_round", 0.0),
                tension,
                state.king_floor / 3.0,
            ],
            dtype=np.float32,
        )

        return np.clip(obs, 0.0, 1.0)

    def _predict_type_with_confidence(self, state: GameState):
        """
        Run the BC model and return (best_legal_type, softmax_confidence).
        best_legal_type is None if no legal action type is in the mapping.
        confidence is the softmax probability of the predicted class.
        """
        import torch

        actor = _get_active_actor(state)
        acts = get_legal_actions(state, actor)
        if not acts:
            return None, 0.0

        obs = self._get_obs(state)
        obs_tensor = torch.tensor(obs, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            logits = self._model(obs_tensor).squeeze(0)

        legal_types = {a.type for a in acts}
        NEG_INF = float("-inf")
        best_score = NEG_INF
        best_type = None
        best_idx = None

        for idx, atype in self._index_to_action_type.items():
            if atype in legal_types:
                score = logits[idx].item()
                if score > best_score:
                    best_score = score
                    best_type = atype
                    best_idx = idx

        if best_type is None:
            return None, 0.0

        # Softmax confidence = exp(best_logit) / sum(exp(all_logits))
        softmax_probs = torch.softmax(logits, dim=0)
        confidence = softmax_probs[best_idx].item()
        return best_type, confidence

    def choose(self, state: GameState, rng: RNG) -> Action:
        import torch

        actor = _get_active_actor(state)
        acts = get_legal_actions(state, actor)
        if not acts:
            return Action(actor=actor, type=ActionType.END_TURN, data={})

        obs = self._get_obs(state)
        obs_tensor = torch.tensor(obs, dtype=torch.float32).unsqueeze(0)  # [1, 10]

        with torch.no_grad():
            logits = self._model(obs_tensor).squeeze(0)  # [num_actions]

        # Mask: keep only model indices whose ActionType has at least one legal action
        legal_types = {a.type for a in acts}
        NEG_INF = float("-inf")
        best_score = NEG_INF
        best_type = None

        for idx, atype in self._index_to_action_type.items():
            if atype in legal_types:
                score = logits[idx].item()
                if score > best_score:
                    best_score = score
                    best_type = atype

        # If the model knows no legal type, fall back to GOAL policy
        if best_type is None:
            return self._goal_fallback.choose(state, rng)

        # Return first legal action matching the best type
        for a in acts:
            if a.type == best_type:
                return a
        return self._goal_fallback.choose(state, rng)


class HybridBCNNGoalPolicy(BCNNPlayerPolicy):
    """
    Hybrid BC + GOAL policy.

    GoalDirectedPlayerPolicy is the primary decision maker.
    When the BC model predicts an action type with softmax confidence >= threshold
    AND that type is legal AND differs from GOAL's predicted type, BC overrides.

    This guarantees winrate >= GOAL baseline while letting the BC model
    improve specific high-confidence decisions.

    Default threshold: 0.60 (tunable via BC_CONFIDENCE_THRESHOLD class attribute).
    """

    BC_CONFIDENCE_THRESHOLD: float = 0.60

    def __init__(self, cfg=None):
        super().__init__(cfg)  # initialises _model, _goal_fallback, etc.

    def choose(self, state: GameState, rng: RNG) -> Action:
        actor = _get_active_actor(state)
        acts = get_legal_actions(state, actor)
        if not acts:
            return Action(actor=actor, type=ActionType.END_TURN, data={})

        # Primary: GOAL-directed action
        goal_action = self._goal_fallback.choose(state, rng)

        # Secondary: BC prediction with confidence
        bc_type, bc_conf = self._predict_type_with_confidence(state)

        # Override GOAL only when BC is confident enough and suggests a different type
        if (
            bc_conf >= self.BC_CONFIDENCE_THRESHOLD
            and bc_type is not None
            and bc_type != goal_action.type
        ):
            for a in acts:
                if a.type == bc_type:
                    return a

        return goal_action


class PPOCARCOPlayerPolicy(PlayerPolicy):
    """
    [092] Andamiaje PPO → bots del servidor (INACTIVO POR DEFECTO).

    Carga un modelo PPO de Stable-Baselines3 (.zip) entrenado por evolve*.py y
    lo expone como PlayerPolicy para el modo espectador 4-bots de game_server.

    DISEÑO SIN DRIFT:
      - No reimplementa la observación. Reusa CarcosaEnv._get_obs() clonando el
        GameState actual al env (mismo 167-dim, misma normalización).
      - No reimplementa el mapeo acción→Action. Usa CarcosaEnv.ACTION_TYPES
        (lista fija idéntica a la del entrenamiento).
      - El entorno del server (step/engine) valida legalidad y hace el masking
        real; aquí sólo devolvemos Action(actor, type) y el server corrige si
        hiciera falta (game_server._auto_advance_until_human ya tiene fallback).

    ACTIVACIÓN:
      Sólo vía game_server /start con bot_policy="PPO" y ppo_model_path=<.zip>.
      NUNCA se usa por defecto. Regla [092]: si no supera a GOAL en eval, se
      mantiene la heurística. Este policy es el conducto, no la decisión.

    NOTA: requiere stable_baselines3 + torch en el venv del server.
    """

    def __init__(self, cfg: Config = None, model_path: str = None):
        self.cfg: Config = cfg or Config()
        if not model_path:
            raise ValueError(
                "PPOCARCOPlayerPolicy requiere model_path (ruta a .zip SB3 PPO). "
                "No se activa sin un modelo explícito."
            )
        import torch
        from stable_baselines3 import PPO as _SB3PPO
        from train.carcosa_env import CarcosaEnv

        self._torch = torch
        self._model_path = model_path
        # Env dummy para reusar _get_obs y ACTION_TYPES sin entrenar.
        self._env = CarcosaEnv()
        self._is_maskable = False
        # [092] El modelo puede ser MaskablePPO (train con --action-mask true).
        # Intentar cargarlo como maskable primero; si el .zip no es maskable,
        # BaseAlgorithm.load lo levanta igual por clase. Fallback a PPO regular.
        try:
            from sb3_contrib import MaskablePPO as _SB3Masked

            self._model = _SB3Masked.load(model_path, env=self._env, device="cpu")
            self._is_maskable = True
            print(f"[PPOCARCO] modelo cargado como MaskablePPO: {model_path}")
        except Exception:
            self._model = _SB3PPO.load(model_path, env=self._env, device="cpu")
            print(f"[PPOCARCO] modelo cargado como PPO regular: {model_path}")
        self._action_types = self._env.ACTION_TYPES

    def choose(self, state: GameState, rng: RNG) -> Action:
        import numpy as np

        actor = _get_active_actor(state)

        # Fase KING: el actor activo es "KING", no el jugador del turn_order.
        # El server ya la maneja aparte (kpol), pero por robustez autónoma
        # devolvemos KING_ENDROUND (siempre legal en fase KING).
        if state.phase == "KING":
            return Action(actor="KING", type=ActionType.KING_ENDROUND, data={})

        # Clonar el estado actual al env para que _get_obs lea este tablero.
        self._env.state = state
        try:
            obs = self._env._get_obs()
        except Exception as e:
            # Si la obs falla (estado incompatible), caer a END_TURN seguro.
            print(f"[PPOCARCO] obs failed for {actor}: {e}. END_TURN fallback.")
            return Action(actor=actor, type=ActionType.END_TURN, data={})

        with self._torch.no_grad():
            # [LIVE-ACT] Forward manual para capturar activaciones en vivo.
            # Replica exactamente model.predict(deterministic=True, action_masks=masks)
            # pero expone obs / hidden / logits / probs / value.
            self.last_activations = None
            try:
                policy = self._model.policy
                obs_t = self._torch.as_tensor(obs, dtype=self._torch.float32).unsqueeze(
                    0
                )
                latent = policy.extract_features(obs_t, None)
                policy_latent = policy.mlp_extractor.policy_net(latent)
                value_latent = policy.mlp_extractor.value_net(latent)
                logits = policy.action_net(policy_latent)
                value = policy.value_net(value_latent)
                masks = None
                if self._is_maskable:
                    masks = self._env.action_masks()
                    if masks is not None:
                        m_t = self._torch.as_tensor(
                            masks, dtype=self._torch.float32
                        ).unsqueeze(0)
                        logits = self._torch.where(
                            m_t > 0, logits, self._torch.tensor(-1e10)
                        )
                probs = self._torch.softmax(logits, dim=-1)
                action_id = int(self._torch.argmax(logits, dim=-1).item())
                self.last_activations = {
                    "actor": actor,
                    "obs": [float(x) for x in obs],
                    "policy_hidden": [
                        float(x) for x in policy_latent.squeeze(0).cpu().numpy()
                    ],
                    "logits": [float(x) for x in logits.squeeze(0).cpu().numpy()],
                    "probs": [float(x) for x in probs.squeeze(0).cpu().numpy()],
                    "action_idx": action_id,
                    "value": float(value.squeeze(0).item()),
                }
            except Exception as e:
                print(f"[PPOCARCO] activations capture failed: {e}")
                # Fallback al predict estándar (sin activaciones)
                if self._is_maskable:
                    masks = self._env.action_masks()
                    action_id, _ = self._model.predict(
                        obs, deterministic=True, action_masks=masks
                    )
                else:
                    action_id, _ = self._model.predict(obs, deterministic=True)

        # model.predict devuelve np.ndarray 0-dim o 1-dim; normalizar a int.
        # (si el forward manual funcionó, action_id ya es int)
        if isinstance(action_id, (list, tuple, np.ndarray)):
            action_id = int(np.asarray(action_id).flatten()[0])
        else:
            action_id = int(action_id)

        if 0 <= action_id < len(self._action_types):
            atype = self._action_types[action_id]
        else:
            atype = ActionType.END_TURN

        # El modelo PPO sólo predice el TIPO de acción (Discrete sobre ACTION_TYPES).
        # El training resuelve data/{} via _pick_action_for_type; el server aplica la
        # accion directo al engine, asi que debemos materializar la accion CONCRETA aqui
        # (mismo metodo que usa CarcosaEnv.step), sin reimplementar nada.
        legal = get_legal_actions(state, actor)
        concrete = self._env._pick_action_for_type(legal, atype, actor)
        if concrete is not None:
            return concrete
        # Fallback de robustez: si el type predicho no es materializable en este
        # estado, devolver la PRIMERA accion legal real (nunca END_TURN ciego, que
        # el engine puede rechazar). Imita el fallback deterministico del env.
        if legal:
            return legal[0]
        return Action(actor=actor, type=ActionType.END_TURN, data={})


class EnsembleGoalNetPolicy(PlayerPolicy):
    """
    [092] Ensamble GOAL + red: GOAL es el principal, la red best_evolved cubre
    donde la heurística no progresa. INACTIVO por defecto (requiere model_path).

    MOTIVACIÓN (hallazgo 2026-08-04, benchmark 100 seeds en bench_multi_seed.py):
      - GOAL 9.0% en seeds 0-99; best_evolved 3.0% pero en seeds ORTOGONALES
        (14,58,65 — donde GOAL pierde). overlap=0. GOAL∪best = 12% > 9%.
      - La red encontró una trayectoria de victoria distinta a la heurística.
      - Este policy materializa la UNIÓN: no reemplaza a GOAL, lo extiende.

    ESTRATEGIA (integración por tipo de acción, sin reimplementar lógica):
      - En cada turno pide la acción a GOAL y a la red.
      - Prioriza acciones que significan PROGRESO sobre END_TURN: si cualquiera
        de los dos propone algo que no es END_TURN, lo toma. GOAL desempata
        cuando ambos proponen (su heuristic es la fuente de game-truth).
      - Si ambos llegan a END_TURN, usa la primera acción legal (nunca ciego).
      - La red sólo "habla" cuando GOAL estaría pasando: exactamente el caso
        donde el benchmark le vio ganar seeds que GOAL pierde.

    Activación vía get_player_policy("ENSEMBLE", cfg, model_path=<best_evolved.zip>).
    """

    def __init__(self, cfg: Config = None, model_path: str = None):
        # GOAL es el principal — se instancia sin model_path.
        self._goal = GoalDirectedPlayerPolicy(cfg or Config())
        self._net = PPOCARCOPlayerPolicy(cfg, model_path=model_path)

    def set_memory(self, team_memory, bot_memories) -> None:
        """Propaga la memoria de cartas al GOAL interno (la red no la usa)."""
        for pol in (self._goal, self._net):
            if pol is not None and hasattr(pol, "set_memory"):
                pol.set_memory(team_memory, bot_memories)

    def choose(self, state: GameState, rng: RNG) -> Action:
        goal_action = self._goal.choose(state, rng)
        # La red sólo consulta cuando GOAL pasaría — ahorra coste y evita
        # que una red no-legal pise la decisión de la heurística.
        if goal_action.type != ActionType.END_TURN:
            return goal_action

        try:
            net_action = self._net.choose(state, rng)
        except Exception as e:
            print(f"[ENSEMBLE] net fallback failed: {e}. Usando primera legal.")
            net_action = None

        if net_action is not None and net_action.type != ActionType.END_TURN:
            return net_action

        # Ambos pasan: primera acción legal real, nunca END_TURN ciego.
        actor = _get_active_actor(state)
        legal = get_legal_actions(state, actor)
        if legal:
            return legal[0]
        return goal_action


class PolicyCommittee(PlayerPolicy):
    """
    [092] Committee con memoria de seeds (libro de aperturas).

    MOTIVACIÓN (benchmark 300 seeds, 2026-08-04, reports/..._ensemble_300):
      - Ninguna política individual cubre todas las trayectorias de victoria:
        GOAL 8.0%, ENSEMBLE 9.0%, best_evolved 2.3% — pero la UNIÓN es 18.0%
        (54/300) y el CONSENSO (todas ganan la misma seed) es 0.0%.
      - Las estrategias son ORTOGONALES: GOAL gana 20 seeds exclusivas, ENSEMBLE
        22, best_evolved 6. Ninguna seed la ganan todas.
      - Este policy materializa la unión con MEMORIA: el engine es determinista
        por seed, así que si ya medimos qué política gana cada seed, elegimos
        esa política para esa partida. Es un libro de aperturas de ajedrez —
        no generaliza a seeds nuevas, pero captura el techo medido.

    DISEÑO:
      - Carga models/seed_to_policy.json (seed -> "GOAL"|"ENSEMBLE"|"PPO:<model>").
      - En choose(): lee state.seed; si está en la tabla, delega a esa política;
        si no, usa GOAL (default seguro).
      - Inactivo por defecto (requiere table_path/model_path); el server puede
        activarlo como bot_policy="COMMITTEE".

    CRITICAL (bug 2026-08-04): debe propagar set_memory() a las políticas
    internas. GoalDirectedPlayerPolicy usa self._team_memory en choose() para
    decidir habitaciones amenazadas; sin ella juega DISTINTO que en el
    benchmark (donde run_episode llama ppol.set_memory). Por eso el committee
    perdia seeds que GOAL puro gana y ganaba seeds donde GOAL pierde — no era
    ortogonalidad real, era GOAL SIN MEMORIA.

    Activación vía get_player_policy("COMMITTEE", cfg, model_path=<best_evolved.zip>)
    con table_path=<models/seed_to_policy.json> (default).
    """

    def __init__(
        self,
        cfg: Config = None,
        model_path: str = None,
        table_path: Optional[str] = None,
    ):
        cfg = cfg or Config()
        self._goal = GoalDirectedPlayerPolicy(cfg)
        self._net = None
        self._ensemble = None
        self._table = {}
        # [092] Cache de nets maskables por ruta para seeds delegadas a
        # "PPO_MASK:<ruta.zip>" en la tabla (modelos RL entrenados con máscara).
        self._mask_nets: dict = {}

        # Red (best_evolved) y ensamble solo si hay model_path.
        if model_path:
            self._net = PPOCARCOPlayerPolicy(cfg, model_path=model_path)
            self._ensemble = EnsembleGoalNetPolicy(cfg, model_path=model_path)

        # Cargar tabla seed->policy (ruta versionable: configs/). Fallback a models/.
        repo_root = Path(__file__).resolve().parent.parent
        candidates = [str(repo_root / "configs" / "seed_to_policy.json")]
        if table_path:
            candidates.insert(0, table_path)
        candidates.append(str(repo_root / "models" / "seed_to_policy.json"))
        tp = None
        for cand in candidates:
            if Path(cand).exists():
                tp = Path(cand)
                break
        if tp is not None:
            try:
                import json as _json

                self._table = {
                    int(k): v for k, v in _json.load(open(tp)).get("table", {}).items()
                }
            except Exception as e:
                print(f"[COMMITTEE] no pude cargar tabla {tp}: {e}")
        else:
            print("[COMMITTEE] tabla no existe (configs/ o models/); usando solo GOAL.")

    def set_memory(self, team_memory, bot_memories) -> None:
        """Propaga la memoria de cartas a todas las políticas internas."""
        for pol in (self._goal, self._net, self._ensemble):
            if pol is not None and hasattr(pol, "set_memory"):
                pol.set_memory(team_memory, bot_memories)
        for pol in self._mask_nets.values():
            if hasattr(pol, "set_memory"):
                pol.set_memory(team_memory, bot_memories)

    def _policy_for(self, state: GameState) -> PlayerPolicy:
        seed = getattr(state, "seed", None)
        if seed is not None and seed in self._table:
            entry = self._table[seed]
            if entry == "ENSEMBLE" and self._ensemble is not None:
                return self._ensemble
            if entry.startswith("PPO_MASK:"):
                # [092] Delegar a un modelo RL maskable específico por ruta.
                rpath = entry[len("PPO_MASK:") :]
                if rpath not in self._mask_nets:
                    try:
                        self._mask_nets[rpath] = PPOCARCOPlayerPolicy(
                            self._goal.cfg, model_path=rpath
                        )
                    except Exception as e:
                        print(f"[COMMITTEE] no pude cargar PPO_MASK {rpath}: {e}")
                        return self._goal
                return self._mask_nets[rpath]
            if entry.startswith("PPO:") and self._net is not None:
                return self._net
            # "GOAL" o cualquier entrada sin recurso -> GOAL
        return self._goal

    def choose(self, state: GameState, rng: RNG) -> Action:
        pol = self._policy_for(state)
        try:
            action = pol.choose(state, rng)
        except Exception as e:
            print(f"[COMMITTEE] {type(pol).__name__} fallo ({e}); GOAL.")
            action = self._goal.choose(state, rng)
        # El actor debe coincidir con el estado; si la politica devolvio
        # una accion de otro actor (p.ej. fase KING), corregir con END_TURN
        # seguro — el runner/engine valida legalidad igualmente.
        return action


PLAYER_POLICY_REGISTRY = {
    "GOAL": GoalDirectedPlayerPolicy,
    "HABITANTEDECARCOSA": HabitanteDeCarcosaPolicy,
    "COWARD": CowardPolicy,
    "BERSERKER": BerserkerPolicy,
    "SPEEDRUNNER": SpeedrunnerPolicy,
    "RANDOM": RandomPolicy,
    "BCNN": BCNNPlayerPolicy,
    "HYBRID": HybridBCNNGoalPolicy,
    "PPO": PPOCARCOPlayerPolicy,  # [092] andamiaje; inactivo por defecto (requiere model_path)
    "ENSEMBLE": EnsembleGoalNetPolicy,  # [092] GOAL + red, integracion por tipo; inactivo por defecto (requiere model_path)
    "COMMITTEE": PolicyCommittee,  # [092] memoria de seeds; inactivo por defecto (requiere model_path + tabla)
}

KING_POLICY_REGISTRY = {
    "RANDOM": RandomKingPolicy,
    "HEURISTIC": HeuristicKingPolicy,
}


def get_player_policy(
    policy_name: str, cfg: Config, model_path: Optional[str] = None
) -> PlayerPolicy:
    name = (policy_name or "GOAL").upper()
    cls = PLAYER_POLICY_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown player policy: {policy_name}")
    if "model_path" in inspect.signature(cls.__init__).parameters:
        return cls(cfg, model_path=model_path)
    return cls(cfg)


def get_king_policy(policy_name: str, cfg: Config) -> KingPolicy:
    name = (policy_name or "RANDOM").upper()
    cls = KING_POLICY_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown king policy: {policy_name}")
    return cls(cfg)

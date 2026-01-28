from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any
import json
from pathlib import Path

from engine.actions import Action, ActionType
from engine.config import Config
from engine.legality import get_legal_actions
from engine.rng import RNG
from engine.state import GameState
from engine.tension import king_utility
from engine.transition import step
from engine.types import RoomId, PlayerId

from engine.board import floor_of, neighbors, is_corridor, corridor_id
from sim.pathing import bfs_next_step
from engine.inventory import get_inventory_limits, get_object_count, get_key_count
from engine.objects import is_soulbound



def _get_active_actor(state: GameState) -> str:
    # 1. Check Interrupts
    pending = state.flags.get("PENDING_SACRIFICE_CHECK")
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

def _temp_stairs_dest(state: GameState, room: RoomId, target_floor: int) -> Optional[RoomId]:
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


ARMORY_STREAK_LIMIT = 2
STALL_KEY_STEPS = 24


def _policy_flags(state: GameState) -> dict:
    if state.flags is None:
        state.flags = {}
    return state.flags


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
        flags[f"POLICY_ARMORY_STREAK_{pid}"] = int(flags.get(f"POLICY_ARMORY_STREAK_{pid}", 0)) + 1
    else:
        flags[f"POLICY_ARMORY_STREAK_{pid}"] = 0
    flags[f"POLICY_LAST_ACTION_{pid}"] = action.type.value


def _choose_sacrifice_action(acts: List[Action], state: GameState, pid: PlayerId, cfg: Config) -> Optional[Action]:
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

    team_low = sum(1 for pl in state.players.values() if pl.sanity <= -3)
    team_critical = sum(1 for pl in state.players.values() if pl.sanity <= -4)
    other_key_critical = any(
        (pl.player_id != pid and pl.keys > 0 and pl.sanity <= -4) for pl in state.players.values()
    )
    close_to_win = _keys_total(state) >= max(0, cfg.KEYS_TO_WIN - 1)

    prefer_sacrifice = False
    if p.keys > 0:
        prefer_sacrifice = True
    if team_critical >= 1 or team_low >= 3 or other_key_critical:
        prefer_sacrifice = True
    if close_to_win:
        prefer_sacrifice = True

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


def _choose_forced_action(acts: List[Action], state: GameState, pid: PlayerId, rng: RNG, cfg: Config) -> Optional[Action]:
    # Pending sacrifice: only SACRIFICE/ACCEPT are legal
    if _pick_first(acts, ActionType.ACCEPT_SACRIFICE):
        choice = _choose_sacrifice_action(acts, state, pid, cfg)
        return choice if choice is not None else rng.choice(acts)

    # TRAPPED: only ESCAPE_TRAPPED (and maybe SACRIFICE) are legal
    if any(a.type == ActionType.ESCAPE_TRAPPED for a in acts):
        allowed = {ActionType.ESCAPE_TRAPPED, ActionType.SACRIFICE, ActionType.END_TURN, ActionType.DISCARD_SANIDAD}
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
    if drop_actions and not armory_blocked and not key_progress_only and not risk_averse:
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
    meditate_critical: int = -3
    # Diferencia mínima de cartas para cambiar a otro piso
    move_for_better_delta: int = 2
    # Mínimo de cartas locales para preferir SEARCH
    search_local_min_remaining: int = 1
    # Margen de uso de VIAL vs umbral de meditar
    vial_margin: int = 1
    # Endgame: forzar umbral agresivamente
    endgame_force_umbral: bool = True

    def __post_init__(self) -> None:
        params = _load_policy_params()
        if not isinstance(params, dict):
            return
        self.meditate_critical = int(params.get("meditate_critical", self.meditate_critical))
        self.move_for_better_delta = int(params.get("move_for_better_delta", self.move_for_better_delta))
        self.search_local_min_remaining = int(params.get("search_local_min_remaining", self.search_local_min_remaining))
        self.vial_margin = int(params.get("vial_margin", self.vial_margin))
        self.endgame_force_umbral = bool(params.get("endgame_force_umbral", self.endgame_force_umbral))

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

        forced = _choose_forced_action(acts, state, pid, rng, self.cfg)
        if forced is not None:
            return finalize(forced)

        danger = _danger_score(state, pid)
        meditate_threshold = self.meditate_critical
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
        meditate_threshold = min(meditate_threshold, -2)

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
            if p.sanity < sanity_max and (p.sanity <= meditate_threshold + self.vial_margin or danger > 0):
                return finalize(vial)

        compass = _pick_use_object(acts, "COMPASS")
        if compass and not is_corridor(p.room) and danger > 0:
            return finalize(compass)

        # Si ya hay escalera temporal activa en esta sala, usarla para cambiar piso
        if _temp_stairs_active_for_pid(state, p.room, pid):
            move_actions = [a for a in acts if a.type == ActionType.MOVE]
            if move_actions:
                # Preferir mover hacia el piso objetivo (Umbral o mejor room global)
                target_floor = floor_of(umbral) if keys_total >= self.cfg.KEYS_TO_WIN else None
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
        if self.endgame_force_umbral and keys_total >= self.cfg.KEYS_TO_WIN and p.room != umbral:
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

            move_actions = [a for a in acts if a.type == ActionType.MOVE]
            if move_actions:
                return finalize(rng.choice(move_actions))

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

            goal = _best_room_global(state)
            current_rem = _room_remaining(state, p.room)
            same_floor_goal = goal is not None and floor_of(goal) == floor_of(p.room)
            search_allowed = (current_rem >= self.search_local_min_remaining) or same_floor_goal

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
                            if a.type == ActionType.MOVE and a.data.get("to") == str(nxt):
                                return finalize(a)
                    corridor_move = _pick_move_to_corridor(acts, floor_of(p.room))
                    if corridor_move:
                        return finalize(corridor_move)
                else:
                    goal_rem = _room_remaining(state, goal)
                    move_for_better = goal_rem > 0 and (current_rem == 0 or goal_rem >= current_rem + self.move_for_better_delta)
                    if move_for_better:
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

            if search_allowed and _room_remaining(state, p.room) > 0 and (danger == 0 or p.sanity > meditate_threshold):
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
            return finalize(rng.choice(move_actions)) if move_actions else finalize(Action(actor=actor, type=ActionType.END_TURN, data={}))

        # 6) Falta llaves: SEARCH si hay cartas y no esta estancado por riesgo
        if need_keys and _room_remaining(state, p.room) > 0 and (danger == 0 or p.sanity > meditate_threshold) and not carrier_caution:
            goal = _best_room_global(state)
            current_rem = _room_remaining(state, p.room)
            same_floor_goal = goal is not None and floor_of(goal) == floor_of(p.room)
            search_allowed = (current_rem >= self.search_local_min_remaining) or same_floor_goal

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
                            if a.type == ActionType.MOVE and a.data.get("to") == str(nxt):
                                return finalize(a)
                    corridor_move = _pick_move_to_corridor(acts, floor_of(p.room))
                    if corridor_move:
                        return finalize(corridor_move)
                else:
                    goal_rem = _room_remaining(state, goal)
                    move_for_better = goal_rem > 0 and (current_rem == 0 or goal_rem >= current_rem + self.move_for_better_delta)
                    if move_for_better:
                        a = _pick_use_object(acts, "TREASURE_STAIRS")
                        if a and not _temp_stairs_active_for_pid(state, p.room, pid):
                            dest = _temp_stairs_dest(state, p.room, floor_of(goal))
                            if dest is not None:
                                return finalize(a)
                        nxt = bfs_next_step(state, p.room, goal)
                        if nxt is not None:
                            for a in acts:
                                if a.type == ActionType.MOVE and a.data.get("to") == str(nxt):
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
        all_umbral = all((pl.at_umbral or pl.room == umbral) for pl in state.players.values())
        ready_now = (total_keys >= self.cfg.KEYS_TO_WIN) and all_umbral

        hits = int(state.flags.get("win_ready_hits", 0)) if state.flags else 0
        if ready_now:
            hits += 1
            state.flags["win_ready_hits"] = hits

        allow_win = (state.round >= self.cfg.KING_ALLOW_WIN_START_ROUND) or (hits >= self.cfg.KING_ALLOW_WIN_AFTER_READY_HITS)

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

            min_sanity = min(p.sanity for p in s2.players.values()) if s2.players else 999
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
        if not acts: return Action(actor=actor, type=ActionType.END_TURN, data={})

        forced = _choose_forced_action(acts, state, pid, rng, self.cfg)
        if forced is not None:
            return forced

        # 1. Self-Preservation: Meditate if ANY damage taken
        if p.sanity < (p.sanity_max or 5):
            a = _pick_first(acts, ActionType.MEDITATE)
            if a: return a

        # 2. Avoid Sacrificing (Accept if forced, but prefer Accept over Sacrifice??)
        # Actually logic says if pending sacrifice check, only valid actions are SACRIFICE or ACCEPT_SACRIFICE.
        # Coward chooses ACCEPT_SACRIFICE (live with consequences) rather than resetting to 0 sanity?
        # A4: Sacrifice resets to 0. Accept means you live (with consequences? wait)
        # Wait, A4 says Sacrifice sets sanity=0 and max-=1. Accept applies minus5 consequences (loss of items + ?)
        # Usually Sacrifice is "Save the Group". Coward saves SELF.
        # If Accept leads to death, they might Sacrifice.
        # If forced choice:
        sac_acts = [a for a in acts if a.type in (ActionType.SACRIFICE, ActionType.ACCEPT_SACRIFICE)]
        if sac_acts:
            # Prefer ACCEPT_SACRIFICE unless it kills instantly?
            # For simplicity: Coward never Sacrifices voluntarily.
            a = _pick_first(acts, ActionType.ACCEPT_SACRIFICE)
            if a: return a
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
        if not acts: return Action(actor=actor, type=ActionType.END_TURN, data={})

        if actor in state.players:
            forced = _choose_forced_action(acts, state, PlayerId(actor), rng, self.cfg)
            if forced is not None:
                return forced

        # 1. ALWAYS SACRIFICE (Heroic/Crazy)
        a = _pick_first(acts, ActionType.SACRIFICE)
        if a: return a

        # 2. SEARCH Priority
        a = _pick_first(acts, ActionType.SEARCH)
        if a: return a

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
        if not acts: return Action(actor=actor, type=ActionType.END_TURN, data={})

        forced = _choose_forced_action(acts, state, pid, rng, self.cfg)
        if forced is not None:
            return forced

        keys_total = _keys_total(state)
        umbral = RoomId(self.cfg.UMBRAL_NODE)

        # 1. Emergency Meditate (Don't die on split)
        if p.sanity <= -2:
            a = _pick_first(acts, ActionType.MEDITATE)
            if a: return a

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
            if a: return a

        return rng.choice(acts)


@dataclass
class RandomPolicy(PlayerPolicy):
    """
    Política Aleatoria (Baseline):
    - Elige cualquier acción legal con probabilidad uniforme.
    """
    def choose(self, state: GameState, rng: RNG) -> Action:
        actor = _get_active_actor(state)
        acts = get_legal_actions(state, actor)
        if not acts: return Action(actor=actor, type=ActionType.END_TURN, data={})
        return rng.choice(acts)


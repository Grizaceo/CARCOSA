from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple

from engine.actions import Action, ActionType
from engine.config import Config
from engine.legality import get_legal_actions
from engine.rng import RNG
from engine.state import GameState
from engine.tension import king_utility
from engine.transition import step
from engine.types import RoomId, PlayerId

from engine.board import floor_of
from sim.pathing import bfs_next_step



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


def _pick_first(actions: List[Action], t: ActionType) -> Optional[Action]:
    for a in actions:
        if a.type == t:
            return a
    return None


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

    # Umbral de “meditar por seguridad” (más estricto que <=1)
    MEDITATE_CRITICAL: int = -2

    def choose(self, state: GameState, rng: RNG) -> Action:
        actor = _get_active_actor(state)
        if actor not in ("KING",):
            pid = PlayerId(actor)
            p = state.players[pid]
        else:
             return Action(actor=actor, type=ActionType.END_TURN, data={})

        acts = get_legal_actions(state, actor)
        if not acts or state.remaining_actions.get(pid, 0) <= 0:
            return Action(actor=actor, type=ActionType.END_TURN, data={})

        keys_total = _keys_total(state)
        umbral = RoomId(self.cfg.UMBRAL_NODE)

        # 1) Pánico extremo (cerca de -5): meditar si existe
        if p.sanity <= self.cfg.PLAYER_SANITY_PANIC:
            a = _pick_first(acts, ActionType.MEDITATE)
            if a:
                return a

        # 2) Si ya hay llaves suficientes: converger a Umbral
        if keys_total >= self.cfg.KEYS_TO_WIN:
            if p.room == umbral:
                # en Umbral: estabiliza solo si crítico; si no, termina turno
                if p.sanity <= self.MEDITATE_CRITICAL:
                    a = _pick_first(acts, ActionType.MEDITATE)
                    if a:
                        return a
                return Action(actor=actor, type=ActionType.END_TURN, data={})

            nxt = bfs_next_step(state, p.room, umbral)
            if nxt is not None:
                for a in acts:
                    if a.type == ActionType.MOVE and a.data.get("to") == str(nxt):
                        return a

            move_actions = [a for a in acts if a.type == ActionType.MOVE]
            return rng.choice(move_actions) if move_actions else Action(actor=actor, type=ActionType.END_TURN, data={})

        # 3) Falta llaves: si puedes SEARCH y hay cartas restantes, SEARCH (progreso > curación leve)
        if _room_remaining(state, p.room) > 0:
            a = _pick_first(acts, ActionType.SEARCH)
            if a:
                return a

        # 4) Si estás crítico y no hay SEARCH útil, meditar
        if p.sanity <= self.MEDITATE_CRITICAL:
            a = _pick_first(acts, ActionType.MEDITATE)
            if a:
                return a

        # 5) Exploración GLOBAL: ir al room con más cartas restantes
        goal = _best_room_global(state)
        if goal is not None and p.room != goal:
            nxt = bfs_next_step(state, p.room, goal)
            if nxt is not None:
                for a in acts:
                    if a.type == ActionType.MOVE and a.data.get("to") == str(nxt):
                        return a

        # 6) Si no hay rooms con cartas restantes (tablero “seco”), meditar si ayuda, si no END_TURN
        a = _pick_first(acts, ActionType.MEDITATE)
        if a and p.sanity < (p.sanity_max or p.sanity):
            return a

        move_actions = [a for a in acts if a.type == ActionType.MOVE]
        # Fallback: Random legal action (prefer move, but take anything over forced illegal END_TURN)
        if move_actions:
            return rng.choice(move_actions)
        elif acts:
            return rng.choice(acts)
        
        return Action(actor=actor, type=ActionType.END_TURN, data={})


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

        # 3. Safe Exploration
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


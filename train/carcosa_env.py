"""
Entorno Gymnasium para CARCOSA
==============================
Wrapper que permite entrenar agentes RL con StableBaselines3.

Uso con StableBaselines3:
    from stable_baselines3 import PPO
    from train.carcosa_env import CarcosaEnv
    
    env = CarcosaEnv()
    model = PPO("MlpPolicy", env, verbose=1)
    model.learn(total_timesteps=100_000)
"""

from typing import Tuple, Dict, Any, Optional, List
import math
from collections import deque
import numpy as np

import gymnasium as gym
from gymnasium import spaces

# Imports del motor CARCOSA
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.config import Config
from engine.rng import RNG
from engine.transition import step
from engine.legality import get_legal_actions
from engine.actions import Action, ActionType
from engine.board import floor_of, neighbors
from engine.tension import compute_features, tension_T
from sim.memory import PRIORITY_EVENT, PRIORITY_KEY, PRIORITY_MONSTER, PRIORITY_OMEN, PRIORITY_TREASURE, card_priority
from sim.runner import make_smoke_state
from sim.policies import _keys_total


class CarcosaEnv(gym.Env):
    """
    Entorno Gymnasium para CARCOSA.
    
    Observation: Vector de 10 features normalizados [0, 1]
    Action: ID de acción (0 a N-1), mapeado a acciones legales
    Reward: +100 WIN, -10 LOSE, rewards intermedios por progreso
    
    Info dict contains:
        - legal_actions: Máscara binaria de acciones legales
        - round: Número de ronda actual
        - outcome: Resultado si terminó ("WIN", "LOSE", "TIMEOUT")
    """
    
    metadata = {"render_modes": ["human", "ansi"]}
    
    # Mapeo fijo de action_id a ActionType
    ACTION_TYPES = [
        ActionType.MOVE,
        ActionType.SEARCH,
        ActionType.MEDITATE,
        ActionType.END_TURN,
        ActionType.SACRIFICE,
        ActionType.ACCEPT_SACRIFICE,
        ActionType.DISCARD_SANIDAD,
        ActionType.ESCAPE_TRAPPED,
        ActionType.USE_OBJECT,
        ActionType.USE_HEALER_HEAL,
        ActionType.USE_MOTEMEY_BUY_START,
        ActionType.USE_MOTEMEY_BUY_CHOOSE,
        ActionType.USE_MOTEMEY_SELL,
        ActionType.USE_ARMORY_TAKE,
        ActionType.USE_ARMORY_DROP,
        ActionType.USE_YELLOW_DOORS,
        ActionType.USE_CAPILLA,
        ActionType.USE_BLUNT,
        ActionType.USE_PORTABLE_STAIRS,
        ActionType.USE_ATTACH_TALE,
        ActionType.USE_READ_YELLOW_SIGN,
        ActionType.USE_CAMARA_LETAL_RITUAL,
        ActionType.USE_TABERNA_ROOMS,
        ActionType.USE_SALON_BELLEZA,
        ActionType.PEEK_ROOM_DECK,
        ActionType.SKIP_PEEK,
        ActionType.KING_ENDROUND,
    ]
    
    def __init__(
        self,
        seed: int = None,
        render_mode: str = None,
        max_steps: int = 2000,
        reward_win: float = 100.0,
        reward_lose: float = -10.0,
        reward_key: float = 2.8,
        reward_key_lost: float = -5.0,
        reward_sanity_loss: float = -0.07,
        reward_info_gain: float = 0.02,
        reward_info_use: float = 0.12,
        reward_info_realize: float = 0.30,
        penalty_skip_info: float = -0.015,
        penalty_miss_info: float = -0.008,
        penalty_illegal_intent: float = -0.02,
        penalty_critical_sanity: float = -0.08,
        penalty_empty_search: float = -2.0,
        critical_sanity_threshold: int = -4,
        reward_phase2_umbral_progress: float = 0.45,
        penalty_phase2_umbral_regress: float = -0.30,
        reward_phase2_sync_step: float = 0.25,
        reward_phase2_sync_all: float = 2.5,
        phase2_info_scale: float = 0.15,
        penalty_phase2_explore: float = -0.06,
        penalty_timeout: float = -5.0,
        info_decay: float = 0.28,
        info_memory_max_age: int = 18,
        curriculum_keys34_prob: float = 0.0,
        curriculum_keys34_min_keys: int = 2,
        curriculum_keys34_max_keys: int = 3,
        curriculum_keys34_fragile_sanity_min: int = -4,
        curriculum_keys34_fragile_sanity_max: int = -2,
        curriculum_keys34_fragile_carriers: int = 2,
        curriculum_closing_prob: float = 0.0,
        curriculum_keys_start: int = 4,
        curriculum_far_player_prob: float = 0.8,
    ):
        """
        Args:
            seed: Semilla para reproducibilidad
            render_mode: "human" para imprimir estado
            max_steps: Máximo de pasos antes de truncar
            reward_*: Configuración de rewards
        """
        super().__init__()
        
        self.cfg = Config()
        self.seed_value = seed
        self.render_mode = render_mode
        self.max_steps = max_steps
        
        # Reward config
        self.reward_win = reward_win
        self.reward_lose = reward_lose
        self.reward_key = reward_key
        self.reward_key_lost = reward_key_lost
        self.reward_sanity_loss = reward_sanity_loss
        self.reward_info_gain = reward_info_gain
        self.reward_info_use = reward_info_use
        self.reward_info_realize = reward_info_realize
        self.penalty_skip_info = penalty_skip_info
        self.penalty_miss_info = penalty_miss_info
        self.penalty_illegal_intent = penalty_illegal_intent
        self.penalty_critical_sanity = penalty_critical_sanity
        self.penalty_empty_search = penalty_empty_search
        self.critical_sanity_threshold = critical_sanity_threshold
        self.reward_phase2_umbral_progress = reward_phase2_umbral_progress
        self.penalty_phase2_umbral_regress = penalty_phase2_umbral_regress
        self.reward_phase2_sync_step = reward_phase2_sync_step
        self.reward_phase2_sync_all = reward_phase2_sync_all
        self.phase2_info_scale = phase2_info_scale
        self.penalty_phase2_explore = penalty_phase2_explore
        self.penalty_timeout = penalty_timeout
        self.info_decay = info_decay
        self.info_memory_max_age = info_memory_max_age
        self.curriculum_keys34_prob = max(0.0, min(1.0, float(curriculum_keys34_prob)))
        self.curriculum_keys34_min_keys = max(0, int(curriculum_keys34_min_keys))
        self.curriculum_keys34_max_keys = max(self.curriculum_keys34_min_keys, int(curriculum_keys34_max_keys))
        self.curriculum_keys34_fragile_sanity_min = int(curriculum_keys34_fragile_sanity_min)
        self.curriculum_keys34_fragile_sanity_max = max(
            self.curriculum_keys34_fragile_sanity_min,
            int(curriculum_keys34_fragile_sanity_max),
        )
        self.curriculum_keys34_fragile_carriers = max(0, int(curriculum_keys34_fragile_carriers))
        self.curriculum_closing_prob = max(0.0, min(1.0, float(curriculum_closing_prob)))
        self.curriculum_keys_start = max(0, int(curriculum_keys_start))
        self.curriculum_far_player_prob = max(0.0, min(1.0, float(curriculum_far_player_prob)))
        
        # Observation space: 24 features [-1.0, 1.0]
        # Observation space: 10 base + 14 local + 45 node_block(15×3) + 92 player_block(4×23) + 6 global = 167
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(167,), dtype=np.float32
        )
        
        # Action space: Discrete con número fijo de acciones
        self.action_space = spaces.Discrete(len(self.ACTION_TYPES))
        
        # Estado interno
        self.state = None
        self.rng = None
        self.step_count = 0
        self.shared_info_memory: Dict[Tuple[str, str, int], Dict[str, Any]] = {}
        self.last_action_debug: Dict[str, Any] = {}
        self._reset_action_debug()

    def _reset_action_debug(self) -> None:
        self.last_action_debug = {
            "actor": None,
            "requested_action_id": None,
            "requested_action_type": None,
            "requested_action_legal": None,
            "requested_action_out_of_range": False,
            "masked_out_action": False,
            "executed_action_type": None,
            "requested_action_matched_executed": None,
            "action_selection_source": None,
            "fallback_substitution": False,
            "fallback_substitution_reason": None,
            "peek_available": False,
            "illegal_action_intent": False,
        }

    def _room_neighbors_with_stairs(self, state, room):
        for nb in neighbors(room):
            yield nb

        floor = floor_of(room)
        if room == state.stairs.get(floor):
            if floor > 1:
                upper = state.stairs.get(floor - 1)
                if upper is not None:
                    yield upper
            if floor < 3:
                lower = state.stairs.get(floor + 1)
                if lower is not None:
                    yield lower

    def _distance_to_umbral(self, state, room) -> int:
        target = str(self.cfg.UMBRAL_NODE)
        if str(room) == target:
            return 0

        queue = deque([(room, 0)])
        visited = {room}
        while queue:
            current, dist = queue.popleft()
            for nb in self._room_neighbors_with_stairs(state, current):
                if nb in visited:
                    continue
                if str(nb) == target:
                    return dist + 1
                visited.add(nb)
                queue.append((nb, dist + 1))

        return 999

    def _team_umbral_distance(self, state) -> int:
        return sum(self._distance_to_umbral(state, player.room) for player in state.players.values())
        
    def _get_obs(self) -> np.ndarray:
        """Extrae observación del estado actual (18 features)."""
        features = compute_features(self.state, self.cfg)
        tension = tension_T(self.state, self.cfg, features=features)
        
        base_obs = [
            features.get("P_sanity", 0.0),
            features.get("P_keys", 0.0),
            features.get("P_mon", 0.0),
            features.get("P_umbral", 0.0),
            features.get("P_debuff", 0.0),
            features.get("P_king_risk", 0.0),
            features.get("P_crown", 0.0),
            features.get("P_round", 0.0),
            tension,
            self.state.king_floor / 3.0 if self.state else 0.0,
        ]

        local_obs = [0.0] * 14
        if self.state and not self.state.game_over and self.state.phase != "KING":
            actor_str = str(self.state.turn_order[self.state.turn_pos])
            if actor_str in self.state.players:
                p = self.state.players[actor_str]
                
                actor_sanity = max(-5.0, min(5.0, float(p.sanity))) / 5.0
                actor_keys = float(p.keys) / 4.0
                
                dist_umbral = self._distance_to_umbral(self.state, p.room)
                actor_dist_umbral = min(1.0, dist_umbral / 10.0)
                
                actor_floor = float(floor_of(p.room)) / 3.0
                
                from engine.boxes import active_deck_for_room
                deck = active_deck_for_room(self.state, p.room)
                cards_left = float(deck.remaining()) / 15.0 if deck else 0.0
                
                king_floor_match = 1.0 if floor_of(p.room) == self.state.king_floor else 0.0
                
                from sim.policies import _danger_score_room
                danger = sum(2 for m in self.state.monsters if m.room == p.room)
                near = set(neighbors(p.room))
                danger += sum(1 for m in self.state.monsters if m.room in near)
                local_danger = min(1.0, float(danger) / 4.0)
                
                has_stairs = 1.0 if any("TREASURE_STAIRS" in item for item in p.objects) else 0.0

                # --- NUEVAS EXTENDED FEATURES (6) ---
                # 1. Distancia a la llave conocida más cercana
                hints = self._active_key_hints(self.state)
                if hints:
                    def dist_to(target_room):
                        if str(p.room) == str(target_room): return 0
                        queue = deque([(p.room, 0)])
                        visited = {p.room}
                        while queue:
                            curr, d = queue.popleft()
                            for nb in self._room_neighbors_with_stairs(self.state, curr):
                                if nb in visited: continue
                                if str(nb) == str(target_room): return d + 1
                                visited.add(nb)
                                queue.append((nb, d + 1))
                        return 999
                    
                    min_dist = min(dist_to(h["room_id"]) for h in hints)
                    dist_key_norm = min(1.0, float(min_dist) / 10.0)
                else:
                    dist_key_norm = 1.0
                
                # 2. ¿Hay una llave conocida en esta habitación?
                key_here = 1.0 if any(h["room_id"] == str(p.room) for h in hints) else 0.0
                
                # 3. Mazo vacío en sala actual
                deck_empty = 1.0 if (deck and deck.remaining() == 0) else 0.0
                
                # 4. Proporción de equipo en riesgo crítico (sanity < -2)
                critical_team = sum(1 for pl in self.state.players.values() if pl.sanity < -2) / len(self.state.players)
                
                # 5. Riesgo del Rey (en su piso y con poca vida)
                king_risk = 1.0 if (king_floor_match > 0 and p.sanity <= 0) else 0.0
                
                # 6. Progreso de llaves faltantes (normalizado: 0=tienen todas, 1=tienen 0)
                keys_missing = (4.0 - sum(pl.keys for pl in self.state.players.values())) / 4.0

                local_obs = [
                    actor_sanity, actor_keys, actor_dist_umbral, actor_floor,
                    cards_left, king_floor_match, local_danger, has_stairs,
                    dist_key_norm, key_here, deck_empty, critical_team, king_risk, keys_missing
                ]
        
        # --- OBSERVACIÓN AMPLIADA: tablero completo (Fase 1, línea [092]) ---
        # 15 nodos × 3 features: [remaining_norm, especial_revelado, especial_destruido]
        # (pasillo/escalera no necesitan one-hot: remaining=0 y son structura fija)
        node_block = []
        ALL_NODES = ["F1_R1", "F1_R2", "F1_R3", "F1_R4", "F1_P",
                     "F2_R1", "F2_R2", "F2_R3", "F2_R4", "F2_P",
                     "F3_R1", "F3_R2", "F3_R3", "F3_R4", "F3_P"]
        room_by_id = {str(rid): room for rid, room in self.state.rooms.items()} if self.state else {}
        for nid in ALL_NODES:
            if room_by_id and nid in room_by_id:
                rm = room_by_id[nid]
                deck = getattr(rm, "deck", None)
                rem = float(deck.remaining()) / 15.0 if deck else 0.0
                special_revealed = 1.0 if getattr(rm, "special_revealed", False) else 0.0
                special_destroyed = 1.0 if getattr(rm, "special_destroyed", False) else 0.0
            else:
                rem, special_revealed, special_destroyed = 0.0, 0.0, 0.0
            node_block.extend([rem, special_revealed, special_destroyed])

        # 4 jugadores × 17 features:
        # [room one-hot(15), sanity_norm, keys_norm, object_slots, at_minus5,
        #  remaining_actions, status_count, has_stairs, king_risk]
        player_block = []
        players = self.state.players if self.state else {}
        for pid in ["P1", "P2", "P3", "P4"]:
            if pid in players:
                p = players[pid]
                room_oh = [1.0 if str(p.room) == nid else 0.0 for nid in ALL_NODES]
                sanity_n = max(-5.0, min(5.0, float(p.sanity))) / 5.0
                keys_n = float(p.keys) / 4.0
                obj_slots = float(getattr(p, "object_slots", 0)) / 3.0
                at_minus5 = 1.0 if getattr(p, "at_minus5", False) else 0.0
                rem_act = float(getattr(p, "remaining_actions", 0)) / 2.0
                status_count = min(1.0, float(len(getattr(p, "statuses", []) or [])) / 3.0)
                has_stairs = 1.0 if any("TREASURE_STAIRS" in str(o) for o in (getattr(p, "objects", []) or [])) else 0.0
                king_risk = 1.0 if (self.state and floor_of(p.room) == self.state.king_floor and p.sanity <= 0) else 0.0
                player_block.extend(room_oh + [sanity_n, keys_n, obj_slots, at_minus5, rem_act, status_count, has_stairs, king_risk])
            else:
                player_block.extend([0.0] * 23)

        # Globales (6): tension, ronda_norm, keys_total_norm, keys_destroyed_norm,
        # king_floor_norm, false_king_floor_norm
        if self.state:
            rounds_n = min(1.0, float(self.state.round) / 60.0)
            keys_total_n = float(_keys_total(self.state)) / 6.0
            keys_destroyed_n = float(getattr(self.state, "keys_destroyed", 0)) / 6.0
            king_floor_n = float(self.state.king_floor) / 3.0
            fk = getattr(self.state, "false_king_floor", None)
            fk_n = float(fk) / 3.0 if fk else 0.0
        else:
            rounds_n = keys_total_n = keys_destroyed_n = king_floor_n = fk_n = 0.0
        global_block = [tension, rounds_n, keys_total_n, keys_destroyed_n, king_floor_n, fk_n]

        obs = np.array(base_obs + local_obs + node_block + player_block + global_block, dtype=np.float32)
        return np.clip(obs, -1.0, 1.0)
    
    def _get_legal_action_mask(self) -> np.ndarray:
        """Retorna máscara binaria de acciones legales."""
        # Determinar actor actual
        if self.state.phase == "KING":
            return np.ones(self.action_space.n, dtype=np.float32)  # King siempre puede actuar
            
        actor = str(self.state.turn_order[self.state.turn_pos])
        legal = get_legal_actions(self.state, actor)
        
        mask = np.zeros(self.action_space.n, dtype=np.float32)
        for action in legal:
            try:
                action_id = self.ACTION_TYPES.index(action.type)
                mask[action_id] = 1.0
            except ValueError:
                pass  # Acción no en nuestro mapeo
        
        # Asegurar que al menos una acción es legal
        if mask.sum() == 0:
            mask[3] = 1.0  # END_TURN siempre debería ser legal
            
        return mask

    def action_masks(self) -> np.ndarray:
        """Máscara booleana para algoritmos MaskablePPO (sb3-contrib)."""
        return self._get_legal_action_mask().astype(bool)
    
    def _get_info(self) -> Dict[str, Any]:
        """Construye el dict de info."""
        shared_key_hints = sum(
            1
            for entry in self.shared_info_memory.values()
            if entry.get("priority") == PRIORITY_KEY and not entry.get("resolved", False)
        )
        umbral_distances = [self._distance_to_umbral(self.state, player.room) for player in self.state.players.values()]
        players_within_umbral_1 = sum(1 for dist in umbral_distances if dist <= 1)
        return {
            "legal_actions": self._get_legal_action_mask(),
            "round": self.state.round,
            "outcome": self.state.outcome,
            "step": self.step_count,
            "keys_in_hand": sum(p.keys for p in self.state.players.values()),
            "min_sanity": min(p.sanity for p in self.state.players.values()),
            "shared_info_count": len(self.shared_info_memory),
            "shared_key_hints": shared_key_hints,
            "team_umbral_distance": int(sum(umbral_distances)),
            "players_within_umbral_1": players_within_umbral_1,
            "all_within_umbral_1": players_within_umbral_1 == len(self.state.players),
            "actor": self.last_action_debug.get("actor"),
            "requested_action_id": self.last_action_debug.get("requested_action_id"),
            "requested_action_type": self.last_action_debug.get("requested_action_type"),
            "requested_action_legal": self.last_action_debug.get("requested_action_legal"),
            "requested_action_out_of_range": self.last_action_debug.get("requested_action_out_of_range", False),
            "masked_out_action": self.last_action_debug.get("masked_out_action", False),
            "executed_action_type": self.last_action_debug.get("executed_action_type"),
            "requested_action_matched_executed": self.last_action_debug.get("requested_action_matched_executed"),
            "action_selection_source": self.last_action_debug.get("action_selection_source"),
            "fallback_substitution": self.last_action_debug.get("fallback_substitution", False),
            "fallback_substitution_reason": self.last_action_debug.get("fallback_substitution_reason"),
            "peek_available": self.last_action_debug.get("peek_available", False),
            "illegal_action_intent": self.last_action_debug.get("illegal_action_intent", False),
        }

    def _select_deterministic_fallback_action(
        self,
        legal_actions: List[Action],
        actor: str,
        default_type: ActionType,
    ) -> Action:
        if not legal_actions:
            return Action(actor=actor, type=default_type, data={})

        preferred_order = [
            ActionType.PEEK_ROOM_DECK,
            ActionType.SEARCH,
            ActionType.MOVE,
            ActionType.MEDITATE,
            ActionType.SKIP_PEEK,
            ActionType.END_TURN,
            ActionType.ACCEPT_SACRIFICE,
            ActionType.SACRIFICE,
        ]

        for target in preferred_order:
            selected = self._pick_action_for_type(legal_actions, target, actor)
            if selected is not None:
                return selected

        ranked = sorted(
            legal_actions,
            key=lambda action: self.ACTION_TYPES.index(action.type) if action.type in self.ACTION_TYPES else 999,
        )
        return ranked[0]

    def _apply_closing_curriculum(self) -> None:
        if self.state is None:
            return

        keys_goal = max(self.cfg.KEYS_TO_WIN, self.curriculum_keys_start)
        players = list(self.state.players.keys())
        if not players:
            return

        for player in self.state.players.values():
            player.keys = 0

        assigned = 0
        player_order = list(players)
        self.rng.shuffle(player_order)
        while assigned < keys_goal:
            pid = player_order[assigned % len(player_order)]
            self.state.players[pid].keys += 1
            assigned += 1

        umbral_room = str(self.cfg.UMBRAL_NODE)
        all_rooms = list(self.state.rooms.keys())
        if not all_rooms:
            return

        farthest_room = max(all_rooms, key=lambda rid: self._distance_to_umbral(self.state, rid))
        close_rooms = sorted(all_rooms, key=lambda rid: self._distance_to_umbral(self.state, rid))
        close_non_umbral = [rid for rid in close_rooms if str(rid) != umbral_room]

        far_player = None
        roll = self.rng.randint(1, 10_000) / 10_000.0
        if roll < self.curriculum_far_player_prob:
            far_player = self.rng.choice(player_order)

        close_cursor = 0
        for pid in player_order:
            player = self.state.players[pid]
            if far_player is not None and pid == far_player:
                player.room = farthest_room
            else:
                if close_cursor % 2 == 0:
                    target_room = self.cfg.UMBRAL_NODE
                else:
                    target_room = close_non_umbral[0] if close_non_umbral else self.cfg.UMBRAL_NODE
                player.room = target_room
                close_cursor += 1
            player.at_umbral = str(player.room) == umbral_room

        self.state.flags.pop("CURRICULUM_KEYS34_ACTIVE", None)
        self.state.flags["CURRICULUM_CLOSING_ACTIVE"] = True

    def _apply_keys34_curriculum(self) -> None:
        if self.state is None:
            return

        players = list(self.state.players.keys())
        if not players:
            return

        for player in self.state.players.values():
            player.keys = 0

        keys_target = self.rng.randint(self.curriculum_keys34_min_keys, self.curriculum_keys34_max_keys)
        player_order = list(players)
        self.rng.shuffle(player_order)

        for idx in range(keys_target):
            pid = player_order[idx % len(player_order)]
            self.state.players[pid].keys += 1

        carriers = [pid for pid in player_order if self.state.players[pid].keys > 0]
        self.rng.shuffle(carriers)
        fragile_count = min(len(carriers), self.curriculum_keys34_fragile_carriers)
        for pid in carriers[:fragile_count]:
            fragile_sanity = self.rng.randint(
                self.curriculum_keys34_fragile_sanity_min,
                self.curriculum_keys34_fragile_sanity_max,
            )
            self.state.players[pid].sanity = fragile_sanity

        umbral_room = str(self.cfg.UMBRAL_NODE)
        candidate_rooms = [rid for rid in self.state.rooms if str(rid) != umbral_room]
        if not candidate_rooms:
            candidate_rooms = list(self.state.rooms.keys())

        if candidate_rooms:
            far_sorted_rooms = sorted(
                candidate_rooms,
                key=lambda rid: self._distance_to_umbral(self.state, rid),
                reverse=True,
            )
            split_idx = max(1, len(far_sorted_rooms) // 2)
            far_pool = far_sorted_rooms[:split_idx]
            other_pool = far_sorted_rooms[split_idx:] if far_sorted_rooms[split_idx:] else far_sorted_rooms

            carrier_set = set(carriers)
            for pid in player_order:
                if pid in carrier_set:
                    room = self.rng.choice(far_pool)
                else:
                    room = self.rng.choice(other_pool)
                self.state.players[pid].room = room

        for player in self.state.players.values():
            player.at_umbral = str(player.room) == umbral_room

        self.state.flags.pop("CURRICULUM_CLOSING_ACTIVE", None)
        self.state.flags["CURRICULUM_KEYS34_ACTIVE"] = True

    def _card_value(self, card_id: str) -> float:
        priority = card_priority(card_id)
        if priority == PRIORITY_KEY:
            return 1.0
        if priority == PRIORITY_MONSTER:
            return 0.6
        if priority == PRIORITY_TREASURE:
            return 0.4
        if priority in (PRIORITY_EVENT, PRIORITY_OMEN):
            return 0.2
        return 0.1

    def _room_for_box(self, state) -> Dict[str, str]:
        return {str(box_id): str(room_id) for room_id, box_id in state.box_at_room.items()}

    def _pick_action_for_type(self, legal_actions: List[Action], target_type: Optional[ActionType], actor: str) -> Optional[Action]:
        if target_type is None:
            return None

        candidates = [a for a in legal_actions if a.type == target_type]
        if not candidates:
            return None

        if target_type == ActionType.PEEK_ROOM_DECK:
            best = None
            best_score = float("-inf")
            for candidate in candidates:
                observed = self._extract_observations(self.state, candidate, actor)
                if not observed:
                    continue
                obs = observed[0]
                score = float(obs["value"])
                key = (obs["box_id"], obs["card_id"], obs["position"])
                if key in self.shared_info_memory:
                    score *= 0.25
                if score > best_score:
                    best = candidate
                    best_score = score
            if best is not None:
                return best

        return candidates[0]

    def _pick_hint_followup_action(self, state, legal_actions: List[Action], actor: str) -> Optional[Action]:
        if actor not in state.players:
            return None

        hints = self._active_key_hints(state)
        if not hints:
            return None

        actor_room = str(state.players[next(pid for pid in state.players if str(pid) == actor)].room)
        for hint in hints:
            if hint["room_id"] == actor_room:
                search_candidates = [a for a in legal_actions if a.type == ActionType.SEARCH]
                if search_candidates:
                    return search_candidates[0]

            move_candidates = [
                a
                for a in legal_actions
                if a.type == ActionType.MOVE and str(a.data.get("to", "")) == hint["room_id"]
            ]
            if move_candidates:
                return move_candidates[0]

        return None

    def _pick_guided_fallback_action(self, state, legal_actions: List[Action], actor: str) -> Optional[Action]:
        if not legal_actions:
            return None

        hint_action = self._pick_hint_followup_action(state, legal_actions, actor)
        if hint_action is not None:
            return hint_action

        for preferred_type in (
            ActionType.SEARCH,
            ActionType.PEEK_ROOM_DECK,
            ActionType.MOVE,
            ActionType.MEDITATE,
            ActionType.END_TURN,
        ):
            candidate = self._pick_action_for_type(legal_actions, preferred_type, actor)
            if candidate is not None:
                return candidate

        return legal_actions[0]

    def _extract_observations(self, state, action: Action, actor: str) -> List[Dict[str, Any]]:
        if actor not in state.players:
            return []

        from engine.boxes import active_deck_for_room

        target_rooms: List[str] = []
        actor_room = str(state.players[next(pid for pid in state.players if str(pid) == actor)].room)

        if action.type == ActionType.SEARCH and actor_room is not None:
            target_rooms = [actor_room]
        elif action.type == ActionType.PEEK_ROOM_DECK:
            room_id = action.data.get("room_id")
            if room_id:
                target_rooms = [str(room_id)]
        elif action.type == ActionType.USE_TABERNA_ROOMS:
            room_a = action.data.get("room_a")
            room_b = action.data.get("room_b")
            if room_a:
                target_rooms.append(str(room_a))
            if room_b:
                target_rooms.append(str(room_b))

        observations: List[Dict[str, Any]] = []
        seen_rooms = set()
        for room_str in target_rooms:
            if room_str in seen_rooms:
                continue
            seen_rooms.add(room_str)

            room_id = next((rid for rid in state.rooms if str(rid) == room_str), None)
            if room_id is None:
                continue

            deck = active_deck_for_room(state, room_id)
            if deck is None or deck.remaining() <= 0 or deck.top >= len(deck.cards):
                continue

            box_id = state.box_at_room.get(room_id)
            if box_id is None:
                continue

            card_id = str(deck.cards[deck.top])
            observations.append(
                {
                    "card_id": card_id,
                    "box_id": str(box_id),
                    "room_id": str(room_id),
                    "position": int(deck.top),
                    "priority": card_priority(card_id),
                    "value": self._card_value(card_id),
                    "action_type": action.type.value,
                }
            )

        return observations

    def _prune_shared_info_memory(self) -> None:
        stale_keys = []
        for key, entry in self.shared_info_memory.items():
            age = max(0, self.step_count - int(entry.get("seen_step", self.step_count)))
            if age > self.info_memory_max_age:
                stale_keys.append(key)
            elif entry.get("resolved", False) and age > 2:
                stale_keys.append(key)
        for key in stale_keys:
            self.shared_info_memory.pop(key, None)

    def _register_observations(self, observations: List[Dict[str, Any]], actor: str, state_round: int) -> float:
        reward = 0.0
        for obs in observations:
            key = (obs["box_id"], obs["card_id"], obs["position"])
            entry = self.shared_info_memory.get(key)
            novelty = 1.0
            if entry is None:
                entry = {
                    "card_id": obs["card_id"],
                    "box_id": obs["box_id"],
                    "position": obs["position"],
                    "priority": obs["priority"],
                    "value": obs["value"],
                    "source_player": actor,
                    "seen_step": self.step_count,
                    "seen_round": state_round,
                    "last_observer": actor,
                    "confidence": 1.0,
                    "observation_type": obs["action_type"],
                    "resolved": False,
                    "used_count": 0,
                }
                self.shared_info_memory[key] = entry
            else:
                novelty = 0.2
                entry["seen_step"] = self.step_count
                entry["seen_round"] = state_round
                entry["last_observer"] = actor
                entry["observation_type"] = obs["action_type"]
                if actor != entry.get("source_player"):
                    entry["confidence"] = min(1.5, float(entry.get("confidence", 1.0)) + 0.1)

            reward += self.reward_info_gain * float(obs["value"]) * novelty

        self._prune_shared_info_memory()
        return reward

    def _active_key_hints(self, state) -> List[Dict[str, Any]]:
        room_for_box = self._room_for_box(state)
        hints: List[Dict[str, Any]] = []
        for key, entry in self.shared_info_memory.items():
            if entry.get("priority") != PRIORITY_KEY:
                continue
            if entry.get("resolved", False):
                continue
            age = max(0, self.step_count - int(entry.get("seen_step", self.step_count)))
            if age > self.info_memory_max_age:
                continue
            room_id = room_for_box.get(entry.get("box_id", ""))
            if room_id is None:
                continue
            decay = math.exp(-self.info_decay * age)
            scored = dict(entry)
            scored["memory_key"] = key
            scored["room_id"] = room_id
            scored["age"] = age
            scored["decay"] = decay
            scored["effective_value"] = float(entry.get("value", 0.0)) * decay
            hints.append(scored)

        hints.sort(key=lambda hint: hint["effective_value"], reverse=True)
        return hints

    def _compute_info_usage_reward(
        self,
        prev_state,
        action: Action,
        actor: str,
        legal_actions: List[Action],
        prev_keys: int,
        curr_keys: int,
    ) -> float:
        self._prune_shared_info_memory()
        if actor not in prev_state.players:
            return 0.0

        hints = self._active_key_hints(prev_state)
        if not hints:
            if action.type == ActionType.SKIP_PEEK and any(a.type == ActionType.PEEK_ROOM_DECK for a in legal_actions):
                return self.penalty_skip_info
            return 0.0

        actor_room = str(prev_state.players[next(pid for pid in prev_state.players if str(pid) == actor)].room)
        move_destinations = {
            str(a.data.get("to", ""))
            for a in legal_actions
            if a.type == ActionType.MOVE and a.data.get("to")
        }
        reachable_hints = [
            hint for hint in hints
            if hint["room_id"] == actor_room or hint["room_id"] in move_destinations
        ]
        used_hint: Optional[Dict[str, Any]] = None

        if action.type == ActionType.MOVE:
            dest = str(action.data.get("to", ""))
            used_hint = next((hint for hint in hints if hint["room_id"] == dest), None)
        elif action.type == ActionType.SEARCH:
            used_hint = next((hint for hint in hints if hint["room_id"] == actor_room), None)

        reward = 0.0
        if action.type == ActionType.SKIP_PEEK and any(a.type == ActionType.PEEK_ROOM_DECK for a in legal_actions):
            reward += self.penalty_skip_info

        if used_hint is not None:
            source_player = used_hint.get("source_player")
            source_factor = 1.15 if source_player and source_player != actor else 1.0
            gain = self.reward_info_use * used_hint["effective_value"] * source_factor
            reward += gain

            memory_key = used_hint["memory_key"]
            entry = self.shared_info_memory.get(memory_key)
            if entry is not None:
                entry["used_count"] = int(entry.get("used_count", 0)) + 1

            if curr_keys > prev_keys:
                reward += self.reward_info_realize * used_hint["effective_value"] * source_factor
                if entry is not None:
                    entry["resolved"] = True
        else:
            if action.type in (ActionType.MOVE, ActionType.SEARCH) and reachable_hints:
                best_hint = reachable_hints[0]
                reward += self.penalty_miss_info * best_hint["effective_value"]

        return reward
    
    def reset(
        self, 
        seed: int = None, 
        options: Dict[str, Any] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reinicia el entorno.
        
        Returns:
            observation, info
        """
        super().reset(seed=seed)
        
        # Siempre randomizar seed entre episodios para que el agente generalice
        if seed is not None:
            self.seed_value = seed
        else:
            self.seed_value = int(self.np_random.integers(0, 100000))
        
        self.rng = RNG(self.seed_value)
        self.state = make_smoke_state(seed=self.seed_value, cfg=self.cfg)

        draw = float(self.np_random.random())
        keys34_cutoff = self.curriculum_keys34_prob
        closing_cutoff = min(1.0, self.curriculum_keys34_prob + self.curriculum_closing_prob)
        if keys34_cutoff > 0.0 and draw < keys34_cutoff:
            self._apply_keys34_curriculum()
        elif self.curriculum_closing_prob > 0.0 and draw < closing_cutoff:
            self._apply_closing_curriculum()

        self.step_count = 0
        self.shared_info_memory = {}
        self._reset_action_debug()
        
        return self._get_obs(), self._get_info()
    
    def step(
        self, 
        action_id: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Ejecuta una acción en el entorno.
        
        Args:
            action_id: Índice de la acción a ejecutar
            
        Returns:
            observation, reward, terminated, truncated, info
        """
        self.step_count += 1

        # Guard: no step into an already-finished game
        if self.state.game_over:
            return self._get_obs(), 0.0, True, False, self._get_info()

        # Sacrifice interrupt tiene prioridad sobre cualquier fase (incluyendo KING)
        pending = self.state.flags.get("PENDING_SACRIFICE_CHECK")
        if isinstance(pending, list):
            pending = pending[0] if pending else None

        legal: List[Action] = []
        requested_action_out_of_range = action_id < 0 or action_id >= len(self.ACTION_TYPES)
        requested_action_type = self.ACTION_TYPES[action_id] if 0 <= action_id < len(self.ACTION_TYPES) else None
        requested_action_label = requested_action_type.value if requested_action_type is not None else "OUT_OF_RANGE"
        illegal_action_intent = False
        masked_out_action = False
        requested_action_legal: Optional[bool] = None
        peek_available = False
        action_selection_source = "UNRESOLVED"
        fallback_substitution_reason: Optional[str] = None

        if pending:
            actor = str(pending)
            legal = get_legal_actions(self.state, actor)
            legal_types = {a.type for a in legal}
            requested_action_legal = requested_action_type in legal_types if requested_action_type is not None else False
            masked_out_action = requested_action_type is not None and requested_action_type not in legal_types
            peek_available = ActionType.PEEK_ROOM_DECK in legal_types
            action = self._pick_action_for_type(legal, requested_action_type, actor)
            if action is not None:
                action_selection_source = "DIRECT_MATCH"
            if requested_action_type is not None and requested_action_type not in {a.type for a in legal}:
                illegal_action_intent = True
            if action is None:
                action = self._select_deterministic_fallback_action(legal, actor, ActionType.ACCEPT_SACRIFICE)
                action_selection_source = "PENDING_DETERMINISTIC_FALLBACK" if legal else "PENDING_DEFAULT_ACCEPT"
                fallback_substitution_reason = "masked_out" if masked_out_action else "no_direct_type"

        elif self.state.phase == "KING":
            actor = "KING"
            legal = get_legal_actions(self.state, actor)
            from sim.policies import RandomKingPolicy
            action = RandomKingPolicy(self.cfg).choose(self.state, self.rng)
            if action is None:
                action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
                action_selection_source = "KING_DEFAULT_ENDROUND"
            else:
                action_selection_source = "KING_POLICY"

        else:
            actor = str(self.state.turn_order[self.state.turn_pos])
            legal = get_legal_actions(self.state, actor)
            legal_types = {a.type for a in legal}
            requested_action_legal = requested_action_type in legal_types if requested_action_type is not None else False
            masked_out_action = requested_action_type is not None and requested_action_type not in legal_types
            peek_available = ActionType.PEEK_ROOM_DECK in legal_types

            # Mapear action_id a Action
            action = self._pick_action_for_type(legal, requested_action_type, actor)
            if action is not None:
                action_selection_source = "DIRECT_MATCH"
            if requested_action_type is not None and requested_action_type not in {a.type for a in legal}:
                illegal_action_intent = True

            # Fallback guiado
            if action is None:
                action = self._pick_guided_fallback_action(self.state, legal, actor)
                if action is not None:
                    action_selection_source = "GUIDED_FALLBACK"
                    fallback_substitution_reason = "masked_out" if masked_out_action else "no_direct_type"

            # Fallback determinístico (evita ruido estocástico extra)
            if action is None:
                action = self._select_deterministic_fallback_action(legal, actor, ActionType.END_TURN)
                action_selection_source = "DETERMINISTIC_FALLBACK" if legal else "DEFAULT_END_TURN"
                fallback_substitution_reason = "masked_out" if masked_out_action else "no_direct_type"

        if requested_action_legal is None and actor != "KING":
            requested_action_legal = False

        fallback_substitution = (
            actor != "KING"
            and (requested_action_type is None or requested_action_type != action.type)
        )

        self.last_action_debug = {
            "actor": actor,
            "requested_action_id": int(action_id),
            "requested_action_type": requested_action_label,
            "requested_action_legal": requested_action_legal,
            "requested_action_out_of_range": requested_action_out_of_range,
            "masked_out_action": masked_out_action,
            "executed_action_type": action.type.value,
            "requested_action_matched_executed": requested_action_type == action.type if requested_action_type is not None else False,
            "action_selection_source": action_selection_source,
            "fallback_substitution": fallback_substitution,
            "fallback_substitution_reason": fallback_substitution_reason,
            "peek_available": peek_available,
            "illegal_action_intent": illegal_action_intent,
        }

        prev_state = self.state
        observations = self._extract_observations(prev_state, action, actor)

        # Ejecutar transición
        next_state = step(prev_state, action, self.rng, self.cfg)

        # Calcular reward
        reward = self._calculate_reward(
            prev_state,
            next_state,
            action,
            actor,
            legal,
            observations,
            illegal_action_intent=illegal_action_intent,
        )
        
        self.state = next_state
        
        # Terminación
        terminated = self.state.game_over
        truncated = self.step_count >= self.max_steps

        # Penalización de TIMEOUT: si se corta sin game_over, señal negativa
        # para que el agente aprenda a TERMINAR (llegar a WIN/LOSE) en vez de stall.
        if truncated and not terminated:
            reward += self.penalty_timeout
        
        obs = self._get_obs()
        info = self._get_info()
        
        if self.render_mode == "human":
            self.render()
        
        return obs, reward, terminated, truncated, info
    
    def _calculate_reward(
        self,
        prev_state,
        next_state,
        action: Action,
        actor: str,
        legal_actions: List[Action],
        observations: List[Dict[str, Any]],
        illegal_action_intent: bool = False,
    ) -> float:
        """Calcula reward para RL."""
        prev_keys = sum(p.keys for p in prev_state.players.values())
        prev_sanity = sum(p.sanity for p in prev_state.players.values())
        curr_keys = sum(p.keys for p in next_state.players.values())
        curr_sanity = sum(p.sanity for p in next_state.players.values())
        keys_needed = self.cfg.KEYS_TO_WIN
        phase2_active = prev_keys >= keys_needed or curr_keys >= keys_needed

        if next_state.game_over:
            reward = self.reward_win if next_state.outcome == "WIN" else self.reward_lose
        else:
            reward = 0.0

            # Ganar llaves (siempre activo)
            if curr_keys > prev_keys:
                reward += self.reward_key * (curr_keys - prev_keys)

            # Perder llaves (sacrificio o daño)
            if curr_keys < prev_keys:
                reward += self.reward_key_lost * (prev_keys - curr_keys)

            # Pérdida de sanity
            if curr_sanity < prev_sanity:
                reward += self.reward_sanity_loss * (prev_sanity - curr_sanity)

            # --- SHAPING DENSO SIEMPRE ACTIVO (línea [092]) ---
            # Premia acercar al equipo al Umbral y penaliza alejarse,
            # independiente de phase2, para dar gradiente de "victoria" en cada paso.
            prev_team_umbral_dist = self._team_umbral_distance(prev_state)
            curr_team_umbral_dist = self._team_umbral_distance(next_state)
            if curr_team_umbral_dist < prev_team_umbral_dist:
                reward += self.reward_phase2_umbral_progress * (prev_team_umbral_dist - curr_team_umbral_dist)
            elif curr_team_umbral_dist > prev_team_umbral_dist:
                reward += self.penalty_phase2_umbral_regress * (curr_team_umbral_dist - prev_team_umbral_dist)

            prev_near_umbral = sum(
                1 for player in prev_state.players.values() if self._distance_to_umbral(prev_state, player.room) <= 1
            )
            curr_near_umbral = sum(
                1 for player in next_state.players.values() if self._distance_to_umbral(next_state, player.room) <= 1
            )
            if curr_near_umbral > prev_near_umbral:
                reward += self.reward_phase2_sync_step * (curr_near_umbral - prev_near_umbral)

            prev_critical = sum(
                1
                for player in prev_state.players.values()
                if player.sanity <= self.critical_sanity_threshold
            )
            curr_critical = sum(
                1
                for player in next_state.players.values()
                if player.sanity <= self.critical_sanity_threshold
            )
            if curr_critical > prev_critical:
                reward += self.penalty_critical_sanity * (curr_critical - prev_critical)

            # Bonus de victoria inminente: todos con llaves necesarias Y en el Umbral.
            # Siempre activo (no gated por phase2) para reforzar la meta final.
            if curr_keys >= keys_needed and all(
                self._distance_to_umbral(next_state, player.room) == 0
                for player in next_state.players.values()
            ):
                reward += self.reward_phase2_sync_all

        if illegal_action_intent and actor in prev_state.players:
            reward += self.penalty_illegal_intent

        # Penalizar búsqueda en mazo vacío
        if action.type == ActionType.SEARCH and actor in prev_state.players:
            from engine.boxes import active_deck_for_room
            p_room = prev_state.players[actor].room
            deck = active_deck_for_room(prev_state, p_room)
            if deck is None or deck.remaining() == 0:
                reward += self.penalty_empty_search

        info_reward = self._register_observations(observations, actor, prev_state.round)
        info_reward += self._compute_info_usage_reward(
            prev_state=prev_state,
            action=action,
            actor=actor,
            legal_actions=legal_actions,
            prev_keys=prev_keys,
            curr_keys=curr_keys,
        )
        if phase2_active:
            info_reward *= self.phase2_info_scale
        info_reward = max(-0.25, min(0.5, info_reward))
        reward += info_reward

        return reward
    
    def render(self):
        """Renderiza el estado actual."""
        if self.render_mode == "human" or self.render_mode == "ansi":
            output = [
                f"\n--- Step {self.step_count} ---",
                f"Round {self.state.round}, Phase: {self.state.phase}",
                f"King Floor: {self.state.king_floor}",
            ]
            for pid, p in self.state.players.items():
                output.append(f"  {pid}: Room={p.room}, Sanity={p.sanity}, Keys={p.keys}")
            
            if self.state.game_over:
                output.append(f"GAME OVER: {self.state.outcome}")
            
            print("\n".join(output))
            
            if self.render_mode == "ansi":
                return "\n".join(output)
    
    def close(self):
        """Limpieza."""
        pass


# Registrar entorno si gymnasium está disponible
try:
    from gymnasium.envs.registration import register
    register(
        id="Carcosa-v0",
        entry_point="train.carcosa_env:CarcosaEnv",
        max_episode_steps=500,
    )
except Exception:
    pass  # Ya registrado o error de import


if __name__ == "__main__":
    # Test del entorno
    print("Testing CarcosaEnv...")
    
    env = CarcosaEnv(seed=42, render_mode="human")
    obs, info = env.reset()
    
    print(f"\nObservation shape: {obs.shape}")
    print(f"Observation: {obs}")
    print(f"Legal actions: {info['legal_actions']}")
    
    # Ejecutar algunos pasos random
    total_reward = 0
    for i in range(20):
        # Elegir acción random de las legales
        legal_mask = info["legal_actions"]
        legal_ids = np.where(legal_mask > 0)[0]
        action = np.random.choice(legal_ids)
        
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        
        if terminated or truncated:
            print(f"\nEpisode ended: {info['outcome']}, Total reward: {total_reward}")
            break
    
    env.close()
    print("\nTest completado!")

from __future__ import annotations
from typing import Dict, List, Any, Optional
import json
import random
from pathlib import Path
from datetime import datetime
import argparse

from engine.actions import Action, ActionType
from engine.config import Config
from engine.rng import RNG
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId, CardId
from engine.board import corridor_id, room_id, is_corridor
from engine.transition import step
from engine.legality import get_legal_actions
from sim.policies import get_king_policy, get_player_policy
from sim.metrics import transition_record, write_jsonl


SPECIAL_ACTION_TYPES = {
    ActionType.USE_MOTEMEY_BUY_START,
    ActionType.USE_MOTEMEY_BUY_CHOOSE,
    ActionType.USE_MOTEMEY_SELL,
    ActionType.USE_TABERNA_ROOMS,
    ActionType.USE_ARMORY_TAKE,
    ActionType.USE_ARMORY_DROP,
    ActionType.USE_YELLOW_DOORS,
    ActionType.USE_CAPILLA,
    ActionType.USE_SALON_BELLEZA,
    ActionType.USE_CAMARA_LETAL_RITUAL,
}

OBJECT_ACTION_TYPES = {
    ActionType.USE_BLUNT,
    ActionType.USE_PORTABLE_STAIRS,
    ActionType.USE_ATTACH_TALE,
    ActionType.USE_READ_YELLOW_SIGN,
}


def _status_counts(state: GameState) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for p in state.players.values():
        for st in p.statuses:
            counts[st.status_id] = counts.get(st.status_id, 0) + 1
    return counts


def _bump(counter: Dict[str, int], key: str, amount: int = 1) -> None:
    counter[key] = counter.get(key, 0) + amount


def _setup_special_rooms(rng: RNG) -> Dict[str, Dict[int, int]]:
    """
    P1 - FASE 1.5.1: Sortea 3 habitaciones especiales y las asigna a ubicaciones.

    CORRECCIÓN A: Reglas físicas correctas
    - Sortear 3 tipos distintos del pool
    - Asignar 1 tipo a 1 piso (F1, F2, F3)
    - Usar D4 para determinar R1-R4

    Returns:
        Dict mapeando special_room_type -> {floor: room_number}
        Ejemplo: {"CAMARA_LETAL": {1: 2}, "MOTEMEY": {2: 3}, "PUERTAS": {3: 1}}
    """
    available_special_rooms = [
        "MOTEMEY",      # B2
        "CAMARA_LETAL", # B3
        "PUERTAS",      # B4 (Puertas Amarillas)
        "PEEK",         # B5 (Mirador / Taberna)
        "ARMERY"        # B6 (Armería)
    ]

    # Sortear 3 habitaciones especiales
    selected_special_rooms = rng.sample(available_special_rooms, 3)

    # Shuffle para asignación aleatoria a pisos
    rng.shuffle(selected_special_rooms)

    # Asignar ubicaciones: 1 tipo por piso
    special_room_locations = {}

    for i, floor_num in enumerate([1, 2, 3]):
        special_type = selected_special_rooms[i]

        # Tirar D4: 1→R1, 2→R2, 3→R3, 4→R4
        d4_roll = rng.randint(1, 4)

        # Cada tipo solo aparece en UN piso
        special_room_locations[special_type] = {
            floor_num: d4_roll
        }

    return special_room_locations


def make_smoke_state(seed: int = 1, cfg: Optional[Config] = None) -> GameState:
    cfg = cfg or Config()
    rng = RNG(seed)

    # 1. Start with initial players (setup requires GameState which requires players/rooms)
    # CANON 4-Player Roles Config (FIXED por defecto)
    from engine.roles import get_sanity_max, get_starting_items, draw_roles

    p_ids = ["P1", "P2", "P3", "P4"]
    role_mode = getattr(cfg, "ROLE_DRAW_MODE", "FIXED") or "FIXED"
    role_mode = str(role_mode).upper()
    role_pool = list(getattr(cfg, "ROLE_POOL", []) or [])

    if role_mode == "FIXED":
        # P1: SCOUT (Move +1)
        # P2: HIGH_ROLLER (Events)
        # P3: TANK (Capacity/Stam)
        # P4: BRAWLER (Combat)
        p_defs = [
            ("P1", "SCOUT"),
            ("P2", "HIGH_ROLLER"),
            ("P3", "TANK"),
            ("P4", "BRAWLER"),
        ]
        roles_assigned = {pid: role for pid, role in p_defs}
    else:
        roles_assigned = draw_roles(p_ids, role_mode, role_pool, rng)
        p_defs = [(pid, roles_assigned[pid]) for pid in p_ids]
    
    players = {}
    corridors = [corridor_id(1), corridor_id(2), corridor_id(1), corridor_id(2)] # Split start
    
    for i, (pid_str, role) in enumerate(p_defs):
        pid = PlayerId(pid_str)
        s_max = get_sanity_max(role)
        items = get_starting_items(role)
        players[pid] = PlayerState(
            player_id=pid,
            sanity=s_max,
            room=corridors[i],
            role_id=role,
            sanity_max=s_max,
            objects=items,
            keys=0
        )

    # 2. Create GameState with empty rooms initially (but valid dict)
    rooms: Dict[RoomId, RoomState] = {}
    state = GameState(round=1, players=players, rooms=rooms, seed=seed, king_floor=1)
    state.roles_assigned = roles_assigned

    # 3. Setup Canonical Special Rooms & Motemey Deck
    # This populates state.rooms (via special rooms) and state.motemey_deck
    from engine.setup import setup_special_rooms, setup_motemey_deck
    setup_special_rooms(state, rng)
    setup_motemey_deck(state, rng)

    # 4. Fill standard rooms (Corridors + R1-R4) respecting existing special rooms
    room_ids: List[RoomId] = []
    
    for f in (1, 2, 3):
        # Corridor setup
        c_id = corridor_id(f)
        if c_id not in rooms:
             rooms[c_id] = RoomState(room_id=c_id, deck=DeckState(cards=[]))
        
        # Room setup
        for r in (1, 2, 3, 4):
            rid = room_id(f, r)
            room_ids.append(rid)
            
            # If room not created by setup_special_rooms, create empty standard room
            if rid not in rooms:
                rooms[rid] = RoomState(
                    room_id=rid,
                    deck=DeckState(cards=[]),
                    special_card_id=None,
                    special_revealed=False,
                    special_destroyed=False,
                    special_activation_count=0
                )

    # 5. Populate Decks CANONICALLY
    # ===============================
    # Use the centralized setup logic from engine.setup
    from engine.setup import setup_canonical_deck
    setup_canonical_deck(state, rng)

    # Flag setup handled by setup_special_rooms
    state.flags["CAMARA_LETAL_PRESENT"] = "CAMARA_LETAL" in state.flags.get("SPECIAL_ROOMS_SELECTED", [])

    return state



def run_episode(
    max_steps: int = 2000,
    seed: int = 1,
    out_path: Optional[str] = None,
    cfg: Optional[Config] = None,
    policy_name: str = "GOAL",
) -> GameState:
    cfg = cfg or Config()
    rng = RNG(seed)
    state = make_smoke_state(seed=seed, cfg=cfg)

    # Policy Selection
    from sim.policies import (
        GoalDirectedPlayerPolicy, 
        CowardPolicy, 
        BerserkerPolicy, 
        SpeedrunnerPolicy, 
        RandomPolicy
    )
    from sim.mcts_policy import MCTSPlayerPolicy
    
    if policy_name == "MCTS":
        # Extraer config de argumentos si existen, por ahora defaults
        # Hack: Parse args generically or expect caller to modify cfg?
        # For P0 CLI args are parsed in main(), but run_episode receives only signature args.
        # We'll rely on MCTSPlayerPolicy defaults or update cfg if we want to pass them.
        # Better: Pass params via kwargs or extend Config. 
        # Since I can't easily change run_episode signature without breaking other calls (if any),
        # I will assume defaults for now or pass via cfg if I had added them to Config.
        # BUT `main` has `args`. `run_episode` doesn't take kwargs.
        # I'll rely on defaults for P0 or simple hack:
        ppol = MCTSPlayerPolicy(cfg, rollouts=getattr(cfg, "MCTS_ROLLOUTS", 100)) 
    else:
        ppol = get_player_policy(policy_name, cfg)

    kpol = get_king_policy(getattr(cfg, "KING_POLICY", "RANDOM"), cfg)

    records: List[Dict[str, Any]] = []
    step_idx = 0
    episode_stats: Dict[str, Dict[str, int]] = {
        "special_actions": {},
        "object_actions": {},
        "status_gained": {},
        "status_cleared": {},
        "sacrifice": {
            "opportunities": 0,
            "sacrifice_available": 0,
            "sacrifice": 0,
            "accept": 0,
            "sacrifice_with_keys": 0,
            "accept_with_keys": 0,
            "sacrifice_mode": {},
            "keys_destroyed_by": {},
            "keys_destroyed_sources": {},
        },
    }
    prev_status_counts = _status_counts(state)

    while step_idx < max_steps and not state.game_over:
        # Check for Sacrifice Interrupt
        pending_sacrifice_pid = state.flags.get("PENDING_SACRIFICE_CHECK")
        if isinstance(pending_sacrifice_pid, list):
            pending_sacrifice_pid = pending_sacrifice_pid[0] if pending_sacrifice_pid else None
        
        if pending_sacrifice_pid:
            episode_stats["sacrifice"]["opportunities"] += 1
            legal_for_pending = get_legal_actions(state, str(pending_sacrifice_pid))
            if any(a.type == ActionType.SACRIFICE for a in legal_for_pending):
                episode_stats["sacrifice"]["sacrifice_available"] += 1
            # print(f"DEBUG RUNNER: Interrupt active for {pending_sacrifice_pid}")
            # INTERRUPT: Only the pending player can act (Sacrifice/Accept)
            actor = str(pending_sacrifice_pid)
            # Use player policy for this decision
            action = ppol.choose(state, rng) 
            # Note: Policies must be robust enough to pick SACRIFICE/ACCEPT if available.
        elif state.phase == "PLAYER":
            if "PENDING_SACRIFICE_CHECK" in state.flags:
                print(f"DEBUG RUNNER WARN: Flag exists but value is '{state.flags['PENDING_SACRIFICE_CHECK']}'")
            actor = str(state.turn_order[state.turn_pos])
            action = ppol.choose(state, rng)
        else:
            actor = "KING"
            action = kpol.choose(state, rng)
            
        if action is None:
            # Fallback if policy fails (should be rare)
            if actor == "KING":
                 action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
            else:
                 action = Action(actor=actor, type=ActionType.END_TURN, data={})

        # Safety: si la policy devuelve una acción ilegal, escoger una legal
        legal = get_legal_actions(state, actor)
        if action not in legal:
            if legal:
                action = rng.choice(legal)
            else:
                # Sin acciones legales: forzar END_TURN o KING_ENDROUND
                if actor == "KING":
                    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
                else:
                    action = Action(actor=actor, type=ActionType.END_TURN, data={})

        if actor in state.players:
            pid_actor = PlayerId(actor)
            if action.type == ActionType.SACRIFICE:
                episode_stats["sacrifice"]["sacrifice"] += 1
                if state.players[pid_actor].keys > 0:
                    episode_stats["sacrifice"]["sacrifice_with_keys"] += 1
                mode = action.data.get("mode", "UNKNOWN")
                _bump(episode_stats["sacrifice"]["sacrifice_mode"], str(mode))
            elif action.type == ActionType.ACCEPT_SACRIFICE:
                episode_stats["sacrifice"]["accept"] += 1
                if state.players[pid_actor].keys > 0:
                    episode_stats["sacrifice"]["accept_with_keys"] += 1

        next_state = step(state, action, rng, cfg)

        # Track d6 if KING_ENDROUND
        action_dict = {"actor": actor, "type": action.type.value, "data": action.data}
        if action.type.value == "KING_ENDROUND" and rng.last_king_d6 is not None:
            action_dict["d6"] = rng.last_king_d6

        # Episode metrics: specials/objects/status transitions
        if action.type in SPECIAL_ACTION_TYPES:
            _bump(episode_stats["special_actions"], action.type.value)
        if action.type in OBJECT_ACTION_TYPES:
            _bump(episode_stats["object_actions"], action.type.value)

        keys_delta = next_state.keys_destroyed - state.keys_destroyed
        if keys_delta > 0:
            who = actor if actor in state.players else "UNKNOWN"
            _bump(episode_stats["sacrifice"]["keys_destroyed_by"], str(who), keys_delta)
            source = state.last_sanity_loss_event or "UNKNOWN"
            _bump(episode_stats["sacrifice"]["keys_destroyed_sources"], str(source), keys_delta)

        next_status_counts = _status_counts(next_state)
        for st, count in next_status_counts.items():
            prev = prev_status_counts.get(st, 0)
            if count > prev:
                _bump(episode_stats["status_gained"], st, count - prev)
        for st, count in prev_status_counts.items():
            nxt = next_status_counts.get(st, 0)
            if count > nxt:
                _bump(episode_stats["status_cleared"], st, count - nxt)
        prev_status_counts = next_status_counts

        # Add policy info to record for analysis
        records.append(
            transition_record(
                state=state,
                action=action_dict,
                next_state=next_state,
                cfg=cfg,
                step_idx=step_idx,
            )
        )
        # Inject Policy Name into record (hacky but useful)
        records[-1]["policy"] = policy_name

        state = next_state
        step_idx += 1

    if out_path is None:
        Path("runs").mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = f"runs/run_{policy_name}_seed{seed}_{ts}.jsonl"

    write_jsonl(out_path, records)
    role_draw_mode = getattr(cfg, "ROLE_DRAW_MODE", "FIXED")
    role_pool = list(getattr(cfg, "ROLE_POOL", []) or [])
    roles_assigned = state.roles_assigned or {str(pid): p.role_id for pid, p in state.players.items()}

    summary = {
        "policy": policy_name,
        "seed": seed,
        "steps": step_idx,
        "round": state.round,
        "game_over": state.game_over,
        "outcome": state.outcome,
        "keys_destroyed_total": state.keys_destroyed,
        "keys_in_hand": sum(p.keys for p in state.players.values()),
        "role_draw_mode": role_draw_mode,
        "role_pool": role_pool,
        "roles_assigned": roles_assigned,
        **episode_stats,
    }
    summary_path = out_path.replace(".jsonl", "_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Saved run to: {out_path}")
    print(f"Saved summary to: {summary_path}")
    print("Finished:", state.game_over, state.outcome, "round", state.round, "steps", step_idx)
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-steps", type=int, default=2000)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--policy", type=str, default="GOAL", 
                    choices=["GOAL", "HABITANTEDECARCOSA", "COWARD", "BERSERKER", "SPEEDRUNNER", "RANDOM", "MCTS"],
                    help="Player policy to use")
    
    # MCTS Args
    ap.add_argument("--mcts-rollouts", type=int, default=100)
    # Role draw args
    ap.add_argument("--role-draw-mode", type=str, default=None,
                    choices=["FIXED", "RANDOM_UNIQUE", "RANDOM_WITH_REPLACEMENT"],
                    help="Role draw mode for player setup")
    ap.add_argument("--role-pool", type=str, default=None,
                    help="Comma-separated role ids for draw pool (e.g., HEALER,TANK,SCOUT)")
    
    args = ap.parse_args()
    
    role_pool = None
    if args.role_pool:
        role_pool = [r.strip() for r in args.role_pool.split(",") if r.strip()]

    cfg_kwargs = {"MCTS_ROLLOUTS": args.mcts_rollouts}
    if args.role_draw_mode:
        cfg_kwargs["ROLE_DRAW_MODE"] = args.role_draw_mode
    if role_pool is not None:
        cfg_kwargs["ROLE_POOL"] = tuple(role_pool)

    # Inject params into Config via constructor
    cfg = Config(**cfg_kwargs)
    
    run_episode(
        max_steps=args.max_steps, 
        seed=args.seed, 
        out_path=args.out,
        policy_name=args.policy,
        cfg=cfg
    )


if __name__ == "__main__":
    main()

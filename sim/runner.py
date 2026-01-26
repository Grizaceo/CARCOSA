from __future__ import annotations
from typing import Dict, List, Any, Optional
import json
import random
from pathlib import Path
from datetime import datetime
import argparse

from engine.actions import ActionType
from engine.config import Config
from engine.rng import RNG
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId, CardId
from engine.board import corridor_id, room_id, is_corridor
from engine.transition import step
from engine.legality import get_legal_actions
from sim.policies import GoalDirectedPlayerPolicy, HeuristicKingPolicy
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
    # CANON 4-Player Roles Config
    # P1: SCOUT (Move +1)
    # P2: HIGH_ROLLER (Events)
    # P3: TANK (Capacity/Stam)
    # P4: BRAWLER (Combat)
    from engine.roles import get_sanity_max, get_starting_items
    
    p_defs = [
        ("P1", "SCOUT"),
        ("P2", "HIGH_ROLLER"),
        ("P3", "TANK"),
        ("P4", "BRAWLER")
    ]
    
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
    # Gran Mazo (104 cartas aprox) repartido entre 12 habitaciones
    # ------------------------------------------------------------
    cards: List[CardId] = []
    
    # --- EVENTOS (48) ---
    cards.extend([CardId("EVENT:FURIA_AMARILLO")] * 2)
    cards.extend([CardId("EVENT:HAY_CADAVER")] * 5)
    cards.extend([CardId("EVENT:ESPEJO_AMARILLO")] * 5)
    cards.extend([CardId("EVENT:COMIDA_SERVIDA")] * 5)
    cards.extend([CardId("EVENT:DIVAN_AMARILLO")] * 6)
    cards.extend([CardId("EVENT:CAMBIA_CARAS")] * 5)
    cards.extend([CardId("EVENT:GOLPE_AMARILLO")] * 5)
    cards.extend([CardId("EVENT:ASCENSOR")] * 6)
    cards.extend([CardId("EVENT:TRAMPILLA")] * 5)
    cards.extend([CardId("EVENT:EVENTO_MOTEMEY")] * 4)

    # --- ESTADOS EN MAZO (14) ---
    cards.extend([CardId("STATE:ENVENENADO")] * 2)
    cards.extend([CardId("STATE:SANIDAD")] * 2)
    cards.extend([CardId("STATE:MALDITO")] * 5)
    cards.extend([CardId("STATE:PARANOIA")] * 5)

    # --- OBJETOS (24) ---
    cards.extend([CardId("OBJECT:COMPASS")] * 8)
    cards.extend([CardId("OBJECT:VIAL")] * 8)
    cards.extend([CardId("OBJECT:BLUNT")] * 8)

    # --- MONSTRUOS (7) ---
    cards.extend([CardId("MONSTER:TUE_TUE")] * 3)
    cards.extend([CardId("MONSTER:REINA_HELADA")] * 1)
    cards.extend([CardId("MONSTER:DUENDE")] * 1)
    cards.extend([CardId("MONSTER:VIEJO_DEL_SACO")] * 1)
    cards.extend([CardId("MONSTER:ARAÑA")] * 1)

    # --- ESPECIALES / TESOROS / LLAVES ---
    cards.extend([CardId("KEY")] * cfg.KEYS_TOTAL) # 5 keys
    cards.append(CardId("OBJECT:BOOK_CHAMBERS"))
    
    # 3 Cuentos (random o fijos, usaremos 3 distintos por ahora)
    cards.append(CardId("OBJECT:TALE_REPAIRER"))
    cards.append(CardId("OBJECT:TALE_MASK"))
    cards.append(CardId("OBJECT:TALE_DRAGON"))
    
    # Tesoros en mazo regular
    cards.append(CardId("OBJECT:TREASURE_RING")) # Llavero
    cards.append(CardId("OBJECT:RING"))          # Anillo

    # Mezclar el Gran Mazo
    rnd = random.Random(seed)
    rnd.shuffle(cards)

    # Repartir ciegamente entre R1-R4 de F1-F3 (12 rooms)
    # Las llaves y monstruos quedan donde caigan
    room_ids_target = [r for r in room_ids if not is_corridor(r)]
    
    # Round-robin distribution
    idx = 0
    while idx < len(cards):
        for rid in room_ids_target:
            if idx >= len(cards):
                break
            rooms[rid].deck.cards.append(cards[idx])
            idx += 1
            
    # Estado final de mazos: invertimos para que append sea bottom y [0] sea top?
    # No, DeckState no tiene logica compleja, top apunta a indice.
    # Pero para eficiencia de pop(), solemos usar pop() del final?
    # El sistema actual usa DeckState.top avanzando.
    # Así que la lista es [Carta 1, Carta 2, ...]. Carta 1 está en index 0.
    # Reveal usa cards[top].
    # Así que el orden de append es el orden de robo. Shuffle ya randomizó.
    # Todo OK.

    # Flag setup handled by setup_special_rooms
    state.flags["CAMARA_LETAL_PRESENT"] = "CAMARA_LETAL" in state.flags.get("SPECIAL_ROOMS_SELECTED", [])

    return state



def run_episode(
    max_steps: int = 1200,
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
    
    if policy_name == "COWARD":
        ppol = CowardPolicy(cfg)
    elif policy_name == "BERSERKER":
        ppol = BerserkerPolicy(cfg)
    elif policy_name == "SPEEDRUNNER":
        ppol = SpeedrunnerPolicy(cfg)
    elif policy_name == "RANDOM":
        ppol = RandomPolicy()
    elif policy_name == "MCTS":
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
        ppol = GoalDirectedPlayerPolicy(cfg)

    kpol = HeuristicKingPolicy(cfg)

    records: List[Dict[str, Any]] = []
    step_idx = 0
    episode_stats: Dict[str, Dict[str, int]] = {
        "special_actions": {},
        "object_actions": {},
        "status_gained": {},
        "status_cleared": {},
    }
    prev_status_counts = _status_counts(state)

    while step_idx < max_steps and not state.game_over:
        # Check for Sacrifice Interrupt
        pending_sacrifice_pid = state.flags.get("PENDING_SACRIFICE_CHECK")
        
        if pending_sacrifice_pid:
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
            from engine.actions import Action, ActionType
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
                from engine.actions import Action, ActionType
                if actor == "KING":
                    action = Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
                else:
                    action = Action(actor=actor, type=ActionType.END_TURN, data={})

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
    summary = {
        "policy": policy_name,
        "seed": seed,
        "steps": step_idx,
        "round": state.round,
        "game_over": state.game_over,
        "outcome": state.outcome,
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
    ap.add_argument("--max-steps", type=int, default=1200)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--policy", type=str, default="GOAL", 
                    choices=["GOAL", "COWARD", "BERSERKER", "SPEEDRUNNER", "RANDOM", "MCTS"],
                    help="Player policy to use")
    
    # MCTS Args
    ap.add_argument("--mcts-rollouts", type=int, default=100)
    
    args = ap.parse_args()
    
    # Inject MCTS params into Config via constructor
    cfg = Config(
        MCTS_ROLLOUTS=args.mcts_rollouts
    )
    
    run_episode(
        max_steps=args.max_steps, 
        seed=args.seed, 
        out_path=args.out,
        policy_name=args.policy,
        cfg=cfg
    )


if __name__ == "__main__":
    main()

from __future__ import annotations
from typing import Dict, List, Any, Optional
import random
from pathlib import Path
from datetime import datetime
import argparse

from engine.config import Config
from engine.rng import RNG
from engine.state import GameState, PlayerState, RoomState, DeckState
from engine.types import PlayerId, RoomId, CardId
from engine.board import corridor_id, room_id
from engine.transition import step
from sim.policies import GoalDirectedPlayerPolicy, HeuristicKingPolicy
from sim.metrics import transition_record, write_jsonl


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
    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=corridor_id(1)),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=3, room=corridor_id(2)),
    }

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

    # 5. Populate Decks (Keys first, then fillers)
    # Pool global de llaves: el juego físico tiene 6 cartas de Llave.
    key_pool = [CardId("KEY") for _ in range(cfg.KEYS_TOTAL)]

    fillers = [
        CardId("EVENT:X"),
        CardId("EVENT:Y"),
        CardId("STATE:STUN"),
        CardId("STATE:CURSE"),
        CardId("MONSTER:SPIDER"),
        CardId("MONSTER:WORM"),
    ]

    rnd = random.Random(seed)
    rnd.shuffle(room_ids)

    # Distribución equitativa de llaves
    keys_per_room = [0] * len(room_ids)
    for i in range(cfg.KEYS_TOTAL):
        keys_per_room[i % len(room_ids)] += 1
    
    for rid, num_keys in zip(room_ids, keys_per_room):
        # Llaves al fondo (primero en lista = fondo si pop(0) o top si pop()? 
        # Usually list append adds to end. top is presumably index 0 or len-1?
        # DeckState uses 'top' index. If top starts at 0, then index 0 is top.
        # So appending to list puts items at BOTTOM.
        # But here we want keys accessible? 
        # Original code: appended keys first. 
        # If 'top' is 0, then deck[0] is top.
        # So appending keys first -> keys are at top (index 0, 1...). 
        # The prompt says "colocar llaves primero (accesibles)".
        for _ in range(num_keys):
            rooms[rid].deck.cards.append(CardId("KEY"))

    # Rellenar con fillers
    for rid in room_ids:
        deck = rooms[rid].deck.cards
        target = 6
        while len(deck) < target:
            deck.append(rnd.choice(fillers))
        
        # Mezclar SOLO los fillers si hay llaves arriba (para no perder accesibilidad)
        # Ojo: si hay llaves en [0..k-1], y fillers en [k..N], y shuffleamos [k..N], 
        # las llaves quedan arriba.
        if len(deck) > cfg.KEYS_TOTAL:
             keys_count = sum(1 for c in deck if str(c) == "KEY")
             # Mezclar slice [keys_count:]
             sublist = deck[keys_count:]
             rng.shuffle(sublist)
             # Recomponer
             deck[:] = deck[:keys_count] + sublist
        
        rooms[rid].deck = DeckState(cards=deck)

    # Flag setup handled by setup_special_rooms
    state.flags["CAMARA_LETAL_PRESENT"] = "CAMARA_LETAL" in state.flags.get("SPECIAL_ROOMS_SELECTED", [])

    return state



def run_episode(
    max_steps: int = 400,
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
    
    if policy_name == "COWARD":
        ppol = CowardPolicy(cfg)
    elif policy_name == "BERSERKER":
        ppol = BerserkerPolicy(cfg)
    elif policy_name == "SPEEDRUNNER":
        ppol = SpeedrunnerPolicy(cfg)
    elif policy_name == "RANDOM":
        ppol = RandomPolicy()
    else:
        ppol = GoalDirectedPlayerPolicy(cfg)

    kpol = HeuristicKingPolicy(cfg)

    records: List[Dict[str, Any]] = []
    step_idx = 0

    while step_idx < max_steps and not state.game_over:
        # Check for Sacrifice Interrupt
        pending_sacrifice_pid = state.flags.get("PENDING_SACRIFICE_CHECK")
        
        if pending_sacrifice_pid:
            # INTERRUPT: Only the pending player can act (Sacrifice/Accept)
            actor = str(pending_sacrifice_pid)
            # Use player policy for this decision
            action = ppol.choose(state, rng) 
            # Note: Policies must be robust enough to pick SACRIFICE/ACCEPT if available.
        elif state.phase == "PLAYER":
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

        next_state = step(state, action, rng, cfg)

        # Track d6 if KING_ENDROUND
        action_dict = {"actor": actor, "type": action.type.value, "data": action.data}
        if action.type.value == "KING_ENDROUND" and rng.last_king_d6 is not None:
            action_dict["d6"] = rng.last_king_d6

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
    print(f"Saved run to: {out_path}")
    print("Finished:", state.game_over, state.outcome, "round", state.round, "steps", step_idx)
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-steps", type=int, default=400)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--policy", type=str, default="GOAL", 
                    choices=["GOAL", "COWARD", "BERSERKER", "SPEEDRUNNER", "RANDOM"],
                    help="Player policy to use")
    args = ap.parse_args()
    
    run_episode(
        max_steps=args.max_steps, 
        seed=args.seed, 
        out_path=args.out,
        policy_name=args.policy
    )


if __name__ == "__main__":
    main()

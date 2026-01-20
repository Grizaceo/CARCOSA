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

    Returns:
        Dict mapeando special_room_type -> {floor: room_number}
        Ejemplo: {"CAMARA_LETAL": {1: 2, 2: 3, 3: 1}, ...}
    """
    available_special_rooms = [
        "MOTEMEY",      # B2
        "CAMARA_LETAL", # B3
        "PUERTAS",      # B4 (Puertas Amarillas)
        "PEEK",         # B5 (Mirador)
        "ARMERY"        # B6 (Armería)
    ]

    # Sortear 3 habitaciones especiales
    selected_special_rooms = rng.sample(available_special_rooms, 3)

    # Asignar ubicaciones con D4 para cada piso
    special_room_locations = {}

    for special_room in selected_special_rooms:
        # Tirar D4 para cada piso (F1, F2, F3)
        f1_roll = rng.randint(1, 4)  # D4 para piso 1
        f2_roll = rng.randint(1, 4)  # D4 para piso 2
        f3_roll = rng.randint(1, 4)  # D4 para piso 3

        # Mapeo: 1→R1, 2→R2, 3→R3, 4→R4
        special_room_locations[special_room] = {
            1: f1_roll,
            2: f2_roll,
            3: f3_roll
        }

    return special_room_locations


def make_smoke_state(seed: int = 1, cfg: Optional[Config] = None) -> GameState:
    cfg = cfg or Config()
    rng = RNG(seed)

    # P1: Sortear habitaciones especiales
    special_room_locations = _setup_special_rooms(rng)

    rooms: Dict[RoomId, RoomState] = {}
    room_ids: List[RoomId] = []

    for f in (1, 2, 3):
        rooms[corridor_id(f)] = RoomState(room_id=corridor_id(f), deck=DeckState(cards=[]))
        for r in (1, 2, 3, 4):
            rid = room_id(f, r)
            room_ids.append(rid)

            # P1: Verificar si esta ubicación tiene una habitación especial
            special_card_id = None
            for special_type, locations in special_room_locations.items():
                if locations[f] == r:
                    special_card_id = special_type
                    break

            # Crear habitación con datos especiales si corresponde
            rooms[rid] = RoomState(
                room_id=rid,
                deck=DeckState(cards=[]),
                special_card_id=special_card_id,
                special_revealed=False,
                special_destroyed=False,
                special_activation_count=0
            )

    # Pool global de llaves: el juego físico tiene 6 cartas de Llave.:contentReference[oaicite:2]{index=2}
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

    # Distribución mejorada: colocar llaves primero (accesibles) y luego rellenar
    # Distribuir llaves de forma que cada habitación tenga oportunidad
    keys_per_room = [0] * len(room_ids)
    for i in range(cfg.KEYS_TOTAL):
        keys_per_room[i % len(room_ids)] += 1
    
    for rid, num_keys in zip(room_ids, keys_per_room):
        # Agregar llaves PRIMERO (accesibles al inicio del mazo)
        for _ in range(num_keys):
            rooms[rid].deck.cards.append(CardId("KEY"))

    # Luego rellenar con otros tipos de cartas
    for rid in room_ids:
        deck = rooms[rid].deck.cards
        target = 6
        while len(deck) < target:
            deck.append(rnd.choice(fillers))
        # Mezclar SOLO los rellenos, no las llaves
        # Para simplificar: mezclar sin tocar primeras N posiciones
        if len(deck) > cfg.KEYS_TOTAL:
            # Solo mezclar los fillers (después de las keys)
            keys_count = sum(1 for c in deck if str(c) == "KEY")
            rng.shuffle(deck[keys_count:])
        rooms[rid].deck = DeckState(cards=deck)

    players = {
        PlayerId("P1"): PlayerState(player_id=PlayerId("P1"), sanity=3, room=corridor_id(1)),
        PlayerId("P2"): PlayerState(player_id=PlayerId("P2"), sanity=3, room=corridor_id(2)),
    }

    # P1: Crear GameState con flags de habitaciones especiales
    state = GameState(round=1, players=players, rooms=rooms, seed=seed, king_floor=1)

    # P1: Guardar información de habitaciones especiales en flags
    selected_types = list(special_room_locations.keys())
    state.flags["SPECIAL_ROOMS_SELECTED"] = selected_types
    state.flags["SPECIAL_ROOM_LOCATIONS"] = special_room_locations
    state.flags["CAMARA_LETAL_PRESENT"] = "CAMARA_LETAL" in selected_types

    return state


def run_episode(
    max_steps: int = 400,
    seed: int = 1,
    out_path: Optional[str] = None,
    cfg: Optional[Config] = None,
) -> GameState:
    cfg = cfg or Config()
    rng = RNG(seed)
    state = make_smoke_state(seed=seed, cfg=cfg)

    ppol = GoalDirectedPlayerPolicy(cfg)
    kpol = HeuristicKingPolicy(cfg)

    records: List[Dict[str, Any]] = []
    step_idx = 0

    while step_idx < max_steps and not state.game_over:
        if state.phase == "PLAYER":
            actor = str(state.turn_order[state.turn_pos])
            action = ppol.choose(state, rng)
        else:
            actor = "KING"
            action = kpol.choose(state, rng)

        next_state = step(state, action, rng, cfg)

        # Track d6 if KING_ENDROUND
        action_dict = {"actor": actor, "type": action.type.value, "data": action.data}
        if action.type.value == "KING_ENDROUND" and rng.last_king_d6 is not None:
            action_dict["d6"] = rng.last_king_d6

        records.append(
            transition_record(
                state=state,
                action=action_dict,
                next_state=next_state,
                cfg=cfg,
                step_idx=step_idx,
            )
        )

        state = next_state
        step_idx += 1

    if out_path is None:
        Path("runs").mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = f"runs/run_seed{seed}_{ts}.jsonl"

    write_jsonl(out_path, records)
    print(f"Saved run to: {out_path}")
    print("Finished:", state.game_over, state.outcome, "round", state.round, "steps", step_idx)
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-steps", type=int, default=400)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()
    run_episode(max_steps=args.max_steps, seed=args.seed, out_path=args.out)


if __name__ == "__main__":
    main()

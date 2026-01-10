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


def make_smoke_state(seed: int = 1, cfg: Optional[Config] = None) -> GameState:
    cfg = cfg or Config()
    rng = RNG(seed)

    rooms: Dict[RoomId, RoomState] = {}
    room_ids: List[RoomId] = []

    for f in (1, 2, 3):
        rooms[corridor_id(f)] = RoomState(room_id=corridor_id(f), deck=DeckState(cards=[]))
        for r in (1, 2, 3, 4):
            rid = room_id(f, r)
            room_ids.append(rid)
            rooms[rid] = RoomState(room_id=rid, deck=DeckState(cards=[]))

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

    return GameState(round=1, players=players, rooms=rooms, seed=seed, king_floor=1)


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

        records.append(
            transition_record(
                state=state,
                action={"actor": actor, "type": action.type.value, "data": action.data},
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

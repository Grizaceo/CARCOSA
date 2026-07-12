"""
tools/distill_replay.py — Convierte un jsonl del simulador (sim.runner / game_server)
al formato de replay compacto que consume el motor HALI (web/hali/).

Cada registro del jsonl trae full_state (estado PRE-acción). El replay destilado
conserva solo lo renderizable: posiciones, cordura, llaves, monstruos, Rey,
mazos restantes, especiales, tensión y la acción ejecutada.

Uso:
    python3 tools/distill_replay.py runs/.../seedN.jsonl -o web/hali/replays/demo.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _deck_remaining(room: Dict[str, Any], full_state: Dict[str, Any], rid: str) -> int:
    boxes = full_state.get("boxes") or {}
    box_at_room = full_state.get("box_at_room") or {}
    box_id = box_at_room.get(rid)
    deck = None
    if box_id and box_id in boxes:
        deck = boxes[box_id].get("deck")
    if deck is None:
        deck = room.get("deck")
    if not deck:
        return 0
    return max(0, len(deck.get("cards", [])) - int(deck.get("top", 0)))


def distill_frame(rec: Dict[str, Any]) -> Dict[str, Any]:
    fs = rec["full_state"]
    players = {}
    for pid, p in fs["players"].items():
        players[pid] = {
            "room": p["room"],
            "sanity": p["sanity"],
            "sanityMax": p.get("sanity_max"),
            "keys": p.get("keys", 0),
            "role": p.get("role_id", "DEFAULT"),
            "statuses": [s["status_id"] for s in p.get("statuses", [])],
            "objects": list(p.get("objects", [])),
            "atMinus5": bool(p.get("at_minus5", False)),
        }

    rooms_deck = {}
    specials = {}
    for rid, room in fs["rooms"].items():
        rooms_deck[rid] = _deck_remaining(room, fs, rid)
        if room.get("special_card_id"):
            specials[rid] = [
                room["special_card_id"],
                bool(room.get("special_revealed", False)),
                bool(room.get("special_destroyed", False)),
            ]

    return {
        "s": rec["step"],
        "r": rec["round"],
        "ph": rec["phase"],
        "actor": rec["actor"],
        "a": {"t": rec["action_type"], "d": rec.get("action_data", {})},
        "T": round(float(rec.get("T_pre", 0.0)), 4),
        "k": fs.get("king_floor", 1),
        "fk": fs.get("false_king_floor"),
        "kd": fs.get("keys_destroyed", 0),
        "P": players,
        "M": [
            [m["monster_id"], m["room"], int(m.get("stunned_remaining_rounds", 0))]
            for m in fs.get("monsters", [])
        ],
        "D": rooms_deck,
        "SP": specials,
        "ev": rec.get("sanity_loss_events", []) or [],
        "done": bool(rec.get("done", False)),
        "outcome": rec.get("outcome"),
    }


def distill(in_path: str, out_path: str) -> Dict[str, Any]:
    frames = []
    first_fs = None
    last = None
    with open(in_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if first_fs is None:
                first_fs = rec["full_state"]
            frames.append(distill_frame(rec))
            last = rec

    if first_fs is None:
        raise SystemExit(f"jsonl vacío: {in_path}")

    replay = {
        "v": 1,
        "meta": {
            "source": str(in_path),
            "seed": first_fs.get("seed"),
            "policy": (last or {}).get("policy"),
            "outcome": (last or {}).get("outcome"),
            "rounds": (last or {}).get("round"),
            "steps": len(frames),
            "roles": first_fs.get("roles_assigned", {}),
        },
        "stairs": {str(k): v for k, v in (first_fs.get("stairs") or {}).items()},
        "umbral": "F2_P",
        "keysToWin": 4,
        "frames": frames,
    }

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(replay, f, ensure_ascii=False, separators=(",", ":"))
    size_kb = out.stat().st_size / 1024
    print(f"Replay destilado: {out} ({len(frames)} frames, {size_kb:.0f} KB)")
    return replay


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="jsonl del simulador (con full_state por registro)")
    ap.add_argument("-o", "--output", required=True, help="ruta del replay JSON de salida")
    args = ap.parse_args()
    distill(args.input, args.output)


if __name__ == "__main__":
    main()

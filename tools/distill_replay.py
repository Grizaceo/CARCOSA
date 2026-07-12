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


def _active_deck(room: Dict[str, Any], full_state: Dict[str, Any], rid: str) -> Dict[str, Any]:
    boxes = full_state.get("boxes") or {}
    box_at_room = full_state.get("box_at_room") or {}
    box_id = box_at_room.get(rid)
    deck = None
    if box_id and box_id in boxes:
        deck = boxes[box_id].get("deck")
    if deck is None:
        deck = room.get("deck")
    return deck or {"cards": [], "top": 0}


def _deck_remaining(room: Dict[str, Any], full_state: Dict[str, Any], rid: str) -> int:
    deck = _active_deck(room, full_state, rid)
    return max(0, len(deck.get("cards", [])) - int(deck.get("top", 0)))


# ── Inferencia de eventos por diff de estados (espejo de web/hali/js/hali-events.js) ──

def _rich(fs: Dict[str, Any]) -> Dict[str, Any]:
    players = {
        pid: {
            "room": p["room"], "sanity": p["sanity"], "keys": p.get("keys", 0),
            "objects": list(p.get("objects", [])),
            "statuses": [s["status_id"] for s in p.get("statuses", [])],
        }
        for pid, p in fs.get("players", {}).items()
    }
    rooms = {
        rid: {
            "specialId": r.get("special_card_id"),
            "specialRevealed": bool(r.get("special_revealed")),
            "specialDestroyed": bool(r.get("special_destroyed")),
        }
        for rid, r in fs.get("rooms", {}).items()
    }
    # Mazos por BOX (identidad estable a través de la rotación "sushi")
    decks, box_room = {}, {}
    boxes = fs.get("boxes") or {}
    for rid, box_id in (fs.get("box_at_room") or {}).items():
        box = boxes.get(box_id)
        if not box or not box.get("deck"):
            continue
        decks[box_id] = {"top": int(box["deck"].get("top", 0)), "cards": box["deck"].get("cards", [])}
        box_room[box_id] = rid
    return {
        "players": players, "rooms": rooms, "decks": decks, "boxRoom": box_room,
        "phase": fs.get("phase"),
        "monsters": [{"id": m["monster_id"], "room": m["room"]} for m in fs.get("monsters", [])],
        "kingFloor": fs.get("king_floor"), "log": fs.get("action_log", []),
        "gameOver": bool(fs.get("game_over")), "outcome": fs.get("outcome"),
    }


def _who_in(rich: Dict[str, Any], rid: str) -> str | None:
    for pid, p in rich["players"].items():
        if p["room"] == rid:
            return pid
    return None


def _infer_events(prev: Dict[str, Any], curr: Dict[str, Any]) -> list:
    ev: list = []
    for rid, cr in curr["rooms"].items():
        pr = prev["rooms"].get(rid)
        if not pr or not cr["specialId"]:
            continue
        if cr["specialRevealed"] and not pr["specialRevealed"]:
            ev.append({"t": "SPECIAL", "room": rid, "id": cr["specialId"], "p": _who_in(curr, rid)})
        if cr["specialDestroyed"] and not pr["specialDestroyed"]:
            ev.append({"t": "SPECIAL_DESTROYED", "room": rid, "id": cr["specialId"]})

    # cartas reveladas (por box; se omite la fase del Rey: rotar no revela)
    if prev.get("phase") != "KING":
        for bid, cd in curr["decks"].items():
            pd = prev["decks"].get(bid)
            if not pd:
                continue
            rid = prev["boxRoom"].get(bid) or curr["boxRoom"].get(bid)
            for k in range(pd["top"], min(cd["top"], len(pd["cards"]))):
                who = _who_in(curr, rid) or _who_in(prev, rid)
                ev.append({"t": "CARD", "p": who, "room": rid, "card": str(pd["cards"][k])})

    for entry in curr["log"][len(prev["log"]):]:
        e = entry.get("event") if isinstance(entry, dict) else None
        if e == "PEEK_RESULT":
            ev.append({"t": "PEEK", "room": entry.get("room"), "card": entry.get("card")})
        elif e == "ESCAPE_ATTEMPT":
            ev.append({"t": "ESCAPE", "d6": entry.get("d6"), "sanity": entry.get("sanity"),
                       "total": entry.get("total"), "ok": bool(entry.get("success"))})
        elif e == "KING_VANISHED":
            ev.append({"t": "VANISH", "turns": entry.get("turns")})

    prev_ids = {m["id"] for m in prev["monsters"]}
    curr_ids = {m["id"] for m in curr["monsters"]}
    for m in curr["monsters"]:
        if m["id"] not in prev_ids:
            ev.append({"t": "MONSTER", "m": m["id"], "room": m["room"]})
    for m in prev["monsters"]:
        if m["id"] not in curr_ids:
            ev.append({"t": "MONSTER_GONE", "m": m["id"]})

    for pid, cp in curr["players"].items():
        pp = prev["players"].get(pid)
        if not pp:
            continue
        for obj in [o for o in cp["objects"] if o not in pp["objects"]]:
            ev.append({"t": "ITEM", "p": pid, "item": obj})
        for obj in [o for o in pp["objects"] if o not in cp["objects"]]:
            ev.append({"t": "ITEM_LOST", "p": pid, "item": obj})
        if cp["keys"] > pp["keys"]:
            ev.append({"t": "KEY", "p": pid, "d": cp["keys"] - pp["keys"]})
        if cp["keys"] < pp["keys"]:
            ev.append({"t": "KEY_LOST", "p": pid, "d": pp["keys"] - cp["keys"]})
        for st in [s for s in cp["statuses"] if s not in pp["statuses"]]:
            ev.append({"t": "STATUS", "p": pid, "st": st})
        for st in [s for s in pp["statuses"] if s not in cp["statuses"]]:
            ev.append({"t": "STATUS_END", "p": pid, "st": st})
        ds = cp["sanity"] - pp["sanity"]
        if ds:
            ev.append({"t": "SANITY", "p": pid, "d": ds})

    if curr["kingFloor"] != prev["kingFloor"]:
        ev.append({"t": "KINGMOVE", "floor": curr["kingFloor"]})
    if curr["gameOver"] and not prev["gameOver"]:
        ev.append({"t": "GAMEOVER", "outcome": curr["outcome"]})
    return ev


def _inventory_limits(role: str, objects: list, penalty: int) -> tuple:
    """Espejo de engine/systems/inventory.get_inventory_limits (solo display)."""
    key_cap = 2 if role == "HIGH_ROLLER" else 1
    if "TREASURE_RING" in (objects or []):
        key_cap += 1
    base = 3 if role == "TANK" else (1 if role == "SCOUT" else 2)
    return key_cap, max(0, base - (penalty or 0))


def distill_frame(rec: Dict[str, Any]) -> Dict[str, Any]:
    fs = rec["full_state"]
    remaining = fs.get("remaining_actions", {}) or {}
    players = {}
    for pid, p in fs["players"].items():
        role = p.get("role_id", "DEFAULT")
        objects = list(p.get("objects", []))
        key_cap, obj_slots = _inventory_limits(role, objects, p.get("object_slots_penalty", 0))
        players[pid] = {
            "room": p["room"],
            "sanity": p["sanity"],
            "sanityMax": p.get("sanity_max"),
            "keys": p.get("keys", 0),
            "role": role,
            "statuses": [s["status_id"] for s in p.get("statuses", [])],
            "objects": objects,
            "atMinus5": bool(p.get("at_minus5", False)),
            "ra": remaining.get(pid),
            "kc": key_cap,
            "os": obj_slots,
            "sb": list(p.get("soulbound_items", [])),
            "oc": dict(p.get("object_charges", {})),
            "sh": p.get("shield", 0),
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
    prev_rich = None
    with open(in_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if first_fs is None:
                first_fs = rec["full_state"]
            frame = distill_frame(rec)
            # eventos causados por la acción anterior (diff de estados consecutivos)
            rich = _rich(rec["full_state"])
            frame["E"] = _infer_events(prev_rich, rich) if prev_rich else []
            # atribución de reveals sin dueño: el actor de la acción anterior
            causer = frames[-1]["actor"] if frames else None
            if causer and causer != "KING":
                for ev in frame["E"]:
                    if ev["t"] == "CARD" and ev.get("p") is None:
                        ev["p"] = causer
            prev_rich = rich
            frames.append(frame)
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

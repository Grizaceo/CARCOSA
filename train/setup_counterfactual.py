"""
Contra-fáctico de setup: ¿el techo de ganabilidad se mueve ajustando el setup?

Vía (1)/(5) del cierre 2026-08-05: si el problema es el diseño (keys enterradas,
decks que condenan), reordenar el setup SIN tocar la política debería subir el
win-rate de GOAL. Si NO sube, el setup no es el cuello — y las vías (2)/(3)/(4)
(reward) vuelven a ser las candidatas.

Variantes (todas solo reordenan el deck ANTES de jugar; la política GOAL es
idéntica y determinista):
  base         : setup canónico (referencia)
  keys_top     : en CADA habitación, las keys flotan al tope del deck
                 (orden estable del resto de cartas)
  keys_top_f2  : solo en F2 (piso del Umbral)
  motemey_top  : la key de Motemey al tope de ese mazo

Uso:
    python3 train/setup_counterfactual.py [--seeds 300] [--workers 8]
    python3 train/setup_counterfactual.py --seeds 30 --workers 4   # smoke
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.runner import make_smoke_state, run_episode

VARIANTS = ["base", "keys_top", "keys_top_f2", "motemey_top"]


def _reorder_deck_keys(deck, rooms_filter=None):
    """Reordena las cartas del deck para que las KEY queden al tope (orden estable)."""
    cards = list(deck.cards)
    keys = [c for c in cards if c == "KEY"]
    rest = [c for c in cards if c != "KEY"]
    deck.cards = keys + rest
    deck.top = 0


def build_variant_state(seed: int, variant: str):
    state = make_smoke_state(seed=seed)
    if variant == "base":
        return state
    if variant == "keys_top":
        for rid, room in state.rooms.items():
            if "_P" in str(rid):
                continue
            _reorder_deck_keys(room.deck)
        from engine.boxes import sync_boxes_from_rooms

        sync_boxes_from_rooms(state)
    elif variant == "keys_top_f2":
        for rid, room in state.rooms.items():
            if "_P" in str(rid) or not str(rid).startswith("F2_"):
                continue
            _reorder_deck_keys(room.deck)
        from engine.boxes import sync_boxes_from_rooms

        sync_boxes_from_rooms(state)
    elif variant == "motemey_top":
        _reorder_deck_keys(state.motemey_deck)
    else:
        raise ValueError(f"variante desconocida: {variant}")
    return state


def _eval_one(args):
    seed, variant = args
    state = build_variant_state(seed, variant)
    st = run_episode(max_steps=2000, seed=seed, policy_name="GOAL", initial_state=state)
    return {
        "seed": seed,
        "variant": variant,
        "win": bool(getattr(st, "outcome", None) == "WIN"),
        "outcome": str(getattr(st, "outcome", "?")),
        "round": getattr(st, "round", None),
        "keys": sum(p.keys for p in st.players.values()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=300)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--tag", default="")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    n = 30 if args.smoke else args.seeds
    repo = Path(__file__).parent.parent
    tasks = [(s, v) for v in VARIANTS for s in range(n)]

    t0 = __import__("time").time()
    results = []
    if args.workers > 1:
        from multiprocessing import Pool

        with Pool(args.workers) as pool:
            for r in pool.imap_unordered(_eval_one, tasks):
                results.append(r)
    else:
        for t in tasks:
            results.append(_eval_one(t))
    dt = __import__("time").time() - t0

    by_var = {v: [] for v in VARIANTS}
    for r in results:
        by_var[r["variant"]].append(r)

    print("=" * 72)
    print(
        f"CONTRA-FÁCTICO SETUP — GOAL idéntica, solo cambia el setup ({n} seeds, {dt:.0f}s)"
    )
    print("=" * 72)
    rows = []
    for v in VARIANTS:
        rs = by_var[v]
        wins = [r for r in rs if r["win"]]
        wr = len(wins) / max(1, len(rs)) * 100
        rounds = [r["round"] for r in wins if r["round"]]
        avg_r = sum(rounds) / len(rounds) if rounds else None
        avg_keys = sum(r["keys"] for r in rs) / max(1, len(rs))
        rows.append((v, len(rs), len(wins), wr, avg_r, avg_keys))
        print(
            f"  {v:<14} n={len(rs):>3} wins={len(wins):>3}  {wr:>5.1f}%  "
            f"ronda_win_avg={avg_r if avg_r is None else round(avg_r, 1)}  keys_final_avg={avg_keys:.2f}"
        )

    base_wins = {r["seed"] for r in by_var["base"] if r["win"]}
    print()
    for v in VARIANTS[1:]:
        vw = {r["seed"] for r in by_var[v] if r["win"]}
        novel = sorted(vw - base_wins)
        lost = sorted(base_wins - vw)
        print(
            f"  {v}: novelas vs base={len(novel)} {novel[:12]} | perdidas vs base={len(lost)} {lost[:8]}"
        )

    out = {
        "meta": {"seeds": n, "workers": args.workers, "tag": args.tag},
        "results": results,
        "summary": {
            v: {"wins": len([r for r in by_var[v] if r["win"]]), "n": len(by_var[v])}
            for v in VARIANTS
        },
    }
    out_path = (
        repo
        / "reports"
        / f"setup_counterfactual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    out_path.write_text(json.dumps(out, indent=1, default=str))
    print(f"\n[guardado] {out_path}")


if __name__ == "__main__":
    main()

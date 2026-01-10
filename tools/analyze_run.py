from __future__ import annotations
import json
import sys
from collections import Counter

def main(path: str) -> None:
    steps = 0
    rounds = set()
    done = False
    outcome = None

    max_keys = 0
    max_umbral = 0.0
    win_ready_preking = 0  # fase KING con keys>=4 y umbral_frac==1.0

    king_floor = Counter()
    king_d6 = Counter()

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            steps += 1
            rounds.add(r.get("round"))
            done = bool(r.get("done", False))
            outcome = r.get("outcome", outcome)

            sp = r.get("summary_pre", {}) or {}
            max_keys = max(max_keys, int(sp.get("keys_in_hand", 0)))
            max_umbral = max(max_umbral, float(sp.get("umbral_frac", 0.0)))

            if r.get("phase") == "KING":
                if int(sp.get("keys_in_hand", 0)) >= 4 and float(sp.get("umbral_frac", 0.0)) >= 1.0:
                    win_ready_preking += 1

            ad = r.get("action_data", {}) or {}
            if r.get("action_type") == "KING_ENDROUND":
                if "floor" in ad:
                    king_floor[int(ad["floor"])] += 1
                if "d6" in ad:
                    king_d6[int(ad["d6"])] += 1

    print(f"File: {path}")
    print(f"Steps: {steps} | approx_rounds_seen: {len(rounds)} | done: {done} | outcome: {outcome}")
    print(f"Max keys_in_hand observed: {max_keys}")
    print(f"Max umbral_frac observed: {max_umbral:.2f}")
    print(f"WIN-ready on KING phase (keys>=4 & all in umbral): {win_ready_preking}")

    if king_floor:
        print("KING floor counts:", dict(king_floor))
    if king_d6:
        print("KING d6 counts:", dict(king_d6))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/analyze_run.py <path_to_jsonl>")
        raise SystemExit(2)
    main(sys.argv[1])

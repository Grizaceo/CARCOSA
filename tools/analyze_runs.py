#!/usr/bin/env python3
"""Analyze recent run summaries to understand bot behavior."""
import json
import glob
import sys
from pathlib import Path

root = Path(__file__).parent.parent
files = sorted(glob.glob(str(root / "runs/**/*_summary.json"), recursive=True))

if "--last" in sys.argv:
    idx = sys.argv.index("--last")
    n = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 20
    files = files[-n:]

print(f"Analyzing {len(files)} run(s)\n")

outcomes = {}
keys_at_end = []
rounds_list = []
loss_reasons = {}

for f in files:
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue

    outcome = d.get("outcome", "?")
    outcomes[outcome] = outcomes.get(outcome, 0) + 1
    keys_at_end.append(d.get("keys_in_hand", 0))
    rounds_list.append(d.get("round", 0))

    print(f"[{d.get('seed','?')}] {outcome} | round={d.get('round')} steps={d.get('steps')} keys={d.get('keys_in_hand')} destroyed={d.get('keys_destroyed_total')}")

    sac = d.get("sacrifice", {})
    if isinstance(sac, dict):
        print(f"  sacrifice: opps={sac.get('opportunities',0)} sac={sac.get('sacrifice',0)} acc={sac.get('accept',0)} sac_w_keys={sac.get('sacrifice_with_keys',0)}")
        if sac.get("keys_destroyed_by"):
            print(f"  keys_destroyed_by: {sac.get('keys_destroyed_by')}")
        if sac.get("keys_destroyed_sources"):
            print(f"  keys_destroyed_sources: {sac.get('keys_destroyed_sources')}")
    print()

print("=== AGGREGATE ===")
total = len(files)
wins = outcomes.get("WIN", 0)
print(f"Winrate: {wins}/{total} = {wins/total:.1%}")
print(f"Outcomes: {outcomes}")
if keys_at_end:
    print(f"Keys in hand at end: avg={sum(keys_at_end)/len(keys_at_end):.1f} max={max(keys_at_end)} min={min(keys_at_end)}")
if rounds_list:
    print(f"Rounds: avg={sum(rounds_list)/len(rounds_list):.1f} max={max(rounds_list)} min={min(rounds_list)}")

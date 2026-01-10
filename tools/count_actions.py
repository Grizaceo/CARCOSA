#!/usr/bin/env python3
"""Debug: contar acciones."""
import sys
sys.path.insert(0, "/home/gris/carcosa")
import json

# Load the JSONL run
with open("runs/run_seed1_20260110_055003.jsonl", "r") as f:
    records = [json.loads(line) for line in f]

search_count = 0
move_count = 0
for r in records:
    action_type = r.get("action_type", "")
    if action_type == "SEARCH":
        search_count += 1
    elif action_type == "MOVE":
        move_count += 1

print(f"Total steps: {len(records)}")
print(f"SEARCH count: {search_count}")
print(f"MOVE count: {move_count}")

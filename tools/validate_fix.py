#!/usr/bin/env python3
"""Validate fix: run 5 episodes with different seeds."""
import subprocess
import re

print("=== Validation: 5 runs with seeds 1-5 ===\n")

results = {}
for seed in range(1, 6):
    print(f"Running seed {seed}...", end=" ", flush=True)
    result = subprocess.run(
        [".venv/bin/python", "-m", "sim.runner", "--seed", str(seed), "--max-steps", "400"],
        capture_output=True,
        text=True,
        cwd="/home/gris/carcosa"
    )
    
    output = result.stdout + result.stderr
    # Extract: "Finished: True WIN round 36 steps 175"
    match = re.search(r"Finished:\s+(\w+)\s+(\w+)\s+round\s+(\d+)\s+steps\s+(\d+)", output)
    
    if match:
        game_over = match.group(1) == "True"
        outcome = match.group(2)
        round_num = int(match.group(3))
        steps = int(match.group(4))
        results[seed] = (outcome, round_num, steps)
        print(f"{outcome} (round {round_num}, steps {steps})")
    else:
        print("ERROR parsing output")

print("\n=== Summary ===")
wins = sum(1 for r in results.values() if r[0] == "WIN")
loses = sum(1 for r in results.values() if r[0] == "LOSE")
timeouts = sum(1 for r in results.values() if r[0] == "TIMEOUT")

print(f"WIN: {wins}/5")
print(f"LOSE: {loses}/5")
print(f"TIMEOUT: {timeouts}/5")

for seed, (outcome, round_num, steps) in sorted(results.items()):
    print(f"  Seed {seed}: {outcome} round {round_num} steps {steps}")

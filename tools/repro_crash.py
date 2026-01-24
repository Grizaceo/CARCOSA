
from sim.runner import run_episode
from engine.config import Config
import traceback
import sys

def main():
    print("Starting reproduction for seed 1316 (GOAL policy)...")
    try:
        # We will modify runner.py temporarily to print flags or intercept loop, 
        # but let's first see if it crashes deterministically.
        state = run_episode(seed=1316, policy_name="GOAL", max_steps=400)
        print("Run finished successfully!")
    except Exception as e:
        print("\nCRASH CAUGHT:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

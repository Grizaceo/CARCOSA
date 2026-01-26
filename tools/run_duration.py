
import time
import argparse
try:
    from tools.run_versioned import run_episode
except ImportError:
    # Fallback if running directly or issues with path
    import sys
    import os
    sys.path.append(os.getcwd())
    from tools.run_versioned import run_episode
import sys

def run_for_duration(duration_minutes: float):
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    print(f"Starting simulations for {duration_minutes} minutes...")
    
    seed = 1
    runs_count = 0
    version_dir = None
    
    while time.time() < end_time:
        # First run initializes version_dir
        out_file = run_episode(seed, max_steps=400, version_dir=version_dir)
        if version_dir is None:
             # Extract directory from output path
             import os
             version_dir = os.path.dirname(out_file)
             print(f"Saving runs to: {version_dir}")
        
        runs_count += 1
        print(f"Run {runs_count} (Seed {seed}) completed. Time left: {int(end_time - time.time())}s")
        seed += 1
        
    print(f"Finished! Completed {runs_count} runs in {duration_minutes} minutes.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=10.0)
    args = parser.parse_args()
    
    run_for_duration(args.minutes)

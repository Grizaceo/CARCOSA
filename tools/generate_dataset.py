
import os
import argparse
import subprocess
from datetime import datetime

def run_simulation(seed: int, policy: str):
    """Corre una simulación con un seed y policy específicos."""
    cmd = [
        "python", "sim/runner.py",
        "--seed", str(seed),
        "--max-steps", "400",
        "--policy", policy
    ]
    # No imprimir stdout para mantener limpio el log
    subprocess.run(cmd, check=True)

def generate_dataset(num_seeds: int, policies: list):
    """Genera n seeds por cada policy."""
    print(f"Generating dataset: {num_seeds} seeds for policies {policies}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Crear carpeta específica para este lote
    batch_dir = f"runs/batch_{timestamp}"
    os.makedirs(batch_dir, exist_ok=True)
    
    # Override de runner default path hackeando sys.argv o mejor usando el argumento --out
    # Pero runner.py ya formatea el nombre. Lo moveremos después.
    # Actually, runner.py puts it in runs/. We can leave it there.
    
    count = 0
    for policy in policies:
        print(f"--- Running Policy: {policy} ---")
        for i in range(1, num_seeds + 1):
            seed = i * 1000 + (hash(policy) % 1000) # Seed determinista pero distinto por policy
            if seed < 0: seed = -seed
            
            print(f"[{count+1}/{num_seeds*len(policies)}] Seed {seed}...")
            
            # Formatear output para que vaya a la carpeta del batch
            out_file = os.path.join(batch_dir, f"run_{policy}_seed{seed}.jsonl")
            
            env = os.environ.copy()
            env["PYTHONPATH"] = os.getcwd()
            
            cmd = [
                "python", "sim/runner.py",
                "--seed", str(seed),
                "--policy", policy,
                "--out", out_file
            ]
            subprocess.run(cmd, check=True, env=env)
            count += 1
            
    print(f"\nDone! Generated {count} runs in {batch_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate CARCOSA simulation dataset")
    parser.add_argument("--seeds", type=int, default=5, help="Number of seeds per policy")
    args = parser.parse_args()
    
    policies = ["GOAL", "BERSERKER", "COWARD", "SPEEDRUNNER", "RANDOM"]
    generate_dataset(args.seeds, policies)

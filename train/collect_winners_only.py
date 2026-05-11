import os
import sys
import numpy as np
import argparse
import pickle
from pathlib import Path
import time
import multiprocessing as mp
from tqdm import tqdm

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from train.carcosa_env import CarcosaEnv
from sb3_contrib import MaskablePPO

def collect_winners_worker(worker_id, num_wins_target, model_path, output_queue, stop_event):
    """Worker que corre episodios hasta encontrar victorias."""
    env = CarcosaEnv()
    
    # Cargar modelo si existe, si no usar random
    model = None
    if model_path and os.path.exists(model_path):
        model = MaskablePPO.load(model_path)
    
    wins_found = 0
    
    while not stop_event.is_set() and wins_found < num_wins_target:
        obs, info = env.reset()
        done = False
        
        ep_obs = []
        ep_actions = []
        
        step_count = 0
        max_steps = 800 # Limitar para no perder tiempo en timeouts
        
        while not done and step_count < max_steps:
            # Seleccionar acción
            if model:
                action_masks = env.action_masks()
                # 80% modelo (estocástico), 20% random puro para máxima exploración
                if np.random.random() < 0.8:
                    action, _ = model.predict(obs, action_masks=action_masks, deterministic=False)
                else:
                    legal_ids = np.where(action_masks)[0]
                    action = np.random.choice(legal_ids)
            else:
                action_masks = env.action_masks()
                legal_ids = np.where(action_masks)[0]
                action = np.random.choice(legal_ids)
            
            ep_obs.append(obs)
            ep_actions.append(action)
            
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            step_count += 1
            
            # Early exit si se quedan sin llaves y ya pasó mucho tiempo
            if step_count > 400 and info.get("keys_in_hand", 0) == 0:
                break

        if info.get("outcome") == "WIN":
            wins_found += 1
            output_queue.put({
                "observations": ep_obs,
                "actions": ep_actions
            })
            
    env.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-wins", type=int, default=100)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--output", type=str, default="train/winner_data.pkl")
    args = parser.parse_args()
    
    print(f"Buscando {args.target_wins} victorias usando {args.workers} workers...")
    if args.model:
        print(f"Usando modelo base: {args.model}")
    else:
        print("Usando política aleatoria (Hardcore Monte Carlo)")

    output_queue = mp.Queue()
    stop_event = mp.Event()
    
    # Lanzar workers
    # Nota: num_wins_target por worker es alto para que sigan buscando hasta que el main los pare
    processes = []
    for i in range(args.workers):
        p = mp.Process(
            target=collect_winners_worker, 
            args=(i, args.target_wins, args.model, output_queue, stop_event)
        )
        p.start()
        processes.append(p)

    all_obs = []
    all_actions = []
    wins_collected = 0
    
    pbar = tqdm(total=args.target_wins, desc="Victorias encontradas")
    
    try:
        while wins_collected < args.target_wins:
            try:
                # Timeout pequeño para chequear stop_event
                winner_data = output_queue.get(timeout=1.0)
                all_obs.extend(winner_data["observations"])
                all_actions.extend(winner_data["actions"])
                wins_collected += 1
                pbar.update(1)
                
                # Guardado periódico cada 10 victorias
                if wins_collected % 10 == 0:
                    data = {
                        "observations": np.array(all_obs, dtype=np.float32),
                        "actions": np.array(all_actions, dtype=np.int64),
                        "wins_count": wins_collected
                    }
                    with open(args.output, "wb") as f:
                        pickle.dump(data, f)
            except:
                # Check si los procesos siguen vivos
                if not any(p.is_alive() for p in processes):
                    print("\nTodos los workers han terminado antes de alcanzar la meta.")
                    break
                continue
    except KeyboardInterrupt:
        print("\nInterrupción recibida. Guardando lo recolectado...")
    finally:
        stop_event.set()
        for p in processes:
            p.join(timeout=2.0)
            if p.is_alive():
                p.terminate()

    pbar.close()
    
    # Load existing data if appending is possible
    if os.path.exists(args.output):
        try:
            with open(args.output, "rb") as f:
                existing_data = pickle.load(f)
                all_obs = list(existing_data.get("observations", [])) + all_obs
                all_actions = list(existing_data.get("actions", [])) + all_actions
                wins_collected += existing_data.get("wins_count", 0)
                print(f"Appended to existing data. New total wins: {wins_collected}")
        except Exception as e:
            print(f"Could not append to existing data: {e}. Saving new file.")

    if all_obs:
        data = {
            "observations": np.array(all_obs, dtype=np.float32),
            "actions": np.array(all_actions, dtype=np.int64),
            "wins_count": wins_collected
        }
        
        # Guardar resultados
        with open(args.output, "wb") as f:
            pickle.dump(data, f)
        print(f"\nFinalizado. Se guardaron {wins_collected} victorias ({len(all_obs)} pasos) en {args.output}")
    else:
        print("\nNo se encontraron victorias.")

if __name__ == "__main__":
    main()

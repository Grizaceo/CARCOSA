"""
AI-Ready Data Export Tool
=========================
Convierte archivos JSONL de simulaciones a formatos optimizados para análisis de IA.

Uso:
    python tools/ai_ready_export.py --input runs/run_seed*.jsonl --output data/training.parquet
"""

from __future__ import annotations
import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Carga un archivo JSONL y retorna lista de registros."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            records.append(json.loads(line))
    return records


def extract_states_actions_rewards(records: List[Dict[str, Any]], reward_field: str = "reward") -> Dict[str, List]:
    """Extrae tuplas (state, action, reward, next_state, done) para RL."""
    data = {
        "step": [],
        "round": [],
        "state_pre": [],
        "action": [],
        "reward": [],
        "state_post": [],
        "done": [],
        "outcome": [],
    }
    
    for r in records:
        data["step"].append(r["step"])
        data["round"].append(r["round"])
        data["state_pre"].append(json.dumps(r["summary_pre"]))
        data["action"].append(r["action_type"])
        data["reward"].append(r.get(reward_field, 0.0))
        data["state_post"].append(json.dumps(r["summary_post"]))
        data["done"].append(r["done"])
        data["outcome"].append(r["outcome"])
    
    return data


def extract_features_sequence(records: List[Dict[str, Any]]) -> Dict[str, List]:
    """Extrae secuencias de features para análisis temporal."""
    data = {
        "step": [],
        "round": [],
        "P_sanity": [],
        "P_keys": [],
        "P_mon": [],
        "P_umbral": [],
        "T": [],
        "action": [],
        "done": [],
        "outcome": [],
    }
    
    for r in records:
        data["step"].append(r["step"])
        data["round"].append(r["round"])
        data["P_sanity"].append(r["features_post"].get("P_sanity", 0.0))
        data["P_keys"].append(r["features_post"].get("P_keys", 0.0))
        data["P_mon"].append(r["features_post"].get("P_mon", 0.0))
        data["P_umbral"].append(r["features_post"].get("P_umbral", 0.0))
        data["T"].append(r["T_post"])
        data["action"].append(r["action_type"])
        data["done"].append(r["done"])
        data["outcome"].append(r["outcome"])
    
    return data


def extract_policy_examples(records: List[Dict[str, Any]]) -> Dict[str, List]:
    """Extrae ejemplos de decisiones para imitation learning."""
    player_data = {
        "actor": [],
        "round": [],
        "phase": [],
        "action": [],
        "sanity": [],
        "keys": [],
        "monsters": [],
        "umbral": [],
        "tension": [],
    }
    
    king_data = {
        "round": [],
        "floor_pre": [],
        "floor_post": [],
        "d6": [],
        "king_utility_delta": [],
    }
    
    for r in records:
        if r["actor"] == "KING":
            action_data = r.get("action_data", {})
            king_data["round"].append(r["round"])
            king_data["floor_pre"].append(r["summary_pre"].get("king_floor", 1))
            king_data["floor_post"].append(r["summary_post"].get("king_floor", 1))
            king_data["d6"].append(action_data.get("d6", None))
            king_data["king_utility_delta"].append(r["king_reward"])
        else:
            summary = r["summary_pre"]
            player_data["actor"].append(r["actor"])
            player_data["round"].append(r["round"])
            player_data["phase"].append(r["phase"])
            player_data["action"].append(r["action_type"])
            player_data["sanity"].append(summary.get("min_sanity", 0))
            player_data["keys"].append(summary.get("keys_in_hand", 0))
            player_data["monsters"].append(summary.get("monsters", 0))
            player_data["umbral"].append(summary.get("umbral_frac", 0.0))
            player_data["tension"].append(r["T_pre"])
    
    return {"player": player_data, "king": king_data}


def summarize_run(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Genera resumen de estadísticas generales de la partida."""
    outcomes = [r["outcome"] for r in records if r["done"]]
    outcome = outcomes[0] if outcomes else None
    
    final_record = records[-1] if records else {}
    summary = final_record.get("summary_post", {})
    
    max_tension = max((r["T_post"] for r in records), default=0.0)
    min_sanity = min((r["summary_post"].get("min_sanity", 0) for r in records), default=0)
    max_keys = max((r["summary_post"].get("keys_in_hand", 0) for r in records), default=0)
    
    king_actions = [r for r in records if r["actor"] == "KING"]
    king_avg_reward = (sum(r["king_reward"] for r in king_actions) / len(king_actions)) if king_actions else 0.0
    
    return {
        "total_steps": len(records),
        "total_rounds": final_record.get("round", 0),
        "outcome": outcome,
        "max_tension": max_tension,
        "min_sanity_observed": min_sanity,
        "max_keys_in_hand": max_keys,
        "final_keys_destroyed": summary.get("keys_destroyed", 0),
        "king_avg_reward": king_avg_reward,
        "player_count": 2,  # Hardcoded para Carcosa
    }


def main():
    ap = argparse.ArgumentParser(description="Convierte datos de simulación a formato IA-ready")
    ap.add_argument("--input", type=str, nargs="+", required=True, help="Archivos JSONL de entrada")
    ap.add_argument("--output", type=str, default=None, help="Archivo de salida (csv, parquet, json)")
    ap.add_argument("--format", type=str, choices=["csv", "parquet", "json"], 
                    default="csv", help="Formato de salida")
    ap.add_argument("--mode", type=str, choices=["rl", "features", "policy", "all", "summary"], 
                    default="all", help="Modo de extracción")
    ap.add_argument("--reward-field", type=str, default="reward", choices=["reward", "king_reward"],
                    help="Field to use for RL reward (default: reward)")
    
    args = ap.parse_args()
    
    # Cargar todos los archivos
    all_records = []
    for path in args.input:
        print(f"Cargando {path}...")
        records = load_jsonl(path)
        all_records.extend(records)
    
    print(f"Total de registros cargados: {len(all_records)}")
    
    # Procesar según modo
    if args.mode == "summary":
        # Generar resumen
        summary = summarize_run(all_records)
        print("\n=== Resumen de Partida ===")
        for key, value in summary.items():
            print(f"{key}: {value}")
        return
    
    if not HAS_PANDAS and args.format in ["csv", "parquet"]:
        print("Advertencia: pandas no instalado. Use --format json para salida JSON simple.")
        args.format = "json"
    
    # Extraer datos según modo
    if args.mode == "rl":
        print("Extrayendo datos para Reinforcement Learning...")
        data = extract_states_actions_rewards(all_records, args.reward_field)
        name = "rl_transitions"
    elif args.mode == "features":
        print("Extrayendo secuencias de features...")
        data = extract_features_sequence(all_records)
        name = "feature_sequences"
    elif args.mode == "policy":
        print("Extrayendo ejemplos de política...")
        data = extract_policy_examples(all_records)
        # Para policy mode, guardar por separado
        if args.output:
            base = Path(args.output).stem
            for policy_type, policy_data in data.items():
                if HAS_PANDAS:
                    df = pd.DataFrame(policy_data)
                    output = f"{base}_{policy_type}.{args.format}"
                    if args.format == "csv":
                        df.to_csv(output, index=False)
                    elif args.format == "parquet":
                        df.to_parquet(output, index=False)
                    print(f"Guardado: {output}")
                else:
                    output = f"{base}_{policy_type}.json"
                    with open(output, "w") as f:
                        json.dump(policy_data, f, indent=2)
                    print(f"Guardado: {output}")
        return
    else:  # all
        print("Extrayendo todos los modos...")
        # Implementar extracción multi-modo
        data = extract_features_sequence(all_records)
        name = "all_features"
    
    # Guardar
    if args.output is None:
        base = f"data/{name}"
        args.output = f"{base}.{args.format}"
    
    Path(args.output).parent.mkdir(exist_ok=True, parents=True)
    
    if HAS_PANDAS:
        df = pd.DataFrame(data)
        if args.format == "csv":
            df.to_csv(args.output, index=False)
            print(f"[OK] Guardado CSV: {args.output}")
        elif args.format == "parquet":
            df.to_parquet(args.output, index=False)
            print(f"[OK] Guardado Parquet: {args.output}")
    
    if args.format == "json" or not HAS_PANDAS:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[OK] Guardado JSON: {args.output}")


if __name__ == "__main__":
    main()

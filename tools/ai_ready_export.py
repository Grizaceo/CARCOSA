"""
AI-Ready Data Export Tool (v2.0)
=================================
Convierte archivos JSONL de simulaciones a formatos optimizados para:
- Behavioral Cloning / Imitation Learning
- Reinforcement Learning
- Análisis temporal

Uso:
    python tools/ai_ready_export.py --input runs/run_seed*.jsonl --output data/training.parquet
    python tools/ai_ready_export.py --input runs/*.jsonl --mode bc --output data/bc_dataset.csv
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
        "P_debuff": [],
        "P_king_risk": [],
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
        data["P_debuff"].append(r["features_post"].get("P_debuff", 0.0))
        data["P_king_risk"].append(r["features_post"].get("P_king_risk", 0.0))
        data["T"].append(r["T_post"])
        data["action"].append(r["action_type"])
        data["done"].append(r["done"])
        data["outcome"].append(r["outcome"])
    
    return data


def extract_policy_examples(records: List[Dict[str, Any]]) -> Dict[str, List]:
    """
    Extrae ejemplos de decisiones para imitation learning.
    MEJORADO v2: Incluye policy name, room, action_data, y features completos.
    """
    player_data = {
        # Identificación
        "policy": [],          # NUEVO: Qué policy tomó la decisión
        "actor": [],
        "round": [],
        "phase": [],
        
        # Acción tomada
        "action": [],
        "action_data": [],     # NUEVO: Datos específicos (destino, objeto, etc)
        
        # Estado del actor
        "room": [],            # NUEVO: Ubicación actual
        "sanity": [],
        "keys": [],
        
        # Estado global
        "monsters": [],
        "umbral": [],
        "tension": [],
        "king_floor": [],      # NUEVO: Piso del Rey
        
        # Features normalizados completos
        "P_sanity": [],
        "P_keys": [],
        "P_mon": [],
        "P_umbral": [],
        "P_debuff": [],        # NUEVO
        "P_king_risk": [],     # NUEVO
        "P_crown": [],         # NUEVO
        "P_round": [],         # NUEVO
        
        # Outcome de la partida (para filtrar buenos ejemplos)
        "outcome": [],         # NUEVO
    }
    
    king_data = {
        "policy": [],          # NUEVO
        "round": [],
        "floor_pre": [],
        "floor_post": [],
        "d6": [],
        "king_utility_delta": [],
        
        # Features del momento
        "P_sanity": [],        # NUEVO
        "P_keys": [],          # NUEVO
        "P_umbral": [],        # NUEVO
        "tension": [],         # NUEVO
        "outcome": [],         # NUEVO
    }
    
    for r in records:
        policy_name = r.get("policy", "UNKNOWN")
        outcome = r.get("outcome")
        
        if r["actor"] == "KING":
            action_data = r.get("action_data", {})
            features = r.get("features_pre", {})
            
            king_data["policy"].append(policy_name)
            king_data["round"].append(r["round"])
            king_data["floor_pre"].append(r["summary_pre"].get("king_floor", 1))
            king_data["floor_post"].append(r["summary_post"].get("king_floor", 1))
            king_data["d6"].append(action_data.get("d6", None))
            king_data["king_utility_delta"].append(r["king_reward"])
            king_data["P_sanity"].append(features.get("P_sanity", 0.0))
            king_data["P_keys"].append(features.get("P_keys", 0.0))
            king_data["P_umbral"].append(features.get("P_umbral", 0.0))
            king_data["tension"].append(r["T_pre"])
            king_data["outcome"].append(outcome)
        else:
            summary = r["summary_pre"]
            features = r.get("features_pre", {})
            action_data = r.get("action_data", {})
            
            # Extraer room del full_state si existe
            room = None
            full_state = r.get("full_state", {})
            if full_state and "players" in full_state:
                player_state = full_state.get("players", {}).get(r["actor"], {})
                room = player_state.get("room")
            
            player_data["policy"].append(policy_name)
            player_data["actor"].append(r["actor"])
            player_data["round"].append(r["round"])
            player_data["phase"].append(r["phase"])
            player_data["action"].append(r["action_type"])
            player_data["action_data"].append(json.dumps(action_data) if action_data else "")
            player_data["room"].append(room)
            player_data["sanity"].append(summary.get("min_sanity", 0))
            player_data["keys"].append(summary.get("keys_in_hand", 0))
            player_data["monsters"].append(summary.get("monsters", 0))
            player_data["umbral"].append(summary.get("umbral_frac", 0.0))
            player_data["tension"].append(r["T_pre"])
            player_data["king_floor"].append(summary.get("king_floor", 1))
            player_data["P_sanity"].append(features.get("P_sanity", 0.0))
            player_data["P_keys"].append(features.get("P_keys", 0.0))
            player_data["P_mon"].append(features.get("P_mon", 0.0))
            player_data["P_umbral"].append(features.get("P_umbral", 0.0))
            player_data["P_debuff"].append(features.get("P_debuff", 0.0))
            player_data["P_king_risk"].append(features.get("P_king_risk", 0.0))
            player_data["P_crown"].append(features.get("P_crown", 0.0))
            player_data["P_round"].append(features.get("P_round", 0.0))
            player_data["outcome"].append(outcome)
    
    return {"player": player_data, "king": king_data}


def extract_behavioral_cloning_dataset(records: List[Dict[str, Any]]) -> Dict[str, List]:
    """
    NUEVO: Extrae dataset optimizado para Behavioral Cloning con PyTorch.
    
    Formato: (observation_vector, action_id) para cada decisión de jugador.
    - observation_vector: Vector de features numéricos normalizados
    - action_id: Índice de la acción (para clasificación)
    
    Las acciones se mapean a índices enteros para facilitar CrossEntropyLoss.
    """
    # Mapear acciones a IDs
    action_to_id = {}
    
    data = {
        # Metadata (no para entrenamiento directo)
        "step": [],
        "round": [],
        "actor": [],
        "policy": [],
        
        # Features de entrada (observation vector)
        "obs_P_sanity": [],
        "obs_P_keys": [],
        "obs_P_mon": [],
        "obs_P_umbral": [],
        "obs_P_debuff": [],
        "obs_P_king_risk": [],
        "obs_P_crown": [],
        "obs_P_round": [],
        "obs_tension": [],
        "obs_king_floor_norm": [],  # Normalizado: floor / 3
        
        # Label (acción tomada)
        "action": [],
        "action_id": [],
        
        # Para filtrado
        "outcome": [],
        "done": [],
    }
    
    for r in records:
        # Solo decisiones de jugadores (no del King)
        if r["actor"] == "KING":
            continue
            
        features = r.get("features_pre", {})
        summary = r["summary_pre"]
        action_type = r["action_type"]
        
        # Mapear acción a ID
        if action_type not in action_to_id:
            action_to_id[action_type] = len(action_to_id)
        
        data["step"].append(r["step"])
        data["round"].append(r["round"])
        data["actor"].append(r["actor"])
        data["policy"].append(r.get("policy", "UNKNOWN"))
        
        # Observation vector (todas normalizadas 0-1)
        data["obs_P_sanity"].append(features.get("P_sanity", 0.0))
        data["obs_P_keys"].append(features.get("P_keys", 0.0))
        data["obs_P_mon"].append(features.get("P_mon", 0.0))
        data["obs_P_umbral"].append(features.get("P_umbral", 0.0))
        data["obs_P_debuff"].append(features.get("P_debuff", 0.0))
        data["obs_P_king_risk"].append(features.get("P_king_risk", 0.0))
        data["obs_P_crown"].append(features.get("P_crown", 0.0))
        data["obs_P_round"].append(features.get("P_round", 0.0))
        data["obs_tension"].append(r["T_pre"])
        data["obs_king_floor_norm"].append(summary.get("king_floor", 1) / 3.0)
        
        # Action labels
        data["action"].append(action_type)
        data["action_id"].append(action_to_id[action_type])
        
        data["outcome"].append(r.get("outcome"))
        data["done"].append(r["done"])
    
    # Guardar mapeo de acciones
    data["_action_mapping"] = action_to_id
    
    return data


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
    
    # Contar policies usadas
    policies_used = set(r.get("policy", "UNKNOWN") for r in records)
    
    # Contar acciones por tipo
    action_counts = {}
    for r in records:
        act = r["action_type"]
        action_counts[act] = action_counts.get(act, 0) + 1
    
    return {
        "total_steps": len(records),
        "total_rounds": final_record.get("round", 0),
        "outcome": outcome,
        "max_tension": max_tension,
        "min_sanity_observed": min_sanity,
        "max_keys_in_hand": max_keys,
        "final_keys_destroyed": summary.get("keys_destroyed", 0),
        "king_avg_reward": king_avg_reward,
        "player_count": 2,  # Hardcoded para Carcosa base
        "policies_used": list(policies_used),
        "action_distribution": action_counts,
    }


def main():
    ap = argparse.ArgumentParser(description="Convierte datos de simulación a formato IA-ready")
    ap.add_argument("--input", type=str, nargs="+", required=True, help="Archivos JSONL de entrada")
    ap.add_argument("--output", type=str, default=None, help="Archivo de salida (csv, parquet, json)")
    ap.add_argument("--format", type=str, choices=["csv", "parquet", "json"], 
                    default="csv", help="Formato de salida")
    ap.add_argument("--mode", type=str, choices=["rl", "features", "policy", "bc", "all", "summary"], 
                    default="all", help="Modo de extracción (bc = behavioral cloning)")
    ap.add_argument("--reward-field", type=str, default="reward", choices=["reward", "king_reward"],
                    help="Field to use for RL reward (default: reward)")
    ap.add_argument("--filter-outcome", type=str, default=None, choices=["WIN", "LOSE", "TIMEOUT"],
                    help="Filtrar solo registros de partidas con este outcome")
    ap.add_argument("--filter-policy", type=str, default=None,
                    help="Filtrar solo registros de esta policy")
    
    args = ap.parse_args()
    
    # Cargar todos los archivos
    all_records = []
    for path in args.input:
        print(f"Cargando {path}...")
        records = load_jsonl(path)
        all_records.extend(records)
    
    print(f"Total de registros cargados: {len(all_records)}")
    
    # Aplicar filtros si existen
    if args.filter_outcome:
        # Necesitamos agrupar por partida y filtrar
        # Por ahora, filtrar registros cuyo outcome final sea el deseado
        all_records = [r for r in all_records if r.get("outcome") == args.filter_outcome or not r["done"]]
        print(f"Registros después de filtrar outcome={args.filter_outcome}: {len(all_records)}")
    
    if args.filter_policy:
        all_records = [r for r in all_records if r.get("policy") == args.filter_policy]
        print(f"Registros después de filtrar policy={args.filter_policy}: {len(all_records)}")
    
    # Procesar según modo
    if args.mode == "summary":
        # Generar resumen
        summary = summarize_run(all_records)
        print("\n=== Resumen de Partida ===")
        for key, value in summary.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
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
    elif args.mode == "bc":
        print("Extrayendo dataset para Behavioral Cloning...")
        data = extract_behavioral_cloning_dataset(all_records)
        name = "bc_dataset"
        
        # Guardar mapping de acciones por separado
        if "_action_mapping" in data:
            mapping = data.pop("_action_mapping")
            mapping_path = Path(args.output or f"data/{name}").with_suffix(".action_mapping.json")
            mapping_path.parent.mkdir(exist_ok=True, parents=True)
            with open(mapping_path, "w") as f:
                json.dump(mapping, f, indent=2)
            print(f"[OK] Mapeo de acciones guardado: {mapping_path}")
    elif args.mode == "policy":
        print("Extrayendo ejemplos de política...")
        data = extract_policy_examples(all_records)
        # Para policy mode, guardar por separado
        if args.output:
            base = Path(args.output).stem
            parent = Path(args.output).parent
        else:
            base = "policy_examples"
            parent = Path("data")
        
        parent.mkdir(exist_ok=True, parents=True)
        
        for policy_type, policy_data in data.items():
            if HAS_PANDAS:
                df = pd.DataFrame(policy_data)
                output = parent / f"{base}_{policy_type}.{args.format}"
                if args.format == "csv":
                    df.to_csv(output, index=False)
                elif args.format == "parquet":
                    df.to_parquet(output, index=False)
                print(f"Guardado: {output}")
            else:
                output = parent / f"{base}_{policy_type}.json"
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

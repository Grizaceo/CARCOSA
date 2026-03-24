#!/usr/bin/env python3
"""
Fast streaming BC dataset extraction.

Procesa archivos JSONL uno por uno sin cargar todo en memoria.
Escribe directamente al CSV de salida (streaming).

Uso:
    python tools/fast_bc_export.py "datasets/goal_500/*.jsonl" models_bc/bc_mlp_all_best.csv
"""
import json
import csv
import sys
import glob
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        print("Uso: fast_bc_export.py <glob_pattern> <output_csv>")
        sys.exit(1)

    pattern = sys.argv[1]
    output_path = sys.argv[2]

    files = sorted(glob.glob(pattern))
    if not files:
        print(f"ERROR: No files found matching '{pattern}'", file=sys.stderr)
        sys.exit(1)

    print(f"Archivos encontrados: {len(files)}")

    action_to_id: dict = {}
    total_rows = 0

    FIELDNAMES = [
        "step", "round", "actor", "policy",
        "obs_P_sanity", "obs_P_keys", "obs_P_mon", "obs_P_umbral",
        "obs_P_debuff", "obs_P_king_risk", "obs_P_crown", "obs_P_round",
        "obs_tension", "obs_king_floor_norm",
        "action", "action_id",
        "outcome", "done",
    ]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=FIELDNAMES)
        writer.writeheader()

        for idx, file_path in enumerate(files, 1):
            if idx % 50 == 0 or idx == 1:
                print(f"[{idx}/{len(files)}] {file_path}")
            file_rows = 0
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)

                    # Solo decisiones de jugadores (no del King)
                    if r.get("actor") == "KING":
                        continue

                    action_type = r["action_type"]
                    if action_type not in action_to_id:
                        action_to_id[action_type] = len(action_to_id)

                    features = r.get("features_pre", {})
                    summary = r.get("summary_pre", {})

                    writer.writerow({
                        "step": r["step"],
                        "round": r["round"],
                        "actor": r["actor"],
                        "policy": r.get("policy", "UNKNOWN"),
                        "obs_P_sanity": features.get("P_sanity", 0.0),
                        "obs_P_keys": features.get("P_keys", 0.0),
                        "obs_P_mon": features.get("P_mon", 0.0),
                        "obs_P_umbral": features.get("P_umbral", 0.0),
                        "obs_P_debuff": features.get("P_debuff", 0.0),
                        "obs_P_king_risk": features.get("P_king_risk", 0.0),
                        "obs_P_crown": features.get("P_crown", 0.0),
                        "obs_P_round": features.get("P_round", 0.0),
                        "obs_tension": r.get("T_pre", 0.0),
                        "obs_king_floor_norm": summary.get("king_floor", 1) / 3.0,
                        "action": action_type,
                        "action_id": action_to_id[action_type],
                        "outcome": r.get("outcome"),
                        "done": r["done"],
                    })
                    file_rows += 1

            total_rows += file_rows

    print(f"\nTotal filas escritas: {total_rows}")
    print(f"Tipos de acción encontrados ({len(action_to_id)}): {list(action_to_id.keys())}")

    # Guardar mapeo de acciones (sidecar JSON)
    mapping_path = Path(output_path).with_suffix(".action_mapping.json")
    with open(str(mapping_path), "w", encoding="utf-8") as f:
        json.dump(action_to_id, f, indent=2)
    print(f"[OK] Mapeo de acciones guardado: {mapping_path}")
    print("EXPORT_OK")


if __name__ == "__main__":
    main()

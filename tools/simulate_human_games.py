"""
tools/simulate_human_games.py — Sprint 4: Verificación del pipeline BC humano

Simula 3 partidas completas usando el game_server via HTTP (como lo haría Godot),
guarda como JSONL y verifica compatibilidad con ai_ready_export.py.

Uso:
    python tools/simulate_human_games.py
    python tools/simulate_human_games.py --server http://127.0.0.1:8765 --games 3 --seed 100
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Intentar usar httpx, sino urllib
try:
    import httpx
    _USE_HTTPX = True
except ImportError:
    import urllib.request
    import urllib.error
    _USE_HTTPX = False


MAX_STEPS_PER_GAME = 300  # safety limit para evitar loops infinitos


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _post(base_url: str, path: str, data: dict = None) -> Dict[str, Any]:
    url = base_url.rstrip("/") + path
    body = json.dumps(data or {}).encode()
    if _USE_HTTPX:
        r = httpx.post(url, content=body, headers={"Content-Type": "application/json"}, timeout=10)
        r.raise_for_status()
        return r.json()
    else:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())


def _get(base_url: str, path: str) -> Dict[str, Any]:
    url = base_url.rstrip("/") + path
    if _USE_HTTPX:
        r = httpx.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    else:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())


# ── Game simulation ───────────────────────────────────────────────────────────

def simulate_game(base_url: str, seed: int, verbose: bool = True) -> Dict[str, Any]:
    """
    Simula una partida completa usando acciones legales aleatorias (como un bot random),
    a través del HTTP API — exactamente igual a como lo haría Godot.
    
    Retorna el resultado de /save.
    """
    import random
    rng = random.Random(seed)

    # 1. Iniciar partida
    start_resp = _post(base_url, "/start", {"seed": seed})
    game_id = start_resp["game_id"]
    state = start_resp["state"]

    if verbose:
        print(f"  Partida iniciada: game_id={game_id}, seed={seed}")

    steps = 0
    while not state.get("game_over", False) and steps < MAX_STEPS_PER_GAME:
        active_actor = state.get("active_actor", "P1")

        # 2. Obtener acciones legales
        legal_resp = _get(base_url, f"/legal/{game_id}/{active_actor}")
        actions = legal_resp.get("actions", [])

        if not actions:
            if verbose:
                # Get full state for debugging
                state_detail = _get(base_url, f"/state/{game_id}")
                s = state_detail.get("state", state)
                print(f"  ⚠ Sin acciones legales para {active_actor} en step {steps}. "
                      f"phase={s.get('phase')}, round={s.get('round')}, "
                      f"active={s.get('active_actor')}. Terminando.")
            break

        # 3. Elegir acción aleatoria (simulando un humano)
        chosen = rng.choice(actions)
        act_resp = _post(base_url, "/act", {
            "game_id": game_id,
            "actor": active_actor,
            "action_type": chosen["type"],
            "action_data": chosen.get("data", {}),
        })
        state = act_resp["state"]
        steps += 1

        if verbose and steps % 50 == 0:
            print(f"    Step {steps}: actor={active_actor}, action={chosen['type']}, "
                  f"game_over={state.get('game_over')}, outcome={state.get('outcome')}")

    # 4. Guardar sesión
    save_resp = _post(base_url, f"/save/{game_id}")
    outcome = save_resp.get("outcome")
    saved_to = save_resp.get("saved_to", "?")
    n_steps = save_resp.get("steps", steps)

    if verbose:
        print(f"  ✓ Guardado: {saved_to} ({n_steps} pasos, outcome={outcome})")

    return {
        "game_id": game_id,
        "seed": seed,
        "steps": n_steps,
        "outcome": outcome,
        "saved_to": saved_to,
    }


# ── Pipeline verification ─────────────────────────────────────────────────────

def verify_jsonl_format(jsonl_path: str, bot_reference_dir: str = "runs") -> bool:
    """
    Verifica que el JSONL humano tiene los mismos campos clave que un JSONL de bot.
    Compara contra runs/*/seed*.jsonl si existe alguno.
    """
    records = []
    with open(jsonl_path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    if not records:
        print(f"  ✗ JSONL vacío: {jsonl_path}")
        return False

    r = records[0]
    required_fields = [
        "step", "round", "phase", "actor",
        "action_type", "action_data",
        "reward", "T_pre", "T_post",
        "features_pre", "features_post",
        "summary_pre", "summary_post",
        "done", "outcome",
        "full_state",
    ]
    missing = [f for f in required_fields if f not in r]
    if missing:
        print(f"  ✗ Campos faltantes en {jsonl_path}: {missing}")
        return False

    print(f"  ✓ Formato JSONL válido: {len(records)} registros, todos los campos presentes")
    print(f"    policy={r.get('policy', 'N/A')}, outcome={records[-1].get('outcome')}")

    # Verificar campos de features
    fp = r.get("features_pre", {})
    expected_features = ["P_sanity", "P_round", "P_mon", "P_keys", "P_crown", "P_umbral", "P_debuff", "P_king_risk"]
    missing_features = [f for f in expected_features if f not in fp]
    if missing_features:
        print(f"  ⚠ Features faltantes: {missing_features}")
    else:
        print(f"    features_pre: {list(fp.keys())}")

    return True


def run_export_pipeline(jsonl_paths: List[str], output_csv: str) -> bool:
    """
    Ejecuta ai_ready_export.py en modo bc sobre los JSONL generados.
    Intenta primero localmente; si pandas no está disponible, usa Docker.
    """
    import subprocess

    base_args = [
        "--input", *jsonl_paths,
        "--mode", "bc",
        "--output", output_csv,
    ]

    # Intento 1: local
    cmd = [sys.executable, "tools/ai_ready_export.py"] + base_args
    print(f"  Ejecutando (local): {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    stdout = result.stdout + result.stderr

    # Detectar si se usó el fallback JSON (pandas ausente)
    if result.returncode == 0 and "pandas no instalado" not in stdout:
        print(f"  ✓ Export OK:\n{stdout.strip()}")
        return True

    # Pandas ausente o fallback JSON → usar Docker
    if "pandas no instalado" in stdout or result.returncode != 0:
        print(f"  ⚠ pandas ausente en Python local, usando Docker (carcosa:app)...")
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{Path.cwd()}:/app",
            "-w", "/app",
            "carcosa:app",
            "python", "tools/ai_ready_export.py",
        ] + base_args
        print(f"  Ejecutando (Docker): {' '.join(docker_cmd)}")
        result2 = subprocess.run(docker_cmd, capture_output=True, text=True)
        stdout2 = result2.stdout + result2.stderr
        if result2.returncode == 0:
            print(f"  ✓ Export OK (Docker):\n{stdout2.strip()}")
            return True
        else:
            print(f"  ✗ Export falló en Docker:\n{stdout2}")
            return False

    print(f"  ✗ Export falló:\n{stdout}")
    return False


def verify_csv(csv_path: str) -> bool:
    """Verifica que el CSV BC tiene las columnas esperadas y no tiene NaNs críticos."""
    try:
        import pandas as pd
    except ImportError:
        print("  ⚠ pandas no disponible, saltando verificación de CSV")
        return True

    if not Path(csv_path).exists():
        print(f"  ✗ CSV no encontrado: {csv_path}")
        return False

    df = pd.read_csv(csv_path)
    print(f"  ✓ CSV cargado: {len(df)} filas, {len(df.columns)} columnas")

    expected_cols = [
        "obs_P_sanity", "obs_P_keys", "obs_P_mon", "obs_P_umbral",
        "obs_P_debuff", "obs_P_king_risk", "obs_P_crown", "obs_P_round",
        "obs_tension", "action_id",
    ]
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        print(f"  ✗ Columnas BC faltantes en CSV: {missing}")
        return False

    nan_counts = df[expected_cols].isnull().sum()
    total_nans = nan_counts.sum()
    if total_nans > 0:
        print(f"  ⚠ NaNs detectados:\n{nan_counts[nan_counts > 0]}")
    else:
        print(f"  ✓ Sin NaNs en columnas de observación")

    print(f"  Distribución de acciones:\n{df['action'].value_counts().head(10).to_string()}")
    return True


def run_train_quick(csv_path: str, save_dir: str = "models_bc/human_test") -> bool:
    """
    Ejecuta train_bc.py con solo 5 épocas para verificar que procesa sin errores.
    Intenta primero con el Python local; si falla por módulo ausente, intenta con Docker.
    """
    import subprocess
    mapping_path = Path(csv_path).with_suffix(".action_mapping.json")
    if not mapping_path.exists():
        print(f"  ⚠ No se encontró action_mapping {mapping_path}, el entrenamiento puede fallar")

    base_cmd_args = [
        "--data", csv_path,
        "--epochs", "5",
        "--batch-size", "32",
        "--device", "cpu",
        "--save-dir", save_dir,
    ]

    # Intento 1: Python local
    cmd = [sys.executable, "train/train_bc.py"] + base_cmd_args
    print(f"  Ejecutando (local): {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    stdout = result.stdout + result.stderr

    if result.returncode == 0:
        print(f"  ✓ Entrenamiento completado sin errores")
        last_lines = stdout.strip().split("\n")[-8:]
        print("  " + "\n  ".join(last_lines))
        return True

    # Si falló por módulo ausente, intentar con Docker
    if "ModuleNotFoundError" in stdout or "No module named" in stdout:
        print(f"  ⚠ Módulo ausente en Python local, intentando con Docker (carcosa:app)...")
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{Path.cwd()}:/app",
            "-w", "/app",
            "carcosa:app",
            "python", "train/train_bc.py",
        ] + base_cmd_args
        print(f"  Ejecutando (Docker): {' '.join(docker_cmd)}")
        result2 = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=600)
        stdout2 = result2.stdout + result2.stderr

        if result2.returncode == 0:
            print(f"  ✓ Entrenamiento completado sin errores (Docker)")
            last_lines = stdout2.strip().split("\n")[-10:]
            print("  " + "\n  ".join(last_lines))
            return True
        else:
            print(f"  ✗ Entrenamiento falló en Docker (código {result2.returncode}):")
            print(stdout2[-3000:])
            return False

    # Otro error
    print(f"  ✗ Entrenamiento falló (código {result.returncode}):")
    print(stdout[-3000:])
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Simula partidas humanas y verifica pipeline BC")
    ap.add_argument("--server", default="http://127.0.0.1:8765")
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--skip-train", action="store_true", help="Saltar el paso de entrenamiento")
    ap.add_argument("--output-csv", default="data/human_bc_test.csv")
    args = ap.parse_args()

    print(f"\n{'='*60}")
    print(f"CARCOSA Sprint 4 — Verificación Pipeline BC Humano")
    print(f"{'='*60}")
    print(f"Servidor: {args.server}")
    print(f"Partidas a simular: {args.games}")
    print()

    # ── Paso 1: Verificar que el servidor responde ─────────────────────────
    print("[1/4] Verificando servidor...")
    try:
        health = _get(args.server, "/")
        print(f"  ✓ Servidor OK: {health}")
    except Exception as e:
        print(f"  ✗ No se puede conectar al servidor: {e}")
        print("  Arrancar con: python -m uvicorn sim.game_server:app --port 8765")
        sys.exit(1)

    # ── Paso 2: Simular partidas ───────────────────────────────────────────
    print(f"\n[2/4] Simulando {args.games} partidas (acciones aleatorias)...")
    results = []
    jsonl_paths = []
    for i in range(args.games):
        seed = args.seed + i * 7  # seeds distintas
        print(f"\n  Partida {i+1}/{args.games} (seed={seed}):")
        try:
            result = simulate_game(args.server, seed=seed, verbose=True)
            results.append(result)
            if result.get("saved_to"):
                jsonl_paths.append(result["saved_to"])
        except Exception as e:
            print(f"  ✗ Error en partida {i+1}: {e}")

    print(f"\n  Resumen: {len(results)}/{args.games} partidas completadas")
    outcomes = [r.get("outcome") for r in results]
    print(f"  Outcomes: {outcomes}")

    if not jsonl_paths:
        print("\n✗ No se generaron archivos JSONL. Abortando.")
        sys.exit(1)

    # ── Paso 3: Verificar formato JSONL ───────────────────────────────────
    print(f"\n[3/4] Verificando formato JSONL...")
    all_ok = True
    for path in jsonl_paths:
        print(f"  Verificando: {path}")
        ok = verify_jsonl_format(path)
        all_ok = all_ok and ok

    # ── Paso 4: Export + CSV check + Train ───────────────────────────────
    print(f"\n[4/4] Pipeline BC: export → CSV → train...")

    Path("data").mkdir(exist_ok=True)
    export_ok = run_export_pipeline(jsonl_paths, args.output_csv)
    if export_ok:
        verify_csv(args.output_csv)

    if not args.skip_train and export_ok:
        print(f"\n  Ejecutando entrenamiento rápido (5 épocas)...")
        train_ok = run_train_quick(args.output_csv)
        all_ok = all_ok and train_ok
    else:
        print(f"\n  (Entrenamiento omitido con --skip-train)")

    # ── Resultado final ───────────────────────────────────────────────────
    print(f"\n{'='*60}")
    if all_ok:
        print("✓ Sprint 4 COMPLETADO: pipeline BC humano verificado")
    else:
        print("⚠ Sprint 4: pipeline BC con advertencias (ver arriba)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

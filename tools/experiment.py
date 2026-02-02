#!/usr/bin/env python3
"""
Orquestador de experimentos para CARCOSA (MVP).

Flujo: simular -> exportar -> entrenar -> evaluar -> indexar
"""
from __future__ import annotations
import argparse
import subprocess
import json
import hashlib
import sys
from pathlib import Path
from datetime import datetime
import shutil

try:
    import yaml
except Exception as e:
    yaml = None


def compute_config_hash(cfg: dict) -> str:
    s = json.dumps(cfg, sort_keys=True).encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:8]


def resolve_device(device_cfg: str) -> str:
    if device_cfg == "auto":
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"
    return device_cfg


def run_subprocess(cmd, cwd: Path = None, env=None, capture: bool = False):
    print(f"$ {' '.join(cmd)}")
    res = subprocess.run([sys.executable, *cmd], cwd=cwd, env=env, capture_output=capture, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return res


def discover_latest_model(save_dir: Path) -> str | None:
    if not save_dir.exists():
        return None
    files = sorted(save_dir.glob("**/*_best.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(files[0]) if files else None


def aggregate_run_metrics(runs_dir: Path) -> dict:
    # Simple aggregator: read all .jsonl final lines
    import glob, json
    files = list(runs_dir.glob("**/*.jsonl"))
    if not files:
        return {}
    wins = 0
    steps = []
    keys = []
    sanities = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                lines = [l for l in fh.readlines() if l.strip()]
                if not lines:
                    continue
                last = json.loads(lines[-1])
                outcome = last.get("outcome")
                if outcome == "WIN":
                    wins += 1
                steps.append(last.get("step", 0))
                summary = last.get("summary_post", {})
                keys.append(summary.get("keys_in_hand", 0))
                sanities.append(summary.get("min_sanity", 0))
        except Exception:
            continue
    n = len(files)
    return {
        "winrate": wins / n if n else None,
        "avg_steps": sum(steps) / n if n else None,
        "avg_keys_end": sum(keys) / n if n else None,
        "avg_sanity_end": sum(sanities) / n if n else None,
        "n_runs": n,
    }


def main():
    ap = argparse.ArgumentParser(description="Run an experiment pipeline")
    ap.add_argument("--config", type=str, default="configs/experiment.default.yaml")
    ap.add_argument("--tag", type=str, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", type=str, default=None,
                    choices=[None, "sim", "export", "train", "eval", "index"]) 
    args = ap.parse_args()

    if yaml is None:
        print("PyYAML is required. Install with: pip install pyyaml")
        sys.exit(2)

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"Config not found: {cfg_path}")
        sys.exit(2)

    cfg = yaml.safe_load(cfg_path.read_text())
    # apply CLI tag override
    if args.tag:
        cfg.setdefault("experiment", {})["tag"] = args.tag

    # Resolve seeds vs n_episodes
    sim_cfg = cfg.get("simulation", {})
    seeds = sim_cfg.get("seeds")
    if not seeds:
        n = sim_cfg.get("n_episodes", 0)
        seeds = list(range(1, n + 1))
        sim_cfg["seeds"] = seeds

    # exp_id
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cfg_hash = compute_config_hash(cfg)
    tag = cfg.get("experiment", {}).get("tag", "default")
    exp_id = f"{ts}_{cfg_hash}_{tag}"

    # Prepare dirs
    out_root = Path(cfg.get("experiment", {}).get("output_root", "reports"))
    exp_dir = out_root / exp_id
    runs_root = Path(cfg.get("experiment", {}).get("runs_root", "runs"))
    data_root = Path(cfg.get("experiment", {}).get("data_root", "data"))
    models_root = Path(cfg.get("experiment", {}).get("models_root", "models"))

    exp_dir.mkdir(parents=True, exist_ok=True)

    # Save resolved config
    resolved_cfg_path = exp_dir / "config.resolved.yaml"
    resolved_json_path = exp_dir / "config.resolved.json"
    resolved_cfg_path.write_text(yaml.safe_dump(cfg))
    resolved_json_path.write_text(json.dumps(cfg, indent=2))

    summary = {
        "exp_id": exp_id,
        "tag": tag,
        "timestamp": ts,
        "git": {"commit": None, "branch": None},
        "config_hash": cfg_hash,
        "config_path": str(cfg_path),
        "config_resolved_path": str(resolved_cfg_path),
        "paths": {},
        "simulation": {},
        "results": {},
        "status": "started",
        "error": None,
    }

    # Try git info
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
        if commit.returncode == 0:
            summary["git"]["commit"] = commit.stdout.strip()
        if branch.returncode == 0:
            summary["git"]["branch"] = branch.stdout.strip()
    except Exception:
        pass

    try:
        # Stage: Simulation
        if args.only in (None, "sim") and cfg.get("simulation"):
            version_dir = str(runs_root / exp_id)
            seeds_cfg = cfg["simulation"].get("seeds", [])
            if args.dry_run:
                print("[DRY] would run simulations into", version_dir, "seeds=", seeds_cfg)
            else:
                # If default 1-5 requested and matches common case, use --all-seeds
                default_all = seeds_cfg == [1, 2, 3, 4, 5]
                if default_all:
                    run_subprocess(["tools/run_versioned.py", "--all-seeds", "--max-steps", str(cfg["simulation"]["max_steps"]), "--version-dir", version_dir])
                else:
                    # run per-seed to allow arbitrary seeds
                    for sd in seeds_cfg:
                        run_subprocess(["tools/run_versioned.py", "--seed", str(sd), "--max-steps", str(cfg["simulation"]["max_steps"]), "--version-dir", version_dir])
            summary["paths"]["runs_dir"] = version_dir
            summary["simulation"] = {
                "policy": cfg["simulation"].get("policy"),
                "policy_kwargs": cfg["simulation"].get("policy_kwargs"),
                "seeds": cfg["simulation"].get("seeds"),
                "max_steps": cfg["simulation"].get("max_steps"),
            }

        # Stage: Export
        dataset_path = None
        if args.only in (None, "export") and cfg.get("export", {}).get("enabled", False):
            exporter = cfg["export"].get("exporter", "ai_ready")
            out_csv = cfg["export"].get("out_csv", "bc_training_generated.csv")
            dataset_path = str(exp_dir / out_csv)
            if args.dry_run:
                print("[DRY] would export runs ->", dataset_path)
            else:
                # Use ai_ready_export.py
                runs_dir = Path(summary["paths"].get("runs_dir")) if summary.get("paths") else Path(runs_root / exp_id)
                # Expand JSONL list (shell globbing not available on Windows)
                input_files = [str(p) for p in runs_dir.glob("*.jsonl")] if runs_dir.exists() else []
                if not input_files:
                    raise RuntimeError(f"No run files found in {runs_dir}")
                cmd = ["tools/ai_ready_export.py", "--mode", "bc", "--output", dataset_path]
                # append --input multiple times
                for f in input_files:
                    cmd.extend(["--input", f])
                run_subprocess(cmd)
            summary["paths"]["dataset_path"] = dataset_path

        # Stage: Train
        model_path = None
        if args.only in (None, "train") and cfg.get("train", {}).get("mode") and cfg["train"]["mode"] != "none":
            mode = cfg["train"]["mode"]
            device = resolve_device(cfg.get("train", {}).get("device", "cpu"))
            model_save_dir = exp_dir / "models"
            model_save_dir.mkdir(parents=True, exist_ok=True)

            if mode == "bc":
                # Check torch availability; training requires torch. If missing, skip training (smoke friendly).
                try:
                    import torch  # type: ignore
                    HAS_TORCH = True
                except Exception:
                    HAS_TORCH = False

                if not HAS_TORCH:
                    print("PyTorch not available; skipping BC training in this environment.")
                    summary["paths"]["model_path"] = None
                else:
                    bc = cfg["train"].get("bc", {})
                    epochs = bc.get("epochs", 1)
                    batch = bc.get("batch_size", 64)
                    lr = bc.get("lr", 1e-3)
                    if args.dry_run:
                        print(f"[DRY] would train BC: data={dataset_path} epochs={epochs} device={device}")
                    else:
                        cmd = [
                            "train/train_bc.py",
                            "--data", dataset_path or str(data_root / "bc_training.csv"),
                            "--epochs", str(epochs),
                            "--batch-size", str(batch),
                            "--lr", str(lr),
                            "--save-dir", str(model_save_dir),
                            "--log-dir", str(exp_dir / "runs"),
                            "--device", "cpu" if device == "cpu" else "cuda",
                        ]
                        run_subprocess(cmd)
                model_path = discover_latest_model(model_save_dir)
            elif mode == "rl":
                rl = cfg["train"].get("rl", {})
                timesteps = rl.get("timesteps", 20000)
                if args.dry_run:
                    print(f"[DRY] would train RL: timesteps={timesteps}")
                else:
                    cmd = [
                        "train/train_rl.py",
                        "train",
                        "--algo", "ppo",
                        "--timesteps", str(timesteps),
                        "--save-dir", str(model_save_dir),
                    ]
                    run_subprocess(cmd)
                model_path = discover_latest_model(model_save_dir)

            summary["paths"]["model_path"] = model_path

        # Stage: Eval
        if args.only in (None, "eval") and cfg.get("eval", {}).get("enabled", False):
            ep = cfg["eval"].get("n_episodes", 10)
            max_steps = cfg["eval"].get("max_steps", 300)
            if cfg["eval"].get("policy") == "trained" and summary["paths"].get("model_path"):
                model_for_eval = summary["paths"]["model_path"]
                if args.dry_run:
                    print(f"[DRY] would evaluate model {model_for_eval} for {ep} episodes")
                else:
                    run_subprocess(["train/evaluate.py", "--model", model_for_eval, "--episodes", str(ep), "--device", "cpu"]) 
                    # Note: evaluate prints results — we keep it simple

        # Aggregate metrics
        metrics = aggregate_run_metrics(Path(summary["paths"].get("runs_dir", str(runs_root))))
        summary["results"] = metrics
        summary["status"] = "ok"

    except Exception as e:
        summary["status"] = "failed"
        summary["error"] = str(e)
        exp_dir.mkdir(parents=True, exist_ok=True)
        with open(exp_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print("Experiment failed:", e)
        sys.exit(1)

    # Save summary
    with open(exp_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Generate simple markdown
    md = [f"# Experiment {exp_id}", "", f"Tag: {tag}", f"Timestamp: {ts}", "", "## Metrics", ""]
    for k, v in summary.get("results", {}).items():
        md.append(f"- {k}: {v}")
    (exp_dir / "summary.md").write_text("\n".join(md))

    # Call indexer
    try:
        run_subprocess(["tools/index_experiments.py", str(out_root)])
    except Exception:
        print("Index update failed (non-fatal)")

    print(f"Experiment completed: {exp_dir}")


if __name__ == "__main__":
    main()

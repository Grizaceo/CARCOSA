import json
import subprocess
import sys
from pathlib import Path
import tempfile


def test_smoke_pipeline(tmp_path):
    # Create minimal config overriding defaults
    cfg = {
        "experiment": {
            "tag": "smoke"
        },
        "simulation": {
            "seeds": [1],
            "max_steps": 50
        },
        "export": {"enabled": True, "out_csv": "bc_smoke.csv"},
        "train": {"mode": "bc", "device": "cpu", "bc": {"epochs": 1, "batch_size": 8, "lr": 1e-3}},
        "eval": {"enabled": True, "n_episodes": 1, "max_steps": 50}
    }

    cfg_path = tmp_path / "exp_smoke.yaml"
    import yaml
    cfg_path.write_text(yaml.safe_dump(cfg))

    reports_root = tmp_path / "reports"

    # Run experiment
    cmd = [sys.executable, "tools/experiment.py", "--config", str(cfg_path)]
    res = subprocess.run(cmd, cwd=Path.cwd(), capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)
    assert res.returncode == 0

    # Find generated reports
    # There should be a single directory in tmp reports if the script used default output path
    # Since the script writes to reports/, search under repository reports
    repo_reports = Path("reports")
    assert repo_reports.exists()
    # Index CSV should exist
    csv = repo_reports / "experiments.csv"
    assert csv.exists()

    # The latest summary.json should exist
    dirs = [d for d in repo_reports.iterdir() if d.is_dir()]
    assert dirs
    latest = sorted(dirs)[-1]
    summary = latest / "summary.json"
    assert summary.exists()
    data = json.loads(summary.read_text())
    assert data.get("status") == "ok"

# Runs Organization & Versioning System

## Overview

To avoid contaminating simulation data with code changes, the CARCOSA project uses a versioned runs system. Each code version (identified by git commit hash) gets its own isolated directory for runs.

## Directory Structure

```
CARCOSA/
|-- runs/                          # Current runs for the active code state
|   `-- runs_v<hash>_<branch>_<ts>/ # Versioned output (current)
|       |-- metadata.json
|       |-- seed1.jsonl
|       |-- seed2.jsonl
|       |-- seed3.jsonl
|       |-- seed4.jsonl
|       `-- seed5.jsonl
|
|-- docs/historics/                # Archived artifacts (past code states)
|   |-- runs/                       # Past versioned runs (moved here)
|   |-- logs/                       # Old debug logs
|   `-- reproduce/                  # Old reproduce_*.py scripts
|
|-- tools/run_versioned.py          # Run simulations with versioning
`-- tools/analyze_version.py        # Analyze runs from a version
```

## Naming Convention

Version directories are named:
```
runs/runs_v{COMMIT}_{BRANCH}_{TIMESTAMP}
```

Example: `runs/runs_v4fee5ba_main_20260112_161915`
- `4fee5ba` = Git commit hash (short form, 7 chars)
- `main` = Branch name
- `20260112_161915` = ISO date + time

Each version directory contains:
- `metadata.json` - Metadata about the version
- `seed{1-5}.jsonl` - Individual run files (one per seed)

## Usage

### Generate Runs for Current Code

Generate all 5 seeds with automatic versioning:
```bash
python tools/run_versioned.py --all-seeds
```

Generate specific seed:
```bash
python tools/run_versioned.py --seed 3
```

Custom version name:
```bash
python tools/run_versioned.py --all-seeds --version-dir "runs_custom_name"
```

### Analyze Runs from a Version

Analyze the latest version:
```bash
python tools/analyze_version.py
```

Analyze a specific version:
```bash
python tools/analyze_version.py runs/runs_v4fee5ba_main_20260112_161915
```

## Archiving Old Runs

To archive an old version directory:
```bash
mv runs/runs_v<old_hash>_* docs/historics/runs/
```

## Notes

- `runs/` is for current simulations from the active code state.
- Move older runs to `docs/historics/runs/` to preserve snapshots.
- Logs and one-off reproduce scripts live in `docs/historics/`.
- Each analysis automatically detects the latest version if none specified.

---

Created: 2026-01-12 (After RNG bias fix)
Updated: 2026-01-27
Purpose: Prevent data contamination from code changes

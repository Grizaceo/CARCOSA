# 📊 Runs Organization & Versioning System

## Overview

To avoid contaminating simulation data with code changes, the CARCOSA project now uses a **versioned runs system**. Each code version (identified by git commit hash) gets its own isolated directory for runs.

## Directory Structure

```
CARCOSA/
├── runs_archive/                    # Historical runs (organized by version)
│   ├── v0_original_biased_rng/      # Original runs (with d6 bias)
│   └── v1_fixed_d6_randomization/   # Previous fix versions
│
├── runs/                            # Ad-hoc runs (latest version)
│   └── runs_v4fee5ba_main_20260112_161915/
│       ├── metadata.json            # Commit hash, branch, timestamp
│       ├── seed1.jsonl              # 5 seed runs (1-5)
│       ├── seed2.jsonl
│       ├── seed3.jsonl
│       ├── seed4.jsonl
│       └── seed5.jsonl
│
├── tools/run_versioned.py                 # Script to run simulations with versioning
└── tools/analyze_version.py               # Script to analyze runs from a version
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

## Benefits

1. **Clean Data:** No contamination from different code states
2. **Traceability:** Exact git commit linked to each run set
3. **Comparison:** Easy to compare results across code versions
4. **Organization:** Historical versions preserved in `runs_archive/`
5. **Automation:** Automatic commit hash and timestamp in directory name

## Example Workflow

```bash
# Make code changes
git add . && git commit -m "Fix d6 randomization"

# Generate fresh runs
python tools/run_versioned.py --all-seeds
# Creates: runs/runs_v<new_hash>_main_<timestamp>/

# Analyze immediately
python tools/analyze_version.py
# Shows d6 distribution for current code version

# Make more changes
git add . && git commit -m "Add new feature"

# Generate new runs (automatic version isolation)
python tools/run_versioned.py --all-seeds
# Creates: runs/runs_v<new_hash>_main_<timestamp>/

# Compare versions
python tools/analyze_version.py runs/runs_v<old_hash>_...
python tools/analyze_version.py runs/runs_v<new_hash>_...
```

## Archiving Old Runs

To archive an old version directory:
```bash
mv runs/runs_v<old_hash>_* runs_archive/v2_description/
```

## Notes

- The old `runs/` directory has been deprecated
- All new runs should use `tools/run_versioned.py` 
- Old biased runs are archived in `runs_archive/v0_original_biased_rng/`
- Each analysis automatically detects the latest version if none specified

---

**Created:** 2026-01-12 (After RNG bias fix)
**Purpose:** Prevent data contamination from code changes

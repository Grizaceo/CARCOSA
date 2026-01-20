# WORKFLOW - After Code Changes

## Quick Reference

When you modify code and want to test new simulations.

Important: WSL uses a separate Linux filesystem. Keep Windows paths and WSL paths separate. These commands assume a WSL clone at /home/<user>/CARCOSA (adjust as needed).

### 1) Make Code Changes

Windows PowerShell
```powershell
# Edit files as needed
git add .
git commit -m "Your change description"
```

WSL bash
```bash
# Edit files as needed
git add .
git commit -m "Your change description"
```

### 2) Run Tests

Windows PowerShell
```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -q
```

WSL bash
```bash
cd /home/<user>/CARCOSA
source .venv/bin/activate
python -m pytest tests/ -q
```

Expected: 67 passed

### 3) Generate New Runs

Windows PowerShell
```powershell
.\.venv\Scripts\Activate.ps1
python tools/run_versioned.py --all-seeds
```

WSL bash
```bash
cd /home/<user>/CARCOSA
source .venv/bin/activate
python tools/run_versioned.py --all-seeds
```

This creates a new versioned directory with the git commit hash.
Example output:
```
Results saved to: runs/runs_v<new_hash>_main_20260112_162100/
```

### 4) Analyze Results

Windows PowerShell
```powershell
.\.venv\Scripts\Activate.ps1
python tools/analyze_version.py
```

WSL bash
```bash
cd /home/<user>/CARCOSA
source .venv/bin/activate
python tools/analyze_version.py
```

### 5) (Optional) Compare with Previous Version

Windows PowerShell
```powershell
.\.venv\Scripts\Activate.ps1
python tools/compare_versions.py
```

WSL bash
```bash
cd /home/<user>/CARCOSA
source .venv/bin/activate
python tools/compare_versions.py
```

---

## Important Notes

- Every run set gets a unique directory named: runs/runs_v{COMMIT}_{BRANCH}_{TIMESTAMP}
- Old runs are preserved in runs_archive/ for comparison
- RNG is deterministic (same seed = same sequence)
- d6 distribution should be uniform (p-value > 0.05)

---

## For Debugging

### Check RNG Distribution

Windows PowerShell
```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest tests/test_rng_distribution.py -v
```

WSL bash
```bash
cd /home/<user>/CARCOSA
source .venv/bin/activate
python -m pytest tests/test_rng_distribution.py -v
```

### Check Specific Version

Windows PowerShell
```powershell
.\.venv\Scripts\Activate.ps1
python tools/analyze_version.py runs/runs_v<hash>_main_<time>/
```

WSL bash
```bash
cd /home/<user>/CARCOSA
source .venv/bin/activate
python tools/analyze_version.py runs/runs_v<hash>_main_<time>/
```

### See All Versions

Windows PowerShell
```powershell
.\.venv\Scripts\Activate.ps1
python tools/compare_versions.py
```

WSL bash
```bash
cd /home/<user>/CARCOSA
source .venv/bin/activate
python tools/compare_versions.py
```

---

## Commands Reference

| Command | Purpose |
|---------|---------|
| python tools/run_versioned.py --all-seeds | Generate 5 runs (auto-versioned) |
| python tools/run_versioned.py --seed 3 | Generate single seed run |
| python tools/analyze_version.py | Analyze latest version |
| python tools/analyze_version.py <dir> | Analyze specific version |
| python tools/compare_versions.py | Compare all versions |
| python -m pytest tests/ -q | Run test suite |
| python -m pytest tests/test_rng_distribution.py -v | Test RNG uniformity |

---

## Command Usage Format (for future edits)

When adding or editing commands in this file, always include both variants and keep Windows and WSL paths separate.

Windows PowerShell
```powershell
.\.venv\Scripts\Activate.ps1
<COMMAND>
```

WSL bash
```bash
cd /home/<user>/CARCOSA
source .venv/bin/activate
<COMMAND>
```

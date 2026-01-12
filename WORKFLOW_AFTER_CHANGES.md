# 🔄 WORKFLOW - After Code Changes

## Quick Reference

When you modify code and want to test new simulations:

### 1. Make Code Changes
```bash
# Edit files as needed
git add .
git commit -m "Your change description"
```

### 2. Run Tests
```bash
python -m pytest tests/ -q
```
✓ Should see `67 passed`

### 3. Generate New Runs
```bash
python run_versioned.py --all-seeds
```
This automatically creates a **new versioned directory** with git commit hash.

Example output:
```
Results saved to: runs_v<new_hash>_main_20260112_162100/
```

### 4. Analyze Results
```bash
python analyze_version.py
```

### 5. (Optional) Compare with Previous Version
```bash
python compare_versions.py
```

---

## Important Notes

### Automatic Versioning
- **Every run set gets a unique directory** named: `runs_v{COMMIT}_{BRANCH}_{TIMESTAMP}`
- This prevents accidentally mixing data from different code versions
- Old runs are preserved in `runs_archive/` for comparison

### Data Integrity
- ✅ d6 distribution is uniform (p=0.290 after fix)
- ✅ RNG is deterministic (same seed = same sequence)
- ✅ All 6 d6 effects appear equally (before: d6=3,4,6 never appeared)

### Each Run Contains
```
runs_v<hash>_main_<time>/
├── metadata.json        # Commit hash, branch, timestamp
├── seed1.jsonl          # ~110-250 steps per game
├── seed2.jsonl
├── seed3.jsonl
├── seed4.jsonl
└── seed5.jsonl
```

### Analysis Output
```
✓ Total rolls across 5 seeds: ~72 d6 rolls
✓ Chi-square p-value: >0.05 means UNIFORM
✓ All 6 values should appear (no more d6=0%)
```

---

## Example Workflow

### Session 1: Initial Fix
```bash
# Code changes made to fix d6 bias
git commit -m "Fix d6 randomization in transition.py"
python -m pytest tests/ -q      # 67 passing ✓
python run_versioned.py --all-seeds
python analyze_version.py       # p=0.290, UNIFORM ✓
```

### Session 2: Add New Feature
```bash
# New code added
git commit -m "Add new King ability"
python -m pytest tests/ -q      # Still 67 passing ✓
python run_versioned.py --all-seeds
# Creates: runs_v<NEW_HASH>_main_<time>/
python analyze_version.py       # Compare with previous
```

### Session 3: Compare Versions
```bash
# Want to see if new code changed game balance
python compare_versions.py
# Shows table:
#   Commit | Branch | Rolls | Chi² | P-value | Uniform?
#   ──────────────────────────────────────────────────
#   hash1  | main   |  72   | 6.17 | 0.2903  | ✓ YES
#   hash2  | main   |  71   | 5.89 | 0.3156  | ✓ YES
```

---

## For Debugging

### Check RNG Distribution
```bash
# Verify RNG produces uniform d6 in tests
python -m pytest tests/test_rng_distribution.py -v
```

### Check Specific Version
```bash
python analyze_version.py runs_v<hash>_main_<time>/
```

### See All Versions
```bash
python compare_versions.py
```

---

## Directory Organization

```
Current Code Version      Archived Old Versions
─────────────────────     ─────────────────────
runs_v4fee5ba.../         runs_archive/
├── metadata.json         ├── v0_original_biased_rng/
├── seed1.jsonl           └── v1_previous_version/
├── seed2.jsonl
├── seed3.jsonl
├── seed4.jsonl
└── seed5.jsonl
```

---

## Commands Reference

| Command | Purpose |
|---------|---------|
| `python run_versioned.py --all-seeds` | Generate 5 runs (auto-versioned) |
| `python run_versioned.py --seed 3` | Generate single seed run |
| `python analyze_version.py` | Analyze latest version |
| `python analyze_version.py <dir>` | Analyze specific version |
| `python compare_versions.py` | Compare all versions |
| `python -m pytest tests/ -q` | Run test suite |
| `python -m pytest tests/test_rng_distribution.py -v` | Test RNG uniformity |

---

## Expected Results (After Fix)

✅ **Test Suite**
- 67/67 tests passing
- No regressions from code changes

✅ **d6 Distribution**
- All 6 values appear (not 0%)
- Chi-square p-value > 0.05
- Ratios near 1.0x (each value ~16.7%)

✅ **Game Balance**
- Outcomes (WIN/LOSE/TIMEOUT) should be stable
- Sanity distribution should be consistent
- Monster spawning should be random

---

**Last Updated:** January 12, 2026  
**System Version:** runs_v4fee5ba (RNG fix + versioning)

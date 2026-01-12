# 📚 CARCOSA Documentation Index

## Quick Start

### I Just Want to Run Simulations
→ See [WORKFLOW_AFTER_CHANGES.md](WORKFLOW_AFTER_CHANGES.md) - **Start here!**

### I Want to Understand the RNG Fix
→ See [RNG_FIX_REPORT.md](RNG_FIX_REPORT.md) - Technical details

### I Want to Know How Runs Are Organized
→ See [RUNS_ORGANIZATION.md](RUNS_ORGANIZATION.md) - System architecture

---

## Complete Documentation Map

### 🎯 Project Overview
- **[README.md](README.md)** - Main project readme
- **[SESSION_SUMMARY.md](SESSION_SUMMARY.md)** - What was accomplished this session

### 🔧 Technical Details
- **[RNG_FIX_REPORT.md](RNG_FIX_REPORT.md)** (12 KB)
  - Root cause analysis
  - Solution implementation
  - Before/after comparison
  - Impact on game mechanics

### 📊 Simulations & Analysis
- **[RUNS_ORGANIZATION.md](RUNS_ORGANIZATION.md)** (3 KB)
  - Directory structure
  - Versioning system
  - How to use analysis tools

- **[WORKFLOW_AFTER_CHANGES.md](WORKFLOW_AFTER_CHANGES.md)** (4 KB)
  - Step-by-step workflow
  - Command reference
  - Expected results

### 📖 Game Rules
- **[docs/Carcosa_Canon_P0_extracted.md](docs/Carcosa_Canon_P0_extracted.md)** - P0 Canonical rules
- **[docs/Carcosa_Libro_Tecnico_v0_1_extracted.md](docs/Carcosa_Libro_Tecnico_v0_1_extracted.md)** - Technical book

### 📝 Reports & Analysis
- **[AUDIT_P0_REPORT.md](docs/AUDIT_P0_REPORT.md)** - P0 mechanics audit
- **[VALIDATION_REPORT.md](VALIDATION_REPORT.md)** - Test validation
- **[NOTES.md](NOTES.md)** - Development notes

---

## Tools Overview

### Simulation Management
| Tool | Purpose | Usage |
|------|---------|-------|
| `run_versioned.py` | Generate versioned runs | `python run_versioned.py --all-seeds` |
| `analyze_version.py` | Analyze d6 distribution | `python analyze_version.py` |
| `compare_versions.py` | Compare multiple versions | `python compare_versions.py` |

### Testing
| Command | Purpose |
|---------|---------|
| `pytest tests/ -q` | Run all 67 tests |
| `pytest tests/test_rng_distribution.py -v` | Test RNG uniformity |
| `pytest tests/test_p0_canon.py -v` | Test canonical P0 rules |

### Analysis Tools (Legacy)
| Tool | Purpose |
|------|---------|
| `tools/analyze_d6_distribution.py` | Legacy d6 analysis |
| `tools/check_inconsistencies.py` | Detect state errors |
| `tools/ai_ready_export.py` | Export data for ML |

---

## Key Findings

### ✅ RNG Bias Fixed
- **Before:** d6=1 at 78.7% (expected 16.7%)
- **After:** All values ~16.7% (chi-square p=0.290)

### ✅ Test Suite Robust
- **Total:** 67/67 passing
- **New:** 4 RNG uniformity tests
- **Fixed:** 7 previously failing tests

### ✅ Runs Organized
- **Versioned:** Each commit gets unique directory
- **Archived:** Old runs preserved (27 files)
- **Isolated:** No data contamination between versions

---

## Repository Structure

```
CARCOSA/
├── engine/                  # Core game engine
│   ├── board.py            # P0.1: Adjacencies
│   ├── state.py            # Game state
│   ├── transition.py        # P0.2-P0.5: Mechanics
│   ├── rng.py              # Deterministic RNG ✨ FIXED
│   ├── legality.py         # Action generation ✨ FIXED
│   ├── config.py           # Configuration
│   └── effects/            # Status effects
│
├── sim/                     # Simulation & AI
│   ├── runner.py           # Main loop ✨ FIXED
│   ├── policies.py         # King & Player AI
│   └── metrics.py          # Logging ✨ FIXED
│
├── tests/                   # Test suite (67 tests)
│   ├── test_p0_canon.py    # P0 mechanics
│   ├── test_p0_updates.py  # P0 updates
│   ├── test_rng_distribution.py  # ✨ NEW: RNG tests
│   └── [11 more test files]
│
├── tools/                   # Development utilities
│   ├── run_versioned.py          # ✨ NEW
│   ├── analyze_version.py        # ✨ NEW
│   ├── compare_versions.py       # ✨ NEW
│   ├── analyze_d6_distribution.py
│   └── [more tools]
│
├── runs_v4fee5ba_main_20260112_161915/  # Current version runs
├── runs_archive/                         # Old versions (27 runs)
│
├── docs/                    # Documentation
├── DOCUMENTATION_INDEX.md   # 👈 You are here
├── RNG_FIX_REPORT.md       # Technical fix report
├── RUNS_ORGANIZATION.md    # Runs system doc
├── SESSION_SUMMARY.md      # This session summary
├── WORKFLOW_AFTER_CHANGES.md # How to use going forward
├── README.md               # Main readme
└── pyproject.toml          # Project config

```

---

## Common Tasks

### "I want to run tests"
```bash
python -m pytest tests/ -q
# See: README.md, WORKFLOW_AFTER_CHANGES.md
```

### "I want to generate simulation runs"
```bash
python run_versioned.py --all-seeds
# See: RUNS_ORGANIZATION.md, WORKFLOW_AFTER_CHANGES.md
```

### "I want to analyze d6 distribution"
```bash
python analyze_version.py
# See: RNG_FIX_REPORT.md, RUNS_ORGANIZATION.md
```

### "I want to understand the RNG bias fix"
→ See: **RNG_FIX_REPORT.md**

### "I want to compare code versions"
```bash
python compare_versions.py
# See: RUNS_ORGANIZATION.md
```

### "I want to modify code and test"
→ See: **WORKFLOW_AFTER_CHANGES.md**

---

## Latest Changes (This Session)

✨ **Major Fixes:**
- Fixed critical d6 bias (χ² p=0.290, UNIFORM ✓)
- Updated 7 tests that expected old action format
- Added 4 new RNG uniformity tests

✨ **New Tools:**
- `run_versioned.py` - Versioned run generation
- `analyze_version.py` - Version-specific analysis
- `compare_versions.py` - Cross-version comparison

✨ **New Documentation:**
- `RNG_FIX_REPORT.md` - Technical details
- `RUNS_ORGANIZATION.md` - System architecture
- `SESSION_SUMMARY.md` - Session work summary
- `WORKFLOW_AFTER_CHANGES.md` - Usage guide (IMPORTANT!)
- `DOCUMENTATION_INDEX.md` - This file

📊 **Results:**
- 67/67 tests passing
- d6 uniform across all values
- Runs automatically versioned by git commit
- Old biased runs archived and preserved

---

## Status

✅ **Production Ready**
- All tests passing
- RNG bias fixed and verified
- Runs organization system in place
- Documentation complete

📅 **Last Updated:** January 12, 2026, 16:19 UTC
🔗 **Commit:** 4fee5ba (RNG d6 fix + runs organization)

---

**Start with:** [WORKFLOW_AFTER_CHANGES.md](WORKFLOW_AFTER_CHANGES.md) if you're new!

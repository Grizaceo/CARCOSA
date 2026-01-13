# CARCOSA - Core Simulation Engine (P0 Canonical)

A deterministic game engine for CARCOSA (P0 core), ready for iteration.

## Installation (WSL)

### Prerequisites
- Windows 10/11 with WSL 2 (Ubuntu 22.04+)
- Python 3.11+
- pip

### Setup

From **Windows PowerShell** or **Command Prompt**, navigate to the repo and run:

```powershell
wsl bash -c "cd /home/gris/CARCOSA && python -m pip install -e ."
```

Or inside **WSL bash terminal** directly:

```bash
cd /home/gris/CARCOSA
python -m pip install -e .
```

## Running Tests

From **Windows PowerShell**, run the full test suite:

```powershell
wsl bash -c "cd /home/gris/CARCOSA && source .venv/bin/activate && PYTHONPATH=/home/gris/CARCOSA pytest -q"
```

Or inside **WSL bash terminal**:

```bash
cd /home/gris/CARCOSA
source .venv/bin/activate
export PYTHONPATH=/home/gris/CARCOSA:$PYTHONPATH
pytest -q
```

## Project Structure

```
engine/          # Core simulation engine
  board.py          # P0.1: Canonical room adjacencies (neighbors)
  config.py         # Configuration constants (KING_PRESENCE_START_ROUND, etc.)
  state.py          # Game state dataclasses
  transition.py     # P0.2-P0.5: Game logic transitions
  types.py          # Type definitions
  rng.py            # Deterministic RNG with seed
  effects/          # Card/effect system (WIP)

sim/              # Simulation & AI policies
  runner.py         # Simulation runner
  policies.py       # Player policies
  metrics.py        # Metrics tracking

tests/            # Test suite (65 tests)
  test_p0_canon.py  # P0 canonical tests (P0.1-P0.5)
  test_p0_updates.py  # P0 updates (keys, attract, presence)
  test_*.py         # Other functional tests

tools/            # Development utilities
  setup/           # Historical implementation scripts
  debug/           # Debugging tools
  validate/        # Validation scripts

docs/             # Canon documentation
  Carcosa_Libro_Tecnico_CANON.md           # Canon (primary source of truth)
  Carcosa_Libro_Tecnico_CANON_LEGACY.pdf   # Legacy PDF reference
  Carcosa_Canon_P0_extracted.md            # P0 canonical rules (supporting)
```

## Running Simulations

The simulator uses **versioned runs** to ensure clean data isolation between code versions.

### Generate Runs

Generate 5 seed runs for the current code version:

```bash
# Windows PowerShell
wsl bash -c "cd /home/gris/CARCOSA && source .venv/bin/activate && python tools/run_versioned.py --all-seeds"

# WSL bash
python tools/run_versioned.py --all-seeds
```

This creates a directory like `runs/runs_v4fee5ba_main_20260112_161915/` with:
- `metadata.json` - Commit hash, branch, timestamp
- `seed{1-5}.jsonl` - 5 complete game simulations

### Analyze Runs

Analyze d6 distribution (RNG uniformity):

```bash
# Latest version
python tools/analyze_version.py

# Specific version
python tools/analyze_version.py runs/runs_v4fee5ba_main_20260112_161915

# Compare multiple versions
python tools/compare_versions.py
```

### Run Organization

- **`runs/runs_v{COMMIT}_{BRANCH}_{TIMESTAMP}/`** - Current code version runs
- **`runs_archive/`** - Archived runs from previous code versions

See [docs/RUNS_ORGANIZATION.md](docs/RUNS_ORGANIZATION.md) for detailed structure.

## Running Specific Test Classes

```bash
# P0.1 - Canonical adjacencies (R1<->R2, R3<->R4)
pytest tests/test_p0_canon.py::TestP01Adjacencies -v

# P0.2 - King expel (move to stair room in adjacent floor)
pytest tests/test_p0_canon.py::TestP02ExpelFromFloor -v

# P0.3 - Stair reroll (1d4 per floor at end of round)
pytest tests/test_p0_canon.py::TestP03StairsReroll -v

# P0.4 - Event on crossing to -5 (key/object destruction, sanity loss for others)
pytest tests/test_p0_canon.py::TestP04MinusFiveEvent -v

# P0.5 - King presence damage (per round)
pytest tests/test_p0_canon.py::TestP05KingPresenceDamage -v
```

## Core Features (P0)

### P0.1 - Canonical Adjacencies
- **File**: `engine/board.py::neighbors()`
- **Rule**: Rooms connect to corridor (1 move), plus direct connections R1<->R2 and R3<->R4
- **Tests**: 6 tests in `TestP01Adjacencies`

### P0.2 - King Expel (Move by Stairs)
- **File**: `engine/transition.py::_expel_players_from_floor()`
- **Rule**: Players on King's floor move to stair room in adjacent floor
  - F1 -> F2 stair room
  - F2 -> F1 stair room
  - F3 -> F2 stair room
- **Tests**: 4 tests in `TestP02ExpelFromFloor`

### P0.3 - Stair Reroll
- **File**: `engine/transition.py::_roll_stairs()`
- **Rule**: Each floor rerolls stairs (1d4 per piso) at end of round using seeded RNG
- **Tests**: 3 tests in `TestP03StairsReroll` (determinism verified)

### P0.4 - Event on Crossing to -5
- **File**: `engine/transition.py::_apply_minus5_transitions()`
- **Rules**:
  - Destroy player's keys and objects when crossing to <= -5
  - Other players lose 1 sanity when someone crosses
  - Player at -5 has 1 action per turn; restores 2 actions when leaving to -4
  - Event fires only once on crossing (tracked by `at_minus5` flag)
- **Tests**: 9 tests (basic + keys coherence + multiple players)

### P0.4b - Attract (Atraer) with False King Exception
- **File**: `engine/transition.py::_attract_players_to_floor()`
- **Rule**: All players move to corridor of specified floor, EXCEPT those on the crown holder floor
- **State**: `GameState.flags["CROWN_HOLDER"]` (player id)
- **Tests**: 3 tests in `TestP04bAttractWithFalseKing`

### P0.5 - King Presence Damage (REVISED TABLE)
- **File**: `engine/transition.py::_presence_damage_for_round()`
- **Canon Table** (confirmed):
  - Rounds 1-3: 1 damage per round
  - Rounds 4-6: 2 damage per round
  - Rounds 7-9: 3 damage per round
  - Rounds 10+: 4 damage per round
- **Application**: Only to players on King's floor
- **Tests**: 15 tests (4 in old P05, 12 parametrized in test_p0_updates)

## Test Summary

- **Total**: 65 tests passing OK
  - P0.1 Adjacencies: 6 tests
  - P0.2 Expel: 4 tests
  - P0.3 Stairs: 3 tests
  - P0.4a Minus5: 9 tests (+ keys coherence)
  - P0.4b Attract: 3 tests
  - P0.5 Presence: 15 tests (updated table)
  - Other integration: 25 tests

All tests are **deterministic**, use **fixed seeds**, and **no warnings**.

## P0 Implementation Status

| Feature | File | Implementation | Tests | Status |
|---------|------|---|---|---|
| P0.1 Adjacencies | `engine/board.py` | Canonical R1<->R2, R3<->R4 | 6 | OK |
| P0.2 Expel | `engine/transition.py` | Floor mapping to stairs | 4 | OK |
| P0.3 Stairs Reroll | `engine/transition.py` | 1d4 per floor RNG | 3 | OK |
| P0.4a Event -5 | `engine/transition.py` | Key destruction + counter | 9 | OK |
| P0.4b Attract | `engine/transition.py` | With false_king exception | 3 | OK |
| P0.5 Presence | `engine/transition.py` | Canon table (R1-3->1, R4-6->2, ...) | 15 | OK |

## Development Utilities

See `tools/README.md` for:
- **Setup scripts**: Historical implementation records
- **Debug tools**: Step-by-step debugging
- **Validation**: Syntax, imports, and quick P0 checks

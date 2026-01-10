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

## Running Specific Test Classes

```bash
# P0.1 - Canonical adjacencies (R1↔R2, R3↔R4)
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

## Project Structure

```
engine/
  ├── board.py          # P0.1: Canonical adjacencies (neighbors)
  ├── config.py         # Configuration constants (KING_PRESENCE_START_ROUND, etc.)
  ├── state.py          # Game state dataclasses
  ├── transition.py     # P0.2-P0.5: Game logic transitions
  ├── types.py          # Type definitions
  ├── rng.py            # Deterministic RNG with seed
  └── effects/          # Card/effect system (WIP)

sim/
  ├── runner.py         # Simulation runner
  ├── policies.py       # Player policies
  └── metrics.py        # Metrics tracking

tests/
  ├── test_p0_canon.py  # P0 canonical tests (P0.1-P0.5)
  └── test_*.py         # Other functional tests

docs/
  ├── Carcosa_Canon_P0_extracted.md          # Canon (primary source of truth)
  └── Carcosa_Libro_Tecnico_v0_1_extracted.md  # Technical manual (secondary)
```

## Core Features (P0)

### P0.1 - Canonical Adjacencies
- **File**: `engine/board.py::neighbors()`
- **Rule**: Rooms connect to corridor (1 move), plus direct connections R1↔R2 and R3↔R4
- **Tests**: 6 tests in `TestP01Adjacencies`

### P0.2 - King Expel (Move by Stairs)
- **File**: `engine/transition.py::_expel_players_from_floor()`
- **Rule**: Players on King's floor move to stair room in adjacent floor
  - F1 → F2 stair room
  - F2 → F1 stair room
  - F3 → F2 stair room
- **Tests**: 4 tests in `TestP02ExpelFromFloor`

### P0.3 - Stair Reroll
- **File**: `engine/transition.py::_roll_stairs()`
- **Rule**: Each floor rerolls stairs (1d4 per piso) at end of round using seeded RNG
- **Tests**: 3 tests in `TestP03StairsReroll` (determinism verified)

### P0.4 - Event on Crossing to -5
- **File**: `engine/transition.py::_apply_minus5_transitions()`
- **Rules**:
  - Destroy player's keys and objects when crossing to ≤ -5
  - Other players lose 1 sanity when someone crosses
  - Player at -5 has 1 action per turn; restores 2 actions when leaving to -4
  - Event fires only once on crossing (tracked by `at_minus5` flag)
- **Tests**: 6 tests in `TestP04MinusFiveEvent` (crossing, non-repetition, recovery)

### P0.5 - King Presence Damage
- **File**: `engine/transition.py::_presence_damage_for_round()`
- **Rule**: Round 1: 0 damage. Round 2+: 1 damage per round (only to players on King's floor)
- **Parametrization**: `Config.KING_PRESENCE_DAMAGE` can be adjusted; currently 1
- **Tests**: 2 tests in `TestP05KingPresenceDamage`

## Test Summary

- **Total**: 43 tests passing
  - P0.1: 6 tests
  - P0.2: 4 tests
  - P0.3: 3 tests
  - P0.4: 6 tests
  - P0.5: 2 tests
  - Existing: 22 tests

All tests are **deterministic** and use **seeded RNG** for reproducibility.

## Canon Compliance

See `NOTES.md` for parametrization decisions and any pending canon clarifications.

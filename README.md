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
├── board.py      # P0.1: Canonical room adjacencies
├── state.py      # Game state (P0.4b: false_king_floor)
├── transition.py # P0 transitions (P0.2, P0.3, P0.4a, P0.5)
├── config.py     # Game configuration
└── effects/      # Status effects

sim/              # Simulation & AI policies
├── runner.py
├── policies.py
└── metrics.py

tests/            # Test suite (65 tests)
├── test_p0_canon.py    # P0 canonical mechanics
├── test_p0_updates.py  # P0 updates (keys, attract, presence)
└── [13 more test files]

tools/            # Development utilities
├── setup/        # Historical implementation scripts
├── debug/        # Debugging tools
└── validate/     # Validation scripts

docs/             # Canon documentation
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
- **Tests**: 9 tests (basic + keys coherence + multiple players)

### P0.4b - Attract (Atraer) with False King Exception
- **File**: `engine/transition.py::_attract_players_to_floor()`
- **Rule**: All players move to corridor of specified floor, EXCEPT those on `false_king_floor`
- **State**: `GameState.false_king_floor` (int | None)
- **Tests**: 3 tests in `TestP04bAttractWithFalseKing`

### P0.5 - King Presence Damage (REVISED TABLE)
- **File**: `engine/transition.py::_presence_damage_for_round()`
- **Canon Table** (confirmed):
  - Rounds 1–3: 1 damage per round
  - Rounds 4–6: 2 damage per round
  - Rounds 7–9: 3 damage per round
  - Rounds 10+: 4 damage per round
- **Application**: Only to players on King's floor
- **Tests**: 15 tests (4 in old P05, 12 parametrized in test_p0_updates)

## Test Summary

- **Total**: 65 tests passing ✅
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
| P0.1 Adjacencies | `engine/board.py` | Canonical R1↔R2, R3↔R4 | 6 | ✅ |
| P0.2 Expel | `engine/transition.py` | Floor mapping to stairs | 4 | ✅ |
| P0.3 Stairs Reroll | `engine/transition.py` | 1d4 per floor RNG | 3 | ✅ |
| P0.4a Event -5 | `engine/transition.py` | Key destruction + counter | 9 | ✅ |
| P0.4b Attract | `engine/transition.py` | With false_king exception | 3 | ✅ |
| P0.5 Presence | `engine/transition.py` | Canon table (R1-3→1, R4-6→2, ...) | 15 | ✅ |

## Development Utilities

See `tools/README.md` for:
- **Setup scripts**: Historical implementation records
- **Debug tools**: Step-by-step debugging
- **Validation**: Syntax, imports, and quick P0 checks

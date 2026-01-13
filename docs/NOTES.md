# CARCOSA P0 Implementation Notes

## CANON TODO

### P0.5 - King Presence Damage (Parametrized)

**Issue**: Canon document (Carcosa_Canon_P0_extracted.md) states:
> "Pobres Almas en el piso del Rey pierden cordura según tabla por ronda. En Ronda 1 esta pérdida no aplica."

However, the **damage table is missing** from the extracted canon document.

**Decision**: Parametrized as `Config.KING_PRESENCE_DAMAGE = 1` (1 damage per round, Round 2+).

**Status**: Default implementation uses 1 damage per round. Can be adjusted in `engine/config.py` once the canon is finalized.

---

## P0 Implementation Status

All P0 features implemented and tested:

| Feature | File | Status | Tests |
|---------|------|--------|-------|
| P0.1 Adjacencies | `engine/board.py` | ✓ Complete | 6 tests |
| P0.2 Expel | `engine/transition.py` | ✓ Complete | 4 tests |
| P0.3 Stairs Reroll | `engine/transition.py` | ✓ Complete | 3 tests |
| P0.4 Event -5 | `engine/transition.py` | ✓ Complete | 6 tests |
| P0.5 Presence Damage | `engine/transition.py` | ✓ Complete* | 2 tests |

*P0.5 damage value (1 per round) is parametrized and subject to canon clarification.

---

## Design Decisions

### 1. Stair Reroll Uses Seeded RNG (P0.3)
- Uses `rng.randint(1, 4)` from the game state's RNG instance
- Ensures determinism with fixed seed (reproducible simulations)
- Not global `random.Random()` to allow reproducibility

### 2. Event -5 Fires Once Per Crossing (P0.4)
- Tracked via `PlayerState.at_minus5` boolean flag
- Destruction (keys/objects) and sanity loss for others happen only on **transition into** -5
- Subsequent ticks in -5 do NOT repeat the event (verified by test `test_minus5_event_only_fires_once`)
- Recovery to -4 restores 2 actions automatically

### 3. King Expel Maps Floors Canonically (P0.2)
- F1 → F2 stair room (one floor up, moving through stairs)
- F2 → F1 stair room (one floor down, moving through stairs)
- F3 → F2 stair room (one floor down, moving through stairs)
- Mapping follows canon: "el jugador debe estar en la habitación que contiene la escalera en su piso actual"

### 4. Presence Damage Starts Round 2 (P0.5)
- Canon: "En Ronda 1 esta pérdida no aplica"
- Implemented: `_presence_damage_for_round(round) == 0 if round == 1 else 1`

---

## Testing Strategy

All tests are **deterministic** and **reproducible**:

- **Seeded RNG**: All randomness controlled by explicit seed values
- **No global state**: No reliance on `random` global state or dict ordering
- **Fixed test data**: Tests use fixed room/floor/seed values
- **Clear assertions**: Each test verifies exactly one behavioral rule

Example (P0.3 determinism):
```python
def test_stairs_reroll_deterministic_with_seed(self):
    stairs1 = get_stairs(seed=12345)
    stairs2 = get_stairs(seed=12345)
    assert stairs1 == stairs2  # Same seed -> same stairs
```

---

## Future Work (Beyond P0)

- [ ] Clarify exact King presence damage per round (currently 1, subject to canon)
- [ ] Implement P1+ features (as canon is finalized)
- [ ] Add performance metrics and simulation runner optimization
- [ ] Expand card resolution system (currently minimal)

---

## Running Tests in WSL

From PowerShell:
```powershell
wsl bash -c "cd /home/gris/CARCOSA && source .venv/bin/activate && PYTHONPATH=/home/gris/CARCOSA pytest -q"
```

From WSL bash:
```bash
cd /home/gris/CARCOSA
source .venv/bin/activate
export PYTHONPATH=/home/gris/CARCOSA:$PYTHONPATH
pytest -q  # 43 tests passing
```

---

## Files Modified

| File | Changes |
|------|---------|
| `engine/board.py` | Added canonical adjacencies (R1↔R2, R3↔R4) to `neighbors()` |
| `engine/transition.py` | P0.2-P0.5 implementations (_expel, _roll_stairs, _apply_minus5_transitions, _presence_damage_for_round) |
| `tests/test_p0_canon.py` | 21 new tests for P0.1-P0.5 |
| `README.md` | Installation, test execution, and feature documentation |
| `NOTES.md` | This file (new) |

---

Generated: 2026-01-10
Core: P0 Canonical (ready for commit/push to GitHub)

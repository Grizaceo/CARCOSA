"""Fix _preferred_floor to distribute players across all 3 floors without duplicates.

Current (broken):  [1, 2, 3, 2]  - P0→F1(King), P1→F2, P2→F3, P3→F2 (F2 duplicated)
Fixed:             dynamic based on state.king_floor and available floors
Strategy: assign each player to a different floor cyclically, but avoid king floor
for last player. Actually: spread 4 players across 3 floors (one floor gets 2 players).
Best: [2, 3, 2, 1] - safe floors first, King floor last.
Or: use modulo to cycle naturally and accept one duplicate on a safe floor.
"""
import pathlib, re

root = pathlib.Path(__file__).parent.parent
fp = root / "sim" / "policies.py"
text = fp.read_text(encoding="utf-8")

old = '''    def _preferred_floor(self, pid: PlayerId, state: GameState) -> int:
        """Asigna un piso preferido a cada jugador para evitar clustering."""
        sorted_pids = sorted(str(p) for p in state.players.keys())
        idx = sorted_pids.index(str(pid)) if str(pid) in sorted_pids else 0
        floors = [1, 2, 3, 2]  # P0→F1, P1→F2(Umbral), P2→F3, P3→F2
        return floors[idx % 4]'''

new = '''    def _preferred_floor(self, pid: PlayerId, state: GameState) -> int:
        """Asigna un piso preferido a cada jugador para evitar clustering.
        Distribuye jugadores en los pisos disponibles, priorizando pisos seguros."""
        sorted_pids = sorted(str(p) for p in state.players.keys())
        idx = sorted_pids.index(str(pid)) if str(pid) in sorted_pids else 0
        all_floors = sorted(set(floor_of(rid) for rid in state.rooms
                                if not str(rid).endswith("_P")))
        # Pisos seguros primero, King floor al final (asignado al último jugador)
        safe = [f for f in all_floors if f != state.king_floor]
        ordered = safe + [state.king_floor]
        return ordered[idx % len(ordered)]'''

if old in text:
    text = text.replace(old, new, 1)
    fp.write_text(text, encoding="utf-8")
    print("OK: _preferred_floor updated")
else:
    print("NOT FOUND")
    idx = text.find("_preferred_floor")
    if idx >= 0:
        print(repr(text[idx:idx+500]))

"""Implement Safe-First strategy: bots avoid King's floor, prioritize safe floors.

Key insight: When apply_minus5_consequences fires, ALL player keys are destroyed.
The main cause of key destruction is bots accumulating damage on King's floor.
With 6 keys across 3 floors and needing 4, ~68% of games have 4+ keys on safe floors.

Change: _preferred_floor assigns bots to safe floors (exclude King floor).
Only falls back to King floor when safe floors are exhausted via _best_room_global.
"""
import pathlib

root = pathlib.Path(__file__).parent.parent
fp = root / "sim" / "policies.py"
text = fp.read_text(encoding="utf-8")

old = '''    def _preferred_floor(self, pid: PlayerId, state: GameState) -> int:
        """Asigna un piso preferido a cada jugador para evitar clustering."""
        sorted_pids = sorted(str(p) for p in state.players.keys())
        idx = sorted_pids.index(str(pid)) if str(pid) in sorted_pids else 0
        floors = [1, 2, 3, 2]  # P1→F1, P2→F2(Umbral), P3→F3, P4→F2
        return floors[idx % 4]'''

new = '''    def _preferred_floor(self, pid: PlayerId, state: GameState) -> int:
        """Asigna un piso preferido a cada jugador evitando el piso del Rey.
        
        Estrategia Safe-First: todos los bots cubren pisos seguros primero.
        El piso del Rey (~4 dmg/rnd en late game) es explorado solo si todos
        los pisos seguros estan exhaustos (via fallback en _best_room_for_player).
        Con 6 llaves en 3 pisos, ~68% de juegos tienen 4+ llaves fuera del Rey.
        """
        sorted_pids = sorted(str(p) for p in state.players.keys())
        idx = sorted_pids.index(str(pid)) if str(pid) in sorted_pids else 0
        all_floors = sorted(set(floor_of(rid) for rid in state.rooms
                                if not str(rid).endswith("_P")))
        safe_floors = [f for f in all_floors if f != state.king_floor]
        if not safe_floors:
            return all_floors[idx % len(all_floors)]
        return safe_floors[idx % len(safe_floors)]'''

if old in text:
    text = text.replace(old, new, 1)
    fp.write_text(text, encoding="utf-8")
    print("OK: _preferred_floor updated to Safe-First strategy")
    print("  Floor assignment: all bots → safe floors, fall back to King floor when exhausted")
else:
    print("NOT FOUND")
    idx2 = text.find("_preferred_floor")
    if idx2 >= 0:
        print(repr(text[idx2:idx2+500]))

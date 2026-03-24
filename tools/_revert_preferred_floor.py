"""Revert _preferred_floor to hardcoded [1, 2, 3, 2] (original v2 version)."""
import pathlib

root = pathlib.Path(__file__).parent.parent
fp = root / "sim" / "policies.py"
text = fp.read_text(encoding="utf-8")

old = '''    def _preferred_floor(self, pid: PlayerId, state: GameState) -> int:
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

new = '''    def _preferred_floor(self, pid: PlayerId, state: GameState) -> int:
        """Asigna un piso preferido a cada jugador para evitar clustering."""
        sorted_pids = sorted(str(p) for p in state.players.keys())
        idx = sorted_pids.index(str(pid)) if str(pid) in sorted_pids else 0
        floors = [1, 2, 3, 2]  # P1→F1, P2→F2(Umbral), P3→F3, P4→F2
        return floors[idx % 4]'''

if old in text:
    text = text.replace(old, new, 1)
    fp.write_text(text, encoding="utf-8")
    print("OK: _preferred_floor reverted to v2")
else:
    print("NOT FOUND")
    idx2 = text.find("_preferred_floor")
    print(repr(text[idx2:idx2+600]))

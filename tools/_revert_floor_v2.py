"""Revert _preferred_floor to v2: hardcoded [1, 2, 3, 2]."""
import pathlib

root = pathlib.Path(__file__).parent.parent
fp = root / "sim" / "policies.py"
text = fp.read_text(encoding="utf-8")

old_marker = '    def _preferred_floor(self, pid: PlayerId, state: GameState) -> int:'
idx = text.find(old_marker)
if idx < 0:
    print("NOT FOUND: method not found at all")
    exit(1)

# Find the end of this method (next def at same indent level)
method_start = idx
next_def = text.find('\n    def ', idx + len(old_marker))
if next_def < 0:
    print("Cannot find end of method")
    exit(1)

old_method = text[method_start:next_def]
print("Current method:")
print(repr(old_method[:400]))

new_method = '''    def _preferred_floor(self, pid: PlayerId, state: GameState) -> int:
        """Asigna un piso preferido a cada jugador para evitar clustering."""
        sorted_pids = sorted(str(p) for p in state.players.keys())
        idx = sorted_pids.index(str(pid)) if str(pid) in sorted_pids else 0
        floors = [1, 2, 3, 2]  # P1→F1, P2→F2(Umbral), P3→F3, P4→F2
        return floors[idx % 4]'''

text = text[:method_start] + new_method + text[next_def:]
fp.write_text(text, encoding="utf-8")
print("OK: reverted to v2 _preferred_floor")

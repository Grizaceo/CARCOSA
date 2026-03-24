"""Remove unconditional late_game king-floor flee block (0.8) from policies.py."""
import re, sys, pathlib

root = pathlib.Path(__file__).parent.parent
fp = root / "sim" / "policies.py"
text = fp.read_text(encoding="utf-8")

# Pattern: from the "# 0.8)" comment up to (but not including) "# 1)"
pattern = re.compile(
    r'        # 0\.8\) .+?\n'          # comment line
    r'        if late_game and on_king_floor:\n'
    r'            exits = \[\n'
    r'                a for a in acts\n'
    r'                if a\.type == ActionType\.MOVE\n'
    r'                and floor_of\(RoomId\(a\.data\.get\("to", str\(p\.room\)\)\)\) != state\.king_floor\n'
    r'            \]\n'
    r'            if exits:\n'
    r'                safest = min\(exits, key=lambda a: _danger_score_room\(state, RoomId\(a\.data\.get\("to"\)\)\)\)\n'
    r'                return finalize\(safest\)\n'
    r'\n',
    re.DOTALL,
)

new_text, n = pattern.subn("", text)
if n == 0:
    print("NOT FOUND — trying fallback line-based approach")
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if "0.8)" in line and "late game" in line:
            start = i
            break
    if start is None:
        print("Block 0.8 not found at all")
        sys.exit(1)
    end = start + 1
    while end < len(lines) and "# 1)" not in lines[end]:
        end += 1
    removed = lines[start:end]
    print(f"Removing lines {start+1}-{end} (before # 1)):")
    print("".join(removed))
    new_lines = lines[:start] + lines[end:]
    new_text = "".join(new_lines)
    n = 1

fp.write_text(new_text, encoding="utf-8")
print(f"OK: removed {n} occurrence(s) of block 0.8")

# Verify
remaining = fp.read_text(encoding="utf-8")
if "0.8) En late game" in remaining or "late_game and on_king_floor" in remaining:
    print("WARNING: pattern still present")
else:
    print("Verified: block 0.8 successfully removed")

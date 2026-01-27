#!/usr/bin/env python3
"""Implement P0.2: Fix _expel_players_from_floor to move to stair room in adjacent floor"""

# Leer el archivo actual
with open('engine/transition.py', 'r') as f:
    content = f.read()

# Definir la nueva implementación de _expel_players_from_floor según canon P0.2
new_expel = '''def _expel_players_from_floor(s, floor: int):
    """
    P0.2: Expel players from King's floor to adjacent floor's stair room.
    Floor mapping (canon):
    - F1 -> F2 (move to stair room in F2)
    - F2 -> F1 (move to stair room in F1)
    - F3 -> F2 (move to stair room in F2)
    """
    # Determine destination floor
    if floor == 1:
        dest_floor = 2
    elif floor == 2:
        dest_floor = 1
    elif floor == 3:
        dest_floor = 2
    else:
        return  # Invalid floor
    
    # Move players to stair room in destination floor
    stair_room = s.stairs.get(dest_floor)
    if stair_room is None:
        return  # No stair initialized (shouldn't happen)
    
    for p in s.players.values():
        if floor_of(p.room) == floor:
            p.room = stair_room'''

# Reemplazar la función
import re
pattern = r'def _expel_players_from_floor\(s, floor: int\):.*?(?=\ndef |\Z)'
content = re.sub(pattern, new_expel + '\n\n', content, flags=re.DOTALL)

with open('engine/transition.py', 'w') as f:
    f.write(content)

print('✓ P0.2 _expel_players_from_floor implemented with canon floor mapping')

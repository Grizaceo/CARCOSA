#!/usr/bin/env python3
"""Implement P0.3 (_roll_stairs) and P0.5 (presence damage) in engine/transition.py"""

# Leer el archivo actual
with open('engine/transition.py', 'r') as f:
    lines = f.readlines()

# Buscar líneas para reemplazar
output = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Reemplazar _roll_stairs
    if line.strip().startswith('def _roll_stairs(s, rng: RNG):'):
        output.append(line)  # def line
        i += 1
        # Saltamos la línea vacía "return None" y la reemplazamos
        if i < len(lines) and lines[i].strip() == 'return None':
            # Agregar la implementación P0.3
            output.append('    """Reroll stairs (1d4 per floor) at end of round.\"\"\"\n')
            output.append('    from engine.board import room_from_d4, FLOORS\n')
            output.append('    for floor in range(1, FLOORS + 1):\n')
            output.append('        roll = rng.randint(1, 4)\n')
            output.append('        s.stairs[floor] = room_from_d4(floor, roll)\n')
            i += 1
        continue
    
    # Reemplazar _presence_damage_for_round
    if line.strip().startswith('def _presence_damage_for_round(round_n: int) -> int:'):
        output.append(line)
        i += 1
        # Reemplazar "return 0" or similar con la implementación P0.5
        while i < len(lines) and (lines[i].strip().startswith('return') or 
                                   lines[i].strip() == '' or
                                   lines[i].startswith('    ')):
            if lines[i].strip().startswith('return'):
                output.append('    """Damage per round from King presence (P0.5).\"\"\"\n')
                output.append('    # Ronda 1: sin daño. Ronda 2+: 1 punto por ronda (KING_PRESENCE_DAMAGE en config)\n')
                output.append('    return 1 if round_n >= 2 else 0\n')
                i += 1
                break
            else:
                output.append(lines[i])
                i += 1
        continue
    
    output.append(line)
    i += 1

# Escribir el archivo actualizado
with open('engine/transition.py', 'w') as f:
    f.writelines(output)

print('✓ P0.3 (_roll_stairs) and P0.5 (_presence_damage_for_round) implemented')

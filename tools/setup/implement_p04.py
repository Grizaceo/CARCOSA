#!/usr/bin/env python3
"""Implement P0.4: Event on crossing to -5 (destroy keys/objects, others lose sanity)"""

# Leer el archivo actual
with open('engine/transition.py', 'r') as f:
    lines = f.readlines()

# Encontrar y reemplazar _apply_minus5_transitions
output = []
i = 0
while i < len(lines):
    if lines[i].strip().startswith('def _apply_minus5_transitions(s, cfg):'):
        # Agregar nueva implementación
        output.append(lines[i])  # def line
        i += 1
        
        # Leer hasta el siguiente def o EOF
        indent_content = []
        while i < len(lines) and not (lines[i].strip() and not lines[i].startswith(' ') and lines[i].startswith('def')):
            i += 1
        
        # Escribir la nueva implementación
        impl = '''    """
    P0.4: Event on crossing to -5.
    - Destroy keys and objects when crossing to <= -5
    - Others lose 1 sanity when someone crosses
    - Maintain 1 action while at -5; restore 2 when leaving to -4
    - Event fires only once on crossing (tracked via at_minus5 flag)
    """
    for pid, p in s.players.items():
        if p.sanity <= cfg.S_LOSS:  # At or below -5
            if not p.at_minus5:  # Just crossed into -5
                # Destroy keys and objects
                p.keys = 0
                p.objects = []
                
                # Other players lose 1 sanity
                for other_pid, other in s.players.items():
                    if other_pid != pid:
                        other.sanity -= 1
                
                # Mark as in -5 state
                p.at_minus5 = True
            
            # Maintain 1 action per turn while at -5
            s.remaining_actions[pid] = min(1, s.remaining_actions.get(pid, 2))
        else:  # Above -5
            if p.at_minus5:  # Just left -5
                # Restore to 2 actions
                p.at_minus5 = False
                s.remaining_actions[pid] = 2

'''
        output.append(impl)
        continue
    
    output.append(lines[i])
    i += 1

with open('engine/transition.py', 'w') as f:
    f.writelines(output)

print('✓ P0.4 _apply_minus5_transitions implemented with key/object destruction and sanity loss for others')

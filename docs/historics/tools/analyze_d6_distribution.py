import json
import glob
from collections import Counter

# Analizar distribución de d6 en detalle
print('=== DISTRIBUCIÓN DE d6 DEL REY EN TODAS LAS RUNS ===\n')

all_d6s = []

for run_file in sorted(glob.glob('runs/run_seed*.jsonl')):
    d6s = []
    with open(run_file) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r.get('action_type') == 'KING_ENDROUND':
                    d6 = r.get('action_data', {}).get('d6')
                    if d6:
                        d6s.append(d6)
                        all_d6s.append(d6)
    
    if d6s:
        counter = Counter(d6s)
        total = len(d6s)
        filename = run_file.split('/')[-1]
        print(f'{filename}: total={total:2d}, {dict(counter)}')

print(f'\n=== ESTADÍSTICAS GLOBALES ===')
global_counter = Counter(all_d6s)
total_d6s = len(all_d6s)
print(f'Total tiradas de d6: {total_d6s}')
print(f'Distribución: {dict(global_counter)}')
print(f'\nPorcentajes por dado:')
for die in range(1, 7):
    count = global_counter.get(die, 0)
    percentage = (count / total_d6s * 100) if total_d6s > 0 else 0
    expected = (total_d6s / 6)
    ratio = count / expected if expected > 0 else 0
    print(f'  d6={die}: {count:2d} tiradas ({percentage:5.1f}%) - Esperado: {expected:5.1f} ({ratio:.2f}x)')

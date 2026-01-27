"""
Análisis de Inconsistencias en Runs vs Documentación
Compara datos de simulaciones con reglas especificadas
"""
import json
import glob
from collections import Counter

def analyze_run(run_file):
    """Analiza un archivo JSONL de run y reporta inconsistencias"""
    
    records = []
    with open(run_file) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    
    if not records:
        return None
    
    issues = []
    
    # ========== ISSUE 1: Cordura por debajo del límite ==========
    min_sanities = [r['summary_post'].get('min_sanity', 0) for r in records]
    min_overall = min(min_sanities)
    
    # Según doc: no hay límite inferior explícito, pero "clampear a -5" es estándar
    if min_overall < -5:
        issues.append({
            'type': 'SANITY_BELOW_LIMIT',
            'severity': 'HIGH',
            'description': f'Cordura mínima alcanzada: {min_overall} (debería estar clampéada a -5)',
            'step': next(r['step'] for r in records if r['summary_post'].get('min_sanity', 0) == min_overall),
            'value': min_overall
        })
    
    # ========== ISSUE 2: Tensión fuera de rango ==========
    tensions = [r['T_post'] for r in records]
    invalid_tensions = [t for t in tensions if t < 0.0 or t > 1.0]
    if invalid_tensions:
        issues.append({
            'type': 'TENSION_OUT_OF_RANGE',
            'severity': 'HIGH',
            'description': f'Tensión fuera de [0.0, 1.0]: {len(invalid_tensions)} registros',
            'values': invalid_tensions[:3]
        })
    
    # ========== ISSUE 3: Llaves >4 en mano ==========
    keys_in_hand = [r['summary_post'].get('keys_in_hand', 0) for r in records]
    max_keys = max(keys_in_hand)
    if max_keys > 4:
        issues.append({
            'type': 'EXCESS_KEYS',
            'severity': 'MEDIUM',
            'description': f'Jugadores con más de 4 llaves: máximo alcanzado={max_keys}',
            'note': 'Manual especifica 4 llaves por piso (12 total en juego), capacidad por jugador ~4'
        })
    
    # ========== ISSUE 4: Monstruos excesivos ==========
    max_monsters = max(r['summary_post'].get('monsters', 0) for r in records)
    if max_monsters > 16:  # Cap típico en juegos de tipo Eldritch Horror
        issues.append({
            'type': 'EXCESS_MONSTERS',
            'severity': 'MEDIUM',
            'description': f'Monstruos en tablero: {max_monsters} (posible exceso)',
            'note': 'Revisar si hay cap en pool de monstruos'
        })
    
    # ========== ISSUE 5: Acciones del Rey ==========
    king_endround = [r for r in records if r.get('action_type') == 'KING_ENDROUND']
    if king_endround:
        # Revisar distribución de d6
        d6_rolls = [r.get('action_data', {}).get('d6') for r in king_endround if r.get('action_data', {}).get('d6')]
        d6_counter = Counter(d6_rolls)
        
        # Estadísticamente, cada d6 debería aparecer ~16.67% (1/6)
        expected_count = len(d6_rolls) / 6
        skewed = {k: v for k, v in d6_counter.items() if v > expected_count * 2}
        
        if skewed:
            issues.append({
                'type': 'SKEWED_D6_DISTRIBUTION',
                'severity': 'LOW',
                'description': f'Distribución de d6 del Rey parece sesgada: {dict(d6_counter)}',
                'note': 'Posible problema de RNG o política del Rey muy determinista'
            })
    
    # ========== ISSUE 6: Flujo de llave ==========
    # Revisar si las llaves destruidas tienen sentido
    first_keys_destroyed = records[0]['summary_post'].get('keys_destroyed', 0)
    last_keys_destroyed = records[-1]['summary_post'].get('keys_destroyed', 0)
    
    # Según manual: llaves se destruyen al cruzar a piso -5
    if first_keys_destroyed > 0:
        issues.append({
            'type': 'KEYS_DESTROYED_IMMEDIATELY',
            'severity': 'LOW',
            'description': f'Llaves destruidas desde el primer registro: {first_keys_destroyed}',
            'note': 'Podría ser correcto si cruzó a -5 en primer paso'
        })
    
    # ========== ISSUE 7: Win/Lose conditions ==========
    final_record = records[-1]
    outcome = final_record.get('outcome')
    
    if outcome == 'WIN':
        # Verificar si tenía >=4 llaves en Umbral
        final_keys = final_record['summary_post'].get('keys_in_hand', 0)
        final_umbral = final_record['summary_post'].get('umbral_frac', 0.0)
        
        if final_keys < 4:
            issues.append({
                'type': 'WIN_CONDITION_INVALID',
                'severity': 'HIGH',
                'description': f'Victoria sin 4 llaves: tenía {final_keys} (necesita >=4)',
                'final_state': f'Umbral={final_umbral}, Keys={final_keys}'
            })
        
        if final_umbral < 1.0:
            issues.append({
                'type': 'WIN_CONDITION_INVALID',
                'severity': 'HIGH',
                'description': f'Victoria sin estar todos en Umbral: umbral_frac={final_umbral}',
                'note': 'Manual: "ganais si todos los jugadores estan en piso -5 con >=4 llaves"'
            })
    
    elif outcome == 'LOSE':
        # Verificar si min_sanity <= -5 
        final_min_sanity = final_record['summary_post'].get('min_sanity', 0)
        if final_min_sanity > -5:
            issues.append({
                'type': 'LOSE_CONDITION_INVALID',
                'severity': 'MEDIUM',
                'description': f'Derrota sin cordura a -5: min_sanity={final_min_sanity}',
                'note': 'Revisar si hay otras condiciones de derrota'
            })
    
    # ========== ISSUE 8: Rotación de escaleras ==========
    # Escaleras deben cambiar cada ronda
    stairs_history = []
    for r in records:
        if r.get('action_type') == 'KING_ENDROUND':
            stairs_history.append(r['summary_post'].get('stairs', None))
    
    # ========== ISSUE 9: Cambios de fase sin consistencia ==========
    phases = [r['phase'] for r in records]
    phase_changes = sum(1 for i in range(len(phases)-1) if phases[i] != phases[i+1])
    expected_phase_changes = records[-1]['round'] * 2  # Aprox 2 cambios por ronda
    
    if phase_changes < expected_phase_changes * 0.5:
        issues.append({
            'type': 'PHASE_TRANSITION_UNUSUAL',
            'severity': 'LOW',
            'description': f'Cambios de fase bajos: {phase_changes} (esperado ~{expected_phase_changes})',
            'note': 'Podría indicar que no hay balance correcto entre turnos PLAYER y KING'
        })
    
    # ========== ISSUE 10: Feature normalization ==========
    for r in records:
        for feat_dict in [r.get('features_pre'), r.get('features_post')]:
            if feat_dict:
                invalid_features = {k: v for k, v in feat_dict.items() if not (0.0 <= v <= 1.0)}
                if invalid_features:
                    issues.append({
                        'type': 'FEATURE_OUT_OF_RANGE',
                        'severity': 'HIGH',
                        'description': f'Features fuera de [0,1]: {invalid_features}',
                        'step': r['step'],
                        'phase': r['phase']
                    })
                    break
    
    return records, issues

# ==================================================
# MAIN: Analizar todas las runs
# ==================================================

print('=' * 70)
print('ANÁLISIS DE INCONSISTENCIAS: RUNS vs DOCUMENTACIÓN')
print('=' * 70)
print()

all_issues_by_type = {}

def _find_run_files(limit=5):
    # Prefer current runs/ (recursive) then fall back to historics
    candidates = []
    candidates.extend(glob.glob('runs/**/*.jsonl', recursive=True))
    if not candidates:
        candidates.extend(glob.glob('docs/historics/runs/**/*.jsonl', recursive=True))
    # Newest first
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[:limit]

import os

for run_file in _find_run_files(limit=5):
    filename = run_file.split('/')[-1]
    result = analyze_run(run_file)
    
    if result is None:
        continue
    
    records, issues = result
    
    print(f'\n📄 {filename}')
    print(f'   Pasos: {len(records)} | Rondas: {records[-1]["round"]} | Outcome: {records[-1]["outcome"]}')
    
    if issues:
        print(f'   ⚠️  PROBLEMAS ENCONTRADOS: {len(issues)}')
        for issue in issues:
            severity_icon = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🔵'}[issue['severity']]
            print(f'      {severity_icon} [{issue["type"]}] {issue["description"]}')
            
            # Agrupar por tipo
            if issue['type'] not in all_issues_by_type:
                all_issues_by_type[issue['type']] = []
            all_issues_by_type[issue['type']].append({
                'file': filename,
                'issue': issue
            })
    else:
        print(f'   ✅ Sin inconsistencias detectadas')

# ==================================================
# RESUMEN GLOBAL
# ==================================================
print('\n' + '=' * 70)
print('RESUMEN GLOBAL DE INCONSISTENCIAS')
print('=' * 70)

if all_issues_by_type:
    for issue_type in sorted(all_issues_by_type.keys()):
        occurrences = all_issues_by_type[issue_type]
        print(f'\n{issue_type}: {len(occurrences)} ocurrencia(s)')
        for occ in occurrences[:2]:  # Mostrar primeras 2
            print(f'  - {occ["file"]}: {occ["issue"]["description"]}')
else:
    print('\n✅ No se detectaron inconsistencias significativas.')

print('\n' + '=' * 70)

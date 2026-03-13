# Reporte: Fase A agresiva `3 -> 4` llaves (3 repeticiones)

## Configuración ejecutada

- Base: `models/rl_adaptive_select/adaptive_20260306_181154/best_model_selected.zip`
- Algoritmo: `maskable_ppo`
- Selector: `funnel_k4`
- Timesteps por run: `20k` (`4x5k`)
- Eval interna: `20` episodios
- Eval extendida: `80` episodios

Curriculum:

- `curriculum_closing_prob=0.0`
- `curriculum_focus_threshold_rate4=0.08`
- `curriculum_keys34_prob=0.50`
- `curriculum_keys34_prob_focus=0.85`
- `curriculum_keys34_min_keys=3`
- `curriculum_keys34_max_keys=3`
- `curriculum_keys34_fragile_carriers=1`
- `curriculum_keys34_fragile_sanity=[-4,-3]`
- Gate: `max_minus5_with_keys_rate=0.36`

Batch metadata:

- `runs/rl_training_adaptive_select/phaseA_aggressive_k4_batch3_20260306_183230.txt`
- `runs/rl_training_adaptive_select/phaseA_aggressive_k4_batch3_eval80_report_20260306.json`

## Corridas

1. Seed `1201`
   - `models/rl_adaptive_select/adaptive_20260306_183234/summary.json`
   - `models/rl_adaptive_select/adaptive_20260306_183234/comparison_eval_80_phaseA_aggressive_k4_seed1201.json`

2. Seed `1302`
   - `models/rl_adaptive_select/adaptive_20260306_183329/summary.json`
   - `models/rl_adaptive_select/adaptive_20260306_183329/comparison_eval_80_phaseA_aggressive_k4_seed1302.json`

3. Seed `1403`
   - `models/rl_adaptive_select/adaptive_20260306_183422/summary.json`
   - `models/rl_adaptive_select/adaptive_20260306_183422/comparison_eval_80_phaseA_aggressive_k4_seed1403.json`

## Resultado

### Delta `base -> final` (80 episodios)

- Seed `1201`: sin cambios (`Δ` en métricas clave = `0.0`)
- Seed `1302`: empeora embudo (`Δk3=-0.025`, `Δk4=-0.025`, `Δkeys_goal=-0.025`), mejora leve `m5k`
- Seed `1403`: sin cambios (`Δ` en métricas clave = `0.0`)

### Mediana final80 del bloque

- `win_rate = 0.0000`
- `rate_reached_3_keys = 0.1875`
- `rate_reached_4_keys = 0.0375`
- `rate_reached_keys_goal = 0.0375`
- `win_given_reached_keys_goal = 0.0000`
- `minus5_entry_with_keys_rate = 0.3333`
- `minus5_rate = 0.9000`

## Selección del mejor candidato

Prioridad usada: `k4`, `keys_goal`, `-m5_with_keys`, `-minus5_rate`.

- Mejor por ranking: **seed `1201`**
- Nota: seed `1201` y `1403` quedaron efectivamente empatados en métricas finales (se selecciona `1201` por orden estable de tie-break).

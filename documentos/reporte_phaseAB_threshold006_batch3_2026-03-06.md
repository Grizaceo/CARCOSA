# Reporte: ciclos A+B con `threshold=0.06` (3 repeticiones)

## Configuración

- Límite de ejecución solicitado: `30` minutos
- Tiempo real usado (entrenamiento): `327` segundos (~`5.5` min)
- Batch log: `runs/rl_training_adaptive_select/phaseAB_threshold006_batch3_20260306_180720.txt`
- Modelo inicial del batch: `models/rl_adaptive_select/adaptive_20260306_172029/best_model_selected.zip`

Fase A (densidad 3->4 llaves):

- `selector_profile=funnel_k4`
- `curriculum_focus_threshold_rate4=0.06`
- `curriculum_keys34_prob_focus=0.75`
- `curriculum_closing_prob_below_threshold=0.0`

Fase B (conversión/cierre):

- `selector_profile=funnel_k4`
- `curriculum_focus_threshold_rate4=0.06`
- `curriculum_keys34_prob_focus=0.50`
- `curriculum_closing_prob_below_threshold=0.30`

Ambas fases:

- `20k` timesteps por run (`4x5k`), `eval_episodes=20`, `n_envs=4`
- `max_minus5_with_keys_rate=0.36`
- Eval extendida en `80` episodios sin curriculum

## Runs ejecutados

### Ciclo 1

- A: `models/rl_adaptive_select/adaptive_20260306_180722/summary.json`
- B: `models/rl_adaptive_select/adaptive_20260306_180815/summary.json`
- Eval B (80): `models/rl_adaptive_select/adaptive_20260306_180815/comparison_eval_80_phaseAB_threshold006_cycle1_phaseB.json`

### Ciclo 2

- A: `models/rl_adaptive_select/adaptive_20260306_180908/summary.json`
- B: `models/rl_adaptive_select/adaptive_20260306_181000/summary.json`
- Eval B (80): `models/rl_adaptive_select/adaptive_20260306_181000/comparison_eval_80_phaseAB_threshold006_cycle2_phaseB.json`

### Ciclo 3

- A: `models/rl_adaptive_select/adaptive_20260306_181100/summary.json`
- B: `models/rl_adaptive_select/adaptive_20260306_181154/summary.json`
- Eval B (80): `models/rl_adaptive_select/adaptive_20260306_181154/comparison_eval_80_phaseAB_threshold006_cycle3_phaseB.json`

## Resultado consolidado de fases B (80 episodios)

Reporte consolidado JSON:

- `runs/rl_training_adaptive_select/phaseAB_threshold006_batch3_eval80_report_20260306.json`

Delta `base -> final` por ciclo (fase B):

- Ciclo 1: sin cambios (`Δ` todos `0.0`)
- Ciclo 2: sin cambios (`Δ` todos `0.0`)
- Ciclo 3: sin cambios (`Δ` todos `0.0`)

Mediana `final80` del bloque B:

- `win_rate = 0.0000`
- `rate_reached_3_keys = 0.1875`
- `rate_reached_4_keys = 0.0375`
- `rate_reached_keys_goal = 0.0375`
- `win_given_reached_keys_goal = 0.0000`
- `minus5_entry_with_keys_rate = 0.3333`
- `minus5_rate = 0.9000`

## Comparación global batch (inicio -> fin)

- Archivo: `models/rl_adaptive_select/adaptive_20260306_181154/comparison_eval_80_phaseAB_threshold006_start_vs_end.json`

Delta en 80 episodios:

- `win_rate`: `+0.0000`
- `rate_reached_3_keys`: `+0.0250`
- `rate_reached_4_keys`: `+0.0125`
- `rate_reached_keys_goal`: `+0.0125`
- `minus5_entry_with_keys_rate`: `+0.0242` (peor)
- `minus5_rate`: `-0.0250` (mejor)
- `avg_reward`: `-0.3028` (peor)

## Conclusión

- El esquema A+B con `threshold=0.06` en este batch **sí movió ligeramente el embudo** (`k3`, `k4`, `keys_goal`) al comparar inicio vs fin.
- La fase B no aceptó chunks en ninguno de los 3 ciclos (sin cambios en evaluación B por ciclo).
- No hubo conversión a victorias (`win_rate` permanece en `0.0`).

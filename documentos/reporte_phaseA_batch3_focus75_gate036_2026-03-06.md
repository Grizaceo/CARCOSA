# Reporte: 3 repeticiones Fase A (`funnel_k4`, focus `0.75`, gate `0.36`)

## Configuración común

- Base model: `models/rl_adaptive_select/adaptive_20260306_172029/best_model_selected.zip`
- Algoritmo: `maskable_ppo`
- Selector: `funnel_k4`
- Timesteps por corrida: `20000` (4 chunks de 5000)
- Eval interna por chunk: `20` episodios
- Eval extendida: `80` episodios (sin curriculum en eval)

Batch meta:

- `runs/rl_training_adaptive_select/phaseA_focus75_gate036_batch3_20260306_175822.txt`
- `runs/rl_training_adaptive_select/phaseA_focus75_gate036_batch3_eval80_report_20260306.json`

## Corridas ejecutadas

1. Seed `173`
   - `models/rl_adaptive_select/adaptive_20260306_175826/summary.json`
   - `models/rl_adaptive_select/adaptive_20260306_175826/comparison_eval_80_maskable_phaseA_funnel_k4_focus75_gate036_seed173.json`

2. Seed `274`
   - `models/rl_adaptive_select/adaptive_20260306_175920/summary.json`
   - `models/rl_adaptive_select/adaptive_20260306_175920/comparison_eval_80_maskable_phaseA_funnel_k4_focus75_gate036_seed274.json`

3. Seed `375`
   - `models/rl_adaptive_select/adaptive_20260306_180014/summary.json`
   - `models/rl_adaptive_select/adaptive_20260306_180014/comparison_eval_80_maskable_phaseA_funnel_k4_focus75_gate036_seed375.json`

## Resultado por corrida

### Eval interna (20 episodios, modelo final seleccionado)

| Seed | Chunks aceptados | `k3` | `k4` | `keys_goal` | `m5_with_keys` | `minus5_rate` |
|---|---:|---:|---:|---:|---:|---:|
| 173 | 1 | 0.20 | 0.05 | 0.05 | 0.3396 | 0.80 |
| 274 | 0 | 0.20 | 0.05 | 0.05 | 0.3462 | 0.85 |
| 375 | 1 | 0.25 | 0.05 | 0.05 | 0.3519 | 0.80 |

### Eval extendida (80 episodios, delta `base -> final`)

| Seed | `Δwin_rate` | `Δk3` | `Δk4` | `Δkeys_goal` | `Δm5_with_keys` | `Δminus5_rate` | `Δavg_reward` |
|---|---:|---:|---:|---:|---:|---:|---:|
| 173 | +0.0000 | +0.0125 | -0.0125 | -0.0125 | +0.0050 | -0.0125 | -0.1979 |
| 274 | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 375 | +0.0000 | +0.0125 | -0.0125 | -0.0125 | +0.0094 | -0.0125 | +0.0203 |

## Mediana del bloque (80 episodios)

- `win_rate`: `0.0000`
- `k3`: `0.1750`
- `k4`: `0.0125`
- `keys_goal`: `0.0125`
- `win_given_reached_keys_goal`: `0.0000`
- `m5_with_keys`: `0.3141`
- `minus5_rate`: `0.9125`

## Conclusión

- Las 3 repeticiones **no produjeron mejora neta** en victoria (`win_rate` se mantuvo en `0.0`).
- Dos corridas aceptaron chunks internamente, pero en 80 episodios la conversión a `4+` llaves no mejoró; de hecho bajó `k4` respecto a su base en seeds `173` y `375`.
- El bloque confirma que con esta configuración el avance en `k4` sigue siendo inestable entre seeds.

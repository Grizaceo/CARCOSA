# Reporte 20k `MaskablePPO` + foco `keys34` (2026-03-06)

## 1) Configuración ejecutada

- Script: `train/adaptive_finetune.py`
- Algoritmo: `maskable_ppo`
- Selector: `--selector-profile funnel`
- Base: `models/rl_adaptive_select/adaptive_20260306_140226/best_model_selected.zip`
- Timesteps: `20000` (`4` chunks de `5000`)
- Eval interna por chunk: `20` episodios

Curriculum y gates aplicados:

- `--curriculum-auto-focus-keys34`
- `--curriculum-focus-threshold-rate4 0.10`
- `--curriculum-closing-prob-below-threshold 0.0`
- `--curriculum-keys34-prob 0.35`
- `--curriculum-keys34-prob-focus 0.60`
- `--curriculum-keys34-min-keys 2`
- `--curriculum-keys34-max-keys 3`
- `--curriculum-keys34-fragile-sanity-min -4`
- `--curriculum-keys34-fragile-sanity-max -2`
- `--curriculum-keys34-fragile-carriers 2`
- `--max-minus5-with-keys-rate 0.35`

## 2) Artefactos

- Resumen run: `models/rl_adaptive_select/adaptive_20260306_142751/summary.json`
- Comparación extendida (80 episodios): `models/rl_adaptive_select/adaptive_20260306_142751/comparison_eval_80_maskable_funnel_keys34_focus.json`
- Log de entrenamiento: `runs/rl_training_adaptive_select/maskable_keys34_focus_20k_20260306_142750.log`

## 3) Resultado del proceso adaptativo (eval interna de 20 episodios)

- `accepted_chunks = 1`
- Chunks rechazados por `rate_reached_3_keys`: `1`, `2`
- Chunk aceptado: `3` (mejora en `minus5_entry_with_keys_rate`)
- Chunk rechazado por gate de riesgo: `4` (`risk_gate_minus5_with_keys`)

Métricas `INIT -> FINAL`:

- `win_rate`: `0.000 -> 0.000`
- `rate_reached_3_keys`: `0.150 -> 0.150`
- `rate_reached_4_keys`: `0.000 -> 0.000`
- `minus5_entry_with_keys_rate`: `0.380 -> 0.350`
- `minus5_rate`: `0.850 -> 0.900`
- `key_destroyed_rate`: `0.150 -> 0.100`
- `requested_executed_match_rate`: `0.944 -> 0.939`
- `fallback_substitution_rate`: `0.056 -> 0.061`

## 4) Comparación extendida base vs final (80 episodios)

`base` = modelo de entrada del run, `final` = modelo seleccionado al terminar.

- `win_rate`: `0.0000 -> 0.0000` (`+0.0000`)
- `rate_reached_1_keys`: `0.9375 -> 0.9375` (`+0.0000`)
- `rate_reached_2_keys`: `0.6750 -> 0.6000` (`-0.0750`)
- `rate_reached_3_keys`: `0.1875 -> 0.1375` (`-0.0500`)
- `rate_reached_4_keys`: `0.0000 -> 0.0000` (`+0.0000`)
- `rate_reached_keys_goal`: `0.0000 -> 0.0000` (`+0.0000`)
- `rate_all_near_umbral`: `0.5750 -> 0.6000` (`+0.0250`)
- `minus5_rate`: `0.9000 -> 0.9125` (`+0.0125`)
- `minus5_entry_with_keys_rate`: `0.3271 -> 0.3092` (`-0.0179`)
- `key_destroyed_rate`: `0.1000 -> 0.0875` (`-0.0125`)
- `requested_executed_match_rate`: `0.9429 -> 0.9339` (`-0.0091`)
- `fallback_substitution_rate`: `0.0571 -> 0.0661` (`+0.0091`)
- `avg_reward`: `-32.6261 -> -28.2166` (`+4.4095`)

## 5) Lectura técnica

- El nuevo perfil sí sostuvo el control de acción en rango sano (`match > 0.93`, `fallback < 0.07`).
- El gate de riesgo para `minus5` con llaves funcionó y bloqueó un candidato con deterioro crítico.
- En esta corrida no se consolidó avance del embudo `2->3->4` llaves en la comparación extendida.
- La mejora principal quedó en reducción de pérdidas con llaves (`minus5_with_keys`, `key_destroyed`), pero sin convertir a `4+` llaves ni victorias.

## 6) Siguiente paso recomendado

Para la próxima corrida corta diagnóstica (`20k`), mantener `MaskablePPO` y probar un foco más agresivo de embudo:

- subir `curriculum_keys34_prob_focus` (por ejemplo `0.70`),
- elevar prioridad en selector para `rate_reached_4_keys` manteniendo gate de riesgo,
- y revalidar con comparación extendida de `80` episodios sobre el mismo seed-base.

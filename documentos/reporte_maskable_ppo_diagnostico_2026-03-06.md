# Diagnóstico MaskablePPO (2026-03-06)

## Objetivo

Validar si el cuello principal (`requested_executed_match_rate` bajo y `fallback_substitution_rate` alto)
se corrige al migrar de PPO estándar con fallback post-hoc a `MaskablePPO` con máscara de acción legal.

## Implementación aplicada

- Máscara nativa de entorno para `sb3-contrib`: `train/carcosa_env.py` (`action_masks()`).
- Integración `MaskablePPO` en fine-tune adaptativo:
  - selección por `--algorithm maskable_ppo`;
  - carga robusta con bootstrap `PPO -> MaskablePPO` cuando el checkpoint base es PPO clásico;
  - predicción en evaluación usando `action_masks`.
- Se mantienen gates de calidad de acción:
  - `min_match_rate`;
  - `max_fallback_substitution_rate`.

## Corrida diagnóstica

- Run: `models/rl_adaptive_select/adaptive_20260306_131447`
- Log: `runs/rl_training_adaptive_select/maskable_diag20k_20260306_131445.log`
- Config principal:
  - `--algorithm maskable_ppo`
  - `--total-timesteps 20000`
  - `--chunk-timesteps 5000`
  - `--eval-episodes 20`
  - curriculum cierre: `prob=0.35`, `keys_start=4`, `far_player_prob=0.8`

## Resultado principal (20 episodios internos)

`summary.json` final:

- `requested_executed_match_rate`: **0.9513**
- `fallback_substitution_rate`: **0.0487**
- `invalid_intent_rate`: **0.0487**
- `masked_out_rate`: **0.0487**
- `pred_peek_rate_when_available`: **0.2977**
- `exec_peek_rate_when_available`: **0.2977**
- `accepted_chunks`: **1**

Comparado con diagnóstico previo (sin máscara real), el salto en semántica de acción es contundente:

- Match sube de ~0.35 a ~0.95.
- Fallback baja de ~0.65 a ~0.05.
- `PEEK` deja de estar anclado a 0 en predicción y aparece explícitamente.

## Comparación extendida base vs final (80 episodios, maskable)

Archivo: `models/rl_adaptive_select/adaptive_20260306_131447/comparison_eval_80_maskable.json`

- `win_rate`: 0.0 -> 0.0
- `requested_executed_match_rate`: 0.9519 -> 0.9501
- `fallback_substitution_rate`: 0.0481 -> 0.0499
- `pred_peek_rate_when_available`: 0.3023 -> 0.2686
- `avg_reward`: -33.61 -> -33.39
- `minus5_rate`: 0.975 -> 0.950

Lectura:

1. **El cuello de semántica de acción queda resuelto técnicamente** (métricas de match/fallback en el rango objetivo).
2. **La victoria sigue sin despegar** (`win_rate=0`), por lo que el siguiente cuello ya no es máscara legal sino política de cierre/memoria/planificación.

## Conclusión operativa

Esta iteración confirma la hipótesis: antes el gradiente estaba degradado por sustitución post-hoc.
Con `MaskablePPO`, la política controla la acción ejecutada y los gates dejan de bloquear por semántica.

Siguiente paso recomendado: mantener `MaskablePPO` como base estable y enfocarse en cierre de partida
(`win_given_reached_keys_goal`, curriculum de cierre más dirigido y representación de memoria compartida).


# Reporte 100k MaskablePPO (2026-03-06)

## Objetivo

Ejecutar una corrida larga (`100k`) ya con `MaskablePPO` integrado para verificar:

1. si la semántica de acción se mantiene estable (`match` alto, `fallback` bajo),
2. si esa estabilidad ya se traduce en mejoras de victoria/cierre.

## Ejecución

- Script: `train/adaptive_finetune.py`
- Algoritmo: `maskable_ppo`
- Base: `models/rl_adaptive_select/adaptive_20260306_131447/best_model_selected.zip`
- Timesteps: `100000` (chunks de `5000`)
- `n_envs=4`, `eval_episodes=30`
- Curriculum cierre (train): `closing_prob=0.35`, `keys_start=4`, `far_player_prob=0.8`
- Curriculum cierre (eval): `0.0`

Artefactos:

- Run: `models/rl_adaptive_select/adaptive_20260306_132524`
- Summary: `models/rl_adaptive_select/adaptive_20260306_132524/summary.json`
- Comparación 80 episodios: `models/rl_adaptive_select/adaptive_20260306_132524/comparison_eval_80_maskable.json`
- Comparación 80 episodios (embudo causal): `models/rl_adaptive_select/adaptive_20260306_132524/comparison_eval_80_maskable_funnel.json`
- Log: `runs/rl_training_adaptive_select/maskable_100k_20260306_132522.log`

## Resultado del proceso adaptativo

- Chunks evaluados: `20`
- Chunks aceptados: `0`
- Motivo de rechazo dominante: `rate_all_near_umbral` (18/20 decisiones)

Comparación interna (INIT vs FINAL, 30 episodios):

- `win_rate`: `0.000 -> 0.000`
- `win_given_reached_keys_goal`: `0.000 -> 0.000`
- `rate_reached_keys_goal`: `0.000 -> 0.000`
- `rate_all_near_umbral`: `0.767 -> 0.767`
- `requested_executed_match_rate`: `0.949 -> 0.949`
- `fallback_substitution_rate`: `0.051 -> 0.051`
- `pred_peek_rate_when_available`: `0.297 -> 0.297`
- `avg_reward`: `-32.17 -> -32.17`
- `minus5_rate`: `0.967 -> 0.967`

No hubo mejora neta de candidato sobre el incumbente; el modelo final quedó efectivamente igual al baseline de entrada de esta corrida.

## Comparación extendida base vs final (80 episodios)

Resultado en `comparison_eval_80_maskable.json`:

- Todas las métricas clave quedaron idénticas (`delta = 0.0`) entre base y final.
- Resumen:
  - `win_rate=0.0`
  - `requested_executed_match_rate=0.955`
  - `fallback_substitution_rate=0.045`
  - `pred_peek_rate_when_available=0.278`
  - `minus5_rate=0.938`

## Embudo causal (80 episodios)

Métricas directas de adquisición/protección/cierre:

- Tiempo hasta llaves:
  - `rate_reached_1_keys = 0.875`
  - `rate_reached_2_keys = 0.4875`
  - `rate_reached_3_keys = 0.1125`
  - `rate_reached_keys_goal (4+) = 0.0`
  - `avg_step_to_1_keys_when_reached = 43.77`
  - `avg_step_to_2_keys_when_reached = 88.67`
  - `avg_step_to_3_keys_when_reached = 93.89`
- Colapso `-5`:
  - `minus5_rate = 0.9375`
  - `minus5_entry_events = 411`
  - `minus5_entry_with_keys_events = 115`
  - `minus5_entry_with_keys_rate = 0.2798`
- Sacrificio vs aceptar:
  - `sacrifice_action_steps = 192`
  - `accept_sacrifice_action_steps = 408`
  - `sacrifice_vs_accept_ratio = 0.4706`
- Cierre con 4 llaves:
  - `fail_after_keys_goal_total = 0`
  - `fail_after_keys_goal_without_full_umbral = 0`
  - `fail_after_keys_goal_due_umbral_only = 0`

Lectura del embudo:

1. El sistema llega a 1–2 llaves con frecuencia moderada, cae fuerte en 3 llaves y no alcanza 4 llaves.
2. El colapso por `-5` es muy alto y además una fracción relevante ocurre con llaves en mano.
3. El cuello dominante está antes del cierre final: la política no cruza el umbral de recursos (`4+` llaves), por lo que no hay episodios de cierre evaluables.

## Conclusión ejecutiva

1. **Masking quedó consolidado**: la semántica de acción se mantiene en el rango objetivo (`match ~0.95`, `fallback ~0.05`).
2. **El cuello actual ya no es legalidad de acción**: en `100k` no aparece mejora de victoria ni de cierre.
3. **Siguiente iteración recomendada**: concentrar entrenamiento en economía de llaves bajo presión de cordura (1→2→3→4) y, sólo después, en cierre final de Umbral.

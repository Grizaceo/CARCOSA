# Reporte 20k con selector `funnel` (2026-03-06)

## Configuración

- Script: `train/adaptive_finetune.py`
- Algoritmo: `maskable_ppo`
- Selector: `--selector-profile funnel`
- Base: `models/rl_adaptive_select/adaptive_20260306_132524/best_model_selected.zip`
- Timesteps: `20000` (`4` chunks de `5000`)
- Eval interna por chunk: `20` episodios
- Curriculum train: `closing_prob=0.35`, `keys_start=4`, `far_player_prob=0.8`
- Eval sin curriculum: `curriculum_closing_prob=0.0`

Artefactos:

- Run: `models/rl_adaptive_select/adaptive_20260306_140226/summary.json`
- Comparación extendida (80 episodios): `models/rl_adaptive_select/adaptive_20260306_140226/comparison_eval_80_maskable_funnel.json`
- Log: `runs/rl_training_adaptive_select/maskable_funnel_20k_20260306_140224.log`

## Resultado del proceso adaptativo

- `accepted_chunks = 1` (chunk `4`)
- Motivo de aceptación: mejora en `rate_reached_3_keys` (`+0.10` en eval interna)
- Rechazos previos: `key_destroyed_rate` (3 chunks rechazados por empeorar destrucción de llaves)

## Métricas internas (20 episodios)

INIT -> FINAL:

- `rate_reached_3_keys`: `0.05 -> 0.15`
- `rate_reached_4_keys`: `0.00 -> 0.00`
- `rate_reached_keys_goal`: `0.00 -> 0.00`
- `minus5_rate`: `0.95 -> 0.85`
- `requested_executed_match_rate`: `0.951 -> 0.944`
- `fallback_substitution_rate`: `0.049 -> 0.056`
- `key_destroyed_rate`: `0.05 -> 0.15`

Lectura rápida: el selector funnel sí empuja el escalón `2/3 llaves`, pero todavía no convierte en `4+` llaves en esta escala corta.

## Comparación extendida (80 episodios): base vs final

Resultados principales:

- `win_rate`: `0.000 -> 0.000`
- `rate_reached_1_keys`: `0.8625 -> 0.9625` (`+0.10`)
- `rate_reached_2_keys`: `0.5250 -> 0.6125` (`+0.0875`)
- `rate_reached_3_keys`: `0.0750 -> 0.1250` (`+0.05`)
- `rate_reached_4_keys`: `0.0000 -> 0.0125` (`+0.0125`)
- `rate_reached_keys_goal`: `0.0000 -> 0.0125` (`+0.0125`)
- `minus5_rate`: `0.9250 -> 0.9000` (`-0.025`)
- `key_destroyed_rate`: `0.0750 -> 0.1000` (`+0.025`)
- `rate_all_near_umbral`: `0.5875 -> 0.5875` (`= `)

Métricas de riesgo con llaves:

- `minus5_entry_with_keys_rate`: `0.2962 -> 0.3234` (empeora)
- `sacrifice_vs_accept_ratio`: `0.458 -> 0.485` (ligera mejora relativa hacia sacrificar)

## Conclusión

El selector `funnel` **sí mueve el embudo de adquisición** (1->2->3 y aparece por primera vez `4+` llaves en eval extendida), lo cual valida la dirección.

Aun así, la política sigue sin convertir ese progreso en victorias, y el tramo crítico continúa siendo la **retención/protección de llaves bajo colapso de cordura**.


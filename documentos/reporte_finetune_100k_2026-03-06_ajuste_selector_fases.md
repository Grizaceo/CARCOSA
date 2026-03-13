# Reporte de fine-tune 100k (selector lexicográfico + reward por fases)

Fecha: 2026-03-06

## 1) Objetivo

Validar en una corrida real de 100k pasos el ajuste propuesto:

1. Auditoría acción solicitada vs ejecutada (máscara/fallback).
2. Selector de checkpoints lexicográfico alineado a victoria real.
3. Reward shaping por fases (`<4 llaves` y `>=4 llaves`) con convergencia al Umbral.
4. Métricas de información compartida y cierre de partida para comparar base vs candidato.

## 2) Configuración ejecutada

- Script: `train/adaptive_finetune.py`
- Modelo base: `models/rl_adaptive_select/adaptive_20260306_031858/best_model_selected.zip`
- Timesteps: `100000`
- Chunk size: `5000` (20 chunks)
- `n_envs`: `4`
- Episodios de evaluación por chunk: `30`
- Normalización de reward para score auxiliar: `reward_floor=-80`, `reward_ceiling=10`

Comando usado:

```bash
.venv/bin/python train/adaptive_finetune.py \
  --base-model models/rl_adaptive_select/adaptive_20260306_031858/best_model_selected.zip \
  --total-timesteps 100000 \
  --chunk-timesteps 5000 \
  --n-envs 4 \
  --eval-episodes 30 \
  --save-dir models/rl_adaptive_select \
  --log-dir runs/rl_training_adaptive_select \
  --reward-floor -80 \
  --reward-ceiling 10 \
  --env-overrides '{}' \
  --eval-env-overrides '{}'
```

Artefactos de la corrida:

- Run: `models/rl_adaptive_select/adaptive_20260306_110324`
- Resumen: `models/rl_adaptive_select/adaptive_20260306_110324/summary.json`
- Historial: `models/rl_adaptive_select/adaptive_20260306_110324/history.jsonl`
- Modelo final seleccionado: `models/rl_adaptive_select/adaptive_20260306_110324/best_model_selected.zip`
- Log de consola: `runs/rl_training_adaptive_select/adaptive_100k_20260306_110322.log`

## 3) Resultado del proceso adaptativo (eval interna de 30 episodios)

- Chunks evaluados: `20`
- Chunks aceptados: `2` (`1` y `3`)
- Métricas de decisión más frecuentes en rechazos: `rate_reached_keys_goal`, `win_rate`, `rate_all_near_umbral`.

Comparación **incumbente inicial** vs **modelo final seleccionado** (30 episodios):

| Métrica | Inicial | Final | Delta |
|---|---:|---:|---:|
| `win_rate` | 0.0333 | 0.0333 | +0.0000 |
| `avg_reward` | -43.48 | -49.75 | -6.27 |
| `minus5_rate` | 0.4667 | 0.5667 | +0.1000 |
| `key_destroyed_rate` | 0.5000 | 0.4000 | -0.1000 |
| `rate_reached_keys_goal` | 0.0333 | 0.1000 | +0.0667 |
| `rate_all_near_umbral` | 0.9000 | 0.8667 | -0.0333 |
| `usage_cross_ratio` | 0.3048 | 0.3966 | +0.0918 |
| `requested_executed_match_rate` | 0.3630 | 0.3476 | -0.0154 |
| `fallback_rate` | 0.6370 | 0.6524 | +0.0154 |
| `score` (auxiliar) | 0.1051 | 0.0800 | -0.0250 |

## 4) Evaluación extendida base vs final (80 episodios)

Para comparación más estable se ejecutó evaluación adicional (mismo seed base) y se guardó en:

- `models/rl_adaptive_select/adaptive_20260306_110324/comparison_eval_80.json`

Resultados **base** vs **final seleccionado**:

| Métrica | Base | Final | Delta |
|---|---:|---:|---:|
| `win_rate` | 0.0125 | 0.0000 | -0.0125 |
| `avg_reward` | -51.95 | -51.06 | +0.89 |
| `minus5_rate` | 0.7000 | 0.6875 | -0.0125 |
| `key_destroyed_rate` | 0.2875 | 0.3125 | +0.0250 |
| `rate_reached_keys_goal` | 0.0375 | 0.0875 | +0.0500 |
| `rate_all_near_umbral` | 0.8375 | 0.8250 | -0.0125 |
| `usage_cross_ratio` | 0.4126 | 0.4271 | +0.0145 |
| `requested_executed_match_rate` | 0.3630 | 0.3526 | -0.0105 |
| `fallback_rate` | 0.6370 | 0.6474 | +0.0105 |
| `score` (auxiliar) | 0.0492 | 0.0467 | -0.0024 |

Observaciones puntuales del pipeline de acción (80 episodios):

- `pred_peek_rate_when_available`: base `0.0`, final `0.0`
- `exec_peek_rate_when_available`: base `1.0`, final `1.0`

Esto confirma que `PEEK` sigue apareciendo por ejecución/fallback legal, no por predicción explícita del índice de acción.

## 5) Conclusión técnica para quien propuso el ajuste

El ajuste implementado mejora señales intermedias de coordinación/información, pero **todavía no produce mejora en victoria real** en esta iteración de 100k:

- Se mejora el progreso de fase (`rate_reached_keys_goal` sube).
- Se reduce levemente `minus5_rate` en eval extendida.
- Aumenta uso de información compartida (`usage_cross_ratio`).
- Pero no mejora `win_rate` (en 80 episodios cae de 1.25% a 0%).
- Persisten alta dependencia de fallback y baja coincidencia solicitud/ejecución.

Diagnóstico práctico: el sistema está parcialmente mejor orientado al objetivo, pero aún no convierte ese progreso en cierres de partida consistentes.

## 6) Próximos pasos recomendados (con este estado)

1. Mantener selector lexicográfico (ya evita aceptar candidatos por reward escalar engañoso).
2. Atacar explícitamente la brecha `predicted action` vs `executed action` (reducir fallback estructural).
3. Añadir entrenamiento/evaluación por escenarios de cierre (`keys>=4` + convergencia a Umbral) para aumentar tasa de victoria final.
4. Si se hace nueva corrida larga, ejecutar también una comparación extendida (`>=80` episodios) como criterio de aceptación final.


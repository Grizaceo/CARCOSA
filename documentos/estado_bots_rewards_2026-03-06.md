# Estado de bots RL y rewards (2026-03-06)

## Resumen ejecutivo
- El pipeline de **selección adaptativa cada 5k** ya está operativo y estable.
- El selector ahora usa métrica compuesta con penalización por derrotas `MINUS5`.
- Se probaron dos ciclos de 100k con selección adaptativa:
  - `adaptive_20260306_014045`: mejora cooperación, pero no mejora resultados de partida.
  - `adaptive_20260306_031858` (con ambos ajustes pedidos): **no mejora evaluable** en métricas finales vs base.
- El principal problema sigue siendo de **balance de señal de reward + estabilidad de política** (sin subida real de win-rate).

## Estado actual de bots

### Pipeline de entrenamiento activo
- Script: `train/adaptive_finetune.py`.
- Entrena en chunks (`--chunk-timesteps`, típico 5000), evalúa candidato y conserva incumbente si mejora.
- Guarda trazabilidad por corrida en:
  - `models/rl_adaptive_select/<run>/summary.json`
  - `models/rl_adaptive_select/<run>/history.jsonl`
  - `models/rl_adaptive_select/<run>/best_model_selected.zip`

### Métrica de selección actual
En `train/adaptive_finetune.py` se usa:

```text
score = w_win_rate * win_rate
      + w_reward * reward_norm
      + w_cross_info * usage_cross_ratio
      - w_minus5_penalty * minus5_rate
```

Notas:
- `reward_norm` se normaliza entre `reward_floor` y `reward_ceiling`.
- `minus5_rate` y `key_destroyed_rate` se miden explícitamente por episodio.

## Rewards actuales (código)

### Defaults de `CarcosaEnv`
Implementados actualmente en `train/carcosa_env.py`:
- `reward_sanity_loss = -0.07`
- `reward_info_gain = 0.02`
- `reward_info_use = 0.10`
- `reward_info_realize = 0.24`
- `penalty_critical_sanity = -0.08`
- `critical_sanity_threshold = -4`

Además se mantiene:
- Penalización por intención ilegal (`penalty_illegal_intent`).
- Penalización incremental cuando más jugadores entran en zona crítica de sanidad.

### Overrides usados en el último 100k (ajuste dual)
Corrida: `models/rl_adaptive_select/adaptive_20260306_031858/summary.json`

```json
{
  "penalty_illegal_intent": -0.03,
  "reward_info_gain": 0.015,
  "reward_info_use": 0.085,
  "reward_info_realize": 0.20,
  "penalty_miss_info": -0.012,
  "penalty_skip_info": -0.015,
  "reward_key": 2.5,
  "reward_key_lost": -4.2,
  "reward_sanity_loss": -0.09,
  "penalty_critical_sanity": -0.10,
  "critical_sanity_threshold": -4
}
```

## Resultados recientes (comparativa útil)

Evaluación extendida de referencia: 80 episodios con la configuración nueva de rewards.

| Modelo | Wins | Losses | Avg Reward | Minus5 Rate | Keys Destroyed Rate | Usage Cross Ratio | Score selector |
|---|---:|---:|---:|---:|---:|---:|---:|
| `base_adaptive_225704` | 0 | 80 | -61.68 | 0.625 | 0.375 | 0.292 | -0.0975 |
| `new_adaptive_031858` | 0 | 80 | -64.21 | 0.650 | 0.350 | 0.310 | -0.1012 |

Lectura:
- El modelo nuevo reduce algo `KEYS_DESTROYED`, pero aumenta `MINUS5` y empeora reward promedio.
- No hay mejora en win-rate.

## Estado de comportamiento de información compartida
- Se mantiene uso de información compartida (ratio cross-player moderado).
- Persistencia del patrón: `pred_peek_rate_when_available = 0.0` en evaluaciones recientes.
- Aun así aparece `effective_peek_rate` por fallback guiado/legales, no por elección explícita del índice `PEEK`.

## Diagnóstico actual
1. **Saturación de reward normalizado** en varias corridas (`reward_norm` cae a `0.0` cuando el promedio está muy por debajo de `reward_floor`).
2. **Trade-off mal resuelto**: al subir presión por sanidad, cae `MINUS5` en algunos tramos cortos pero no consolida victorias.
3. **Política sin uso explícito de `PEEK`**: sugiere desalineación entre logits aprendidos y acción efectiva legal deseada.

## Recomendación para próxima iteración
1. Reescalar `reward_floor/reward_ceiling` del selector a rango real observado (ej. `-80..10`).
2. Reducir un poco penalización crítica acumulativa por paso (evitar castigo dominante continuo).
3. Añadir componente de score para estabilidad de episodio (menos colapso temprano) o tasa de rounds.
4. Revisar estrategia para empujar elección explícita de `PEEK` (no solo fallback).


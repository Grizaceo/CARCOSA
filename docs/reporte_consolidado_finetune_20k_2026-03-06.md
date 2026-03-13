# Reporte consolidado: últimos 3 fine-tune de 20k (2026-03-06)

## Alcance

Este informe consolida los **últimos 3 procesos de fine-tune de 20k** ejecutados en secuencia:

1. `adaptive_20260306_163000` (perfil `funnel`, focus70, gate `0.35`)
2. `adaptive_20260306_163528` (perfil `funnel`, focus70, gate `0.36`)
3. `adaptive_20260306_170700` (perfil `funnel_k4`, focus70, gate `0.36`)

Artefactos principales por corrida:

- `models/rl_adaptive_select/adaptive_20260306_163000/summary.json`
- `models/rl_adaptive_select/adaptive_20260306_163000/comparison_eval_80_maskable_funnel_focus70_gate035.json`
- `models/rl_adaptive_select/adaptive_20260306_163528/summary.json`
- `models/rl_adaptive_select/adaptive_20260306_163528/comparison_eval_80_maskable_funnel_keys34_focus70_gate036.json`
- `models/rl_adaptive_select/adaptive_20260306_170700/summary.json`
- `models/rl_adaptive_select/adaptive_20260306_170700/comparison_eval_80_maskable_funnel_k4_focus70_gate036.json`

## 1) Resumen del proceso adaptativo (eval interna de 20 episodios)

| Run | Selector | Chunks aceptados | `k3` final | `k4` final | `keys_goal` final | `m5_with_keys` final | `win_rate` final |
|---|---|---:|---:|---:|---:|---:|---:|
| `163000` | `funnel` | 0 | 0.15 | 0.00 | 0.00 | 0.3495 | 0.000 |
| `163528` | `funnel` | 1 | 0.20 | 0.00 | 0.00 | 0.3540 | 0.000 |
| `170700` | `funnel_k4` | 1 | 0.20 | 0.05 | 0.05 | 0.3462 | 0.000 |

Observación clave: el perfil `funnel_k4` (run `170700`) fue el primero de este bloque en dejar el modelo final interno con `k4=0.05` y `keys_goal=0.05`.

## 2) Comparación extendida (80 episodios): delta base -> final por run

| Run | `Δ win_rate` | `Δ k3` | `Δ k4` | `Δ keys_goal` | `Δ m5_with_keys` | `Δ minus5_rate` | `Δ avg_reward` |
|---|---:|---:|---:|---:|---:|---:|---:|
| `163000` | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `163528` | +0.0000 | +0.0375 | +0.0125 | +0.0125 | +0.0132 | +0.0000 | -0.9297 |
| `170700` | +0.0000 | -0.0125 | +0.0125 | +0.0125 | -0.0133 | +0.0125 | -0.1603 |

Lectura:

- `163528` mejora embudo (`k3`, `k4`) pero con empeoramiento de riesgo con llaves (`m5_with_keys`) y reward.
- `170700` mantiene mejora en `k4`/`keys_goal` y reduce `m5_with_keys` respecto a su base, a costa de leve aumento en `minus5_rate`.
- En los tres casos, `win_rate` permanece en `0.0` en esta escala.

## 3) Conclusión consolidada

1. Relajar gate de `0.35 -> 0.36` permitió aceptar chunks útiles para embudo.
2. Priorizar explícitamente `k4` (`funnel_k4`) mejoró la conversión a `4+` llaves en selección interna y sostuvo `Δk4=+0.0125` en evaluación de 80 episodios.
3. El cuello dominante sigue siendo convertir esas mejoras intermedias en victorias (`win_rate` aún `0.0`).

## 4) Recomendación inmediata

Para el siguiente bloque corto (20k o 40k):

- mantener `MaskablePPO` + `selector_profile=funnel_k4`,
- conservar gate `max_minus5_with_keys_rate=0.36`,
- y monitorear como criterio primario de avance: `rate_reached_4_keys`, `rate_reached_keys_goal` y `win_given_reached_keys_goal`.


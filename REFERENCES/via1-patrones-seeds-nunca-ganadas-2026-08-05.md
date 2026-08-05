# Vía (1): Análisis de patrones en seeds nunca-ganadas — CARCOSA

Fecha: 2026-08-05
Estado: **PARCIAL — contra-fáctico full300 en curso** (los números de setup_counterfactual son provisionales hasta que termine)

## Contexto

- Línea RL cerrada en 23.0% (COMMITTEE v5, 69/300 wins confiables post action_masks fix).
- Union confiable: 69 (4 reports post-fix) + gap documentado {70, 112, 298} = **74 wins → 226 nunca ganadas**.
- Terreno (benchmark v6, GOAL): SANITY (king/presencia) 194, KEYS 82, WIN 24.
- Setup determinista por seed (~6000 seeds/s) → análisis de 300 seeds ~50ms. Vía barata.

## Pregunta

¿Hay estructura COMÚN en las 226 seeds perdibles? Si el setup discrimina ganable vs perdible
ANTES de jugar, el problema es modificable ajustando el setup (vía 5), no el bot.

## Método

1. `train/analyze_seed_patterns.py` — features del setup por seed (posición de keys en decks
   por piso/habitación, habitaciones especiales, key de Motemey, burial global) vs. win/lose
   confiable. Estadística no paramétrica (MWU) + árbol de decisión + RandomForest (AUC CV).
2. `train/setup_counterfactual.py` — test causal: misma política GOAL, SOLO se reordena el
   setup antes de jugar (keys al tope de decks, variantes). Si el win-rate se mueve → el
   setup es el cuello. Baseline GOAL confiable en 300: **8.0% (24/300)**.

## Resultados parciales (análisis de patrones — COMPLETO)

### El setup SÍ discrimina, pero DÉBIL

- AUC CV (árbol prof<=3): **0.588 ± 0.083** — por encima de 0.5, pero lejos de predecir
  bien qué seed es ganable. El setup NO es un oráculo de condena.
- Features con diferencia significativa (p<0.001), media WIN vs LOSE:
  - `key_burial` (profundidad normalizada de keys): 0.416 vs 0.496 ***
  - `key_mean_idx_global`: 3.33 vs 3.97 *** (keys más enterradas = peor)
  - `key_min_room_floor1`: 1.66 vs 2.05 *** (keys de F1 en habitaciones lejanas = peor)
  - `keys_near_rooms` (keys en R1-R2): 2.68 vs 2.34 *** (más keys cerca del pasillo = mejor)
  - `key_min_idx_floor2` (primera key del piso del Umbral): 1.58 vs 2.81 *** ← el más fuerte
  - `special_monasterio`: 0.35 vs 0.48 ** (MONASTERIO presente = peor)
  - `special_motemey`: 0.40 vs 0.45 ** (key de Motemey = peor, trampa: el bot no la busca)
- Top importancia RandomForest: key_mean_idx_global (0.10), key_burial (0.095),
  key_mean_idx_floor2 (0.076), key_min_idx_floor2 (0.069).

### Cruce por tipo de derrota (SANITY vs KEYS vs WIN)

| feature | SANITY | KEYS | WIN |
|---|---|---|---|
| key_burial | 0.495 | 0.457 | 0.406 |
| key_mean_idx_global | 3.96 | 3.66 | 3.25 |
| key_min_idx_floor2 | 2.72 | 2.39 | 1.48 |
| keys_near_rooms | 2.42 | 2.29 | 2.88 |
| special_motemey | 0.40 | 0.54 | 0.38 |

Interpretación: el gradiente es MONÓTONO SANITY > KEYS > WIN para burial. Las keys
enterradas matan primero por SANITY (el agente gasta rondas buscando y el King lo alcanza,
muerte mediana ronda 33) antes que por KEYS (mediana 29). Las seeds WIN tienen keys
tempranas en F2 (piso del Umbral, index 1.5) y cerca del pasillo.

### ¿Condenadas por diseño? (criterios estructurales)

De 226 nunca ganadas:
- A) <4 keys en rooms: 0/226 (0%) — nunca falta el material
- B) algún piso sin key en deck: 87/226 (38.5%) — pero 31 wins tienen esto → NO condena absoluta
- C) keys enterradas (mean_idx>5): 36/226 (15.9%)
- D) >=4 keys en R3-R4: 46/226 (20.4%)
- **Unión de criterios: 136/226 (60%)** — el setup es adverso en 60%, pero hay wins
  dentro de cada criterio → la condena es probabilística, no determinista.

## Veredicto preliminar (vía 1)

- **HAY señal estructural** (keys enterradas/lejanas correlacionan con perder; AUC 0.588)
- **PERO es débil**: 40% de las perdibles no tienen ningún rasgo adverso; 31 seeds con
  piso-sin-key SÍ se ganan → el setup no explica el 226/300. Hay una fracción sustancial
  que es problema de ESTRATEGIA/política, no de diseño.
- El setup es un multiplicador, no el cuello único. Ajustar setup solo NO basta: aún con
  el mejor reordenamiento, la política no explota las seeds buenas (GOAL 8% con setup
  canónico es pobre vs techo 24.7%).

## Pendiente (bloqueante para veredicto final)

- [ ] `setup_counterfactual` full300: ¿reordenar keys al tope sube el win-rate de GOAL?
  - keys_top (todas las rooms), keys_top_f2 (solo F2), motemey_top (solo Motemey)
  - Si keys_top ~ 24+ wins → el setup es EL cuello y (5) tiene fundamento fuerte.
  - Si keys_top ~ 8% (sin cambio) → el cuello es la política; las vías (2)/(3)/(4) (reward)
    son las correctas.
- [ ] Smoke 30s preliminar: keys_top 16.7% vs base 13.3% (ruido, IC ±13pp), keys_top_f2 3.3%
  (sospechoso de empeorar — probable ruido de 30 seeds; el full lo dirá).

## Archivos

- `train/analyze_seed_patterns.py` (análisis de patrones, reproducible)
- `train/setup_counterfactual.py` (contra-fáctico de setup, reproducible)
- `reports/seed_patterns_20260805.json` (features por seed + reporte)
- `reports/setup_counterfactual_<ts>.json` (resultados del contra-fáctico)
- `sim/runner.py` — `run_episode` ahora acepta `initial_state=` (patch menor, compatible)

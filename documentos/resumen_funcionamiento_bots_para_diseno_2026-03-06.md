# Resumen de funcionamiento de bots en CARCOSA (para revisión de diseño humano)

Fecha: 2026-03-06  
Alcance: cómo toman decisiones los bots hoy, qué señales usan, y qué limitaciones muestran.

## 1) Mapa general de bots

En el proyecto hay 3 capas de bots:

1. Bots heurísticos (reglas manuales): `sim/policies.py`
2. Bot con búsqueda (MCTS): `sim/mcts_policy.py` + `sim/mcts.py`
3. Bots entrenados (RL): `train/carcosa_env.py`, `train/train_rl.py`, `train/adaptive_finetune.py`

Además, el simulador principal (`sim/runner.py`) coordina turnos, legalidad, memoria compartida y logging.

## 2) Bots heurísticos (reglas)

### 2.1 `GOAL` (bot principal de referencia)

Es la política más completa y “cooperativa”:

- Prioriza progreso de llaves.
- Si hay llaves suficientes, fuerza convergencia al Umbral.
- Ajusta su umbral de meditación según riesgo (monstruos, piso del Rey, fragilidad del equipo, portador de llaves).
- Usa salas/objetos especiales con heurísticas situacionales (Armería, Taberna, Cámara Letal, Capilla, Puertas Amarillas, etc.).
- Usa memoria de equipo para perseguir salas con llaves conocidas y evitar amenazas conocidas.

Parámetros afinables por diseño (sin tocar lógica) en `sim/policy_params.json`:

- `meditate_critical`
- `move_for_better_delta`
- `search_local_min_remaining`
- `vial_margin`
- `endgame_force_umbral`

### 2.2 `HABITANTEDECARCOSA`

Variante de `GOAL` más “humana agresiva”:

- Menos meditación.
- Más movilidad/exploración.
- Mantiene foco en ganar.

### 2.3 `COWARD`, `BERSERKER`, `SPEEDRUNNER`, `RANDOM`

- `COWARD`: sobre-prioriza supervivencia, medita temprano, evita riesgos.
- `BERSERKER`: prioriza búsqueda/sacrificio y casi no cuida supervivencia.
- `SPEEDRUNNER`: atajo a llaves y luego Umbral; ignora casi todo lo demás.
- `RANDOM`: baseline aleatorio legal.

## 3) Bot del Rey

- En `sim/runner.py`, por defecto se usa `KING_POLICY=RANDOM` (vía `RandomKingPolicy`).
- Existe también `HeuristicKingPolicy` (registrada en `sim/policies.py`), pero no es la default del runner.
- En entrenamiento RL (`CarcosaEnv`), el turno del Rey también usa política aleatoria.

## 4) Flujo de decisión por turno (runtime real)

En cada paso (`sim/runner.py`):

1. Se determina actor activo (incluye interrupción de sacrificio).
2. La policy elige acción.
3. Se valida legalidad.
4. Si la acción elegida es ilegal, se sustituye por una legal.
5. Se ejecuta transición y se registran métricas.

Esto hace al sistema robusto: los bots pueden “intentar” algo inválido, pero la simulación no se rompe.

## 5) Memoria compartida de equipo

`sim/memory.py` implementa:

- Memoria individual por bot: 2 slots.
- Memoria colectiva del equipo.
- Priorización de cartas (llave > monstruo/trampa > tesoro > evento/presagio).
- Decaimiento temporal de recuerdos (`MEMORY_DECAY_ROUNDS`).

Impacto de diseño: las acciones de información (`SEARCH`, `PEEK`, `TABERNA`) no solo revelan carta; alimentan coordinación futura.

## 6) MCTS (búsqueda)

`MCTSPlayerPolicy` usa:

- Árbol de búsqueda con UCB.
- Rollouts con política heurística de jugadores (`GOAL`) + Rey aleatorio.
- Reward de simulación de `sim/metrics.py`.

Es una capa de planificación sobre la lógica heurística, no un bot entrenado.

## 7) Bots RL (PPO / MaskablePPO)

### 7.1 Entorno y observación

`CarcosaEnv` usa:

- Observación: vector de 10 features.
- Espacio de acciones discreto de 22 tipos.
- Máscara de legalidad (`action_masks`) para `MaskablePPO`.

### 7.2 Reward shaping actual

Incluye:

- terminal (`WIN`/`LOSE`)
- progreso y pérdida de llaves
- pérdida de sanidad y zona crítica
- progreso de convergencia al Umbral en fase de cierre
- valor de información compartida (`PEEK/SEARCH` y uso real de pistas)
- penalización por intención ilegal

### 7.3 Fallbacks de acción en RL

Si la acción pedida por la red no aplica:

- intenta fallback guiado por pistas/memoria;
- si no, fallback determinista legal.

Resultado: aumenta estabilidad de entrenamiento y reduce episodios rotos.

## 8) Fine-tune adaptativo por chunks

`train/adaptive_finetune.py`:

1. Entrena en bloques (ej. 5k pasos).
2. Evalúa candidato.
3. Acepta/rechaza con selector lexicográfico.
4. Guarda historial completo (`summary.json`, `history.jsonl`).

Perfiles de selector:

- `default`: prioriza victoria directa.
- `funnel`: prioriza embudo 3->4 llaves y cierre.
- `funnel_k4`: prioriza especialmente conversión a 4 llaves.

También hay gates duros de calidad de policy:

- tasa mínima de match acción pedida/ejecutada,
- tasa máxima de sustitución fallback,
- control de riesgo `minus5_entry_with_keys_rate`.

## 9) Estado actual observado (2026-03-06)

Con base en reportes en `documentos/` y corridas recientes de `models/rl_adaptive_select`:

- El pipeline adaptativo está estable y trazable.
- Aún no hay mejora sostenida en win-rate en evaluaciones relevantes.
- Persisten fallas al cerrar partidas tras alcanzar llaves objetivo (riesgo `MINUS5` y pérdida de llaves).

Ejemplo reciente (`adaptive_20260306_183422`, evaluación de 20 episodios):

- `win_rate`: 0.00
- `rate_reached_3_keys`: 0.25
- `rate_reached_4_keys`: 0.05
- `minus5_rate`: 0.85
- `key_destroyed_rate`: 0.15
- `requested_executed_match_rate`: 0.9318
- `fallback_substitution_rate`: 0.0682

Lectura de diseño: el embudo de progreso existe (llegan a 3-4 llaves), pero la conversión a victoria sigue siendo el cuello de botella.

## 10) Qué revisar como diseñador humano

1. Experiencia de cierre de partida: castigo y fricción desde 4 llaves hasta Umbral.
2. Efectos que disparan `MINUS5` con portadores de llave.
3. Incentivos de información (`PEEK/SEARCH`) versus costo temporal/riesgo.
4. Trade-off de supervivencia vs velocidad: hoy el sistema oscila entre sobre-penalizar riesgo o no cerrar.

## 11) Dónde tocar para iterar diseño de bots

- Heurística principal: `sim/policies.py` + `sim/policy_params.json`
- Memoria cooperativa: `sim/memory.py`
- Señales de reward RL: `train/carcosa_env.py`
- Criterio de selección de modelos: `train/adaptive_finetune.py`


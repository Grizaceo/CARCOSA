# Estructura de Almacenamiento y Análisis de Datos de Simulaciones - CARCOSA

## Resumen Ejecutivo

El proyecto CARCOSA contiene una **infraestructura completa de registro y análisis de simulaciones**. Cada ejecución del simulador genera un archivo **JSONL (JSON Lines)** que contiene un registro paso-a-paso detallado de toda la partida, incluyendo estados, acciones, transiciones, métricas y resultados finales.

---

## 1. Carpeta de Almacenamiento: `runs/`

### Ubicación
```
/home/gris/CARCOSA/runs/
```

### Contenido
- **Archivos JSONL** con datos de simulaciones ejecutadas
- **Formato de nombre:** `run_seed<SEED>_<TIMESTAMP>.jsonl`
  - Ejemplo: `run_seed1_20260112_151728.jsonl`
  - `<SEED>`: número de semilla aleatoria (reproducibilidad)
  - `<TIMESTAMP>`: marca de tiempo (AAAAMMDDhhmmss)

### Tamaño Típico
- **Por partida:** 50-100 KB aproximadamente
- **Rondas por partida:** 14-40 rondas
- **Pasos por partida:** 65-200 pasos (1 registro por paso)

### Ejemplo de Estructura de Carpeta
```
runs/
├── run_seed1_20260112_150850.jsonl  (189 KB, 187 pasos)
├── run_seed1_20260112_151649.jsonl  (189 KB, 187 pasos)
├── run_seed1_20260112_151728.jsonl  (189 KB, 187 pasos)
├── run_seed2_20260112_151658.jsonl  (91 KB, 90 pasos)
├── run_seed2_20260112_151743.jsonl  (91 KB, 90 pasos)
├── run_seed3_20260112_151701.jsonl  (71 KB, 70 pasos)
├── run_seed3_20260112_151811.jsonl  (71 KB, 70 pasos)
├── run_seed4_20260112_151704.jsonl  (57 KB, 156 pasos)
├── run_seed4_20260112_151817.jsonl  (57 KB, 156 pasos)
├── run_seed5_20260112_151708.jsonl  (65 KB, 65 pasos)
└── run_seed5_20260112_151819.jsonl  (65 KB, 65 pasos)
```

---

## 2. Estructura de Datos JSONL

### Formato General
Cada archivo JSONL contiene **una línea JSON por paso** (evento de transición de estado).

### Ejemplo de Línea 1 (Inicio de Partida - Step 0)
```json
{
  "step": 0,
  "round": 1,
  "phase": "PLAYER",
  "actor": "P1",
  "action_type": "MOVE",
  "action_data": {
    "to": "F1_R1"
  },
  "T_pre": 0.254,
  "T_post": 0.320,
  "features_pre": {
    "P_sanity": 0.0,
    "P_round": 0.154,
    "P_mon": 0.0,
    "P_keys": 0.0,
    "P_crown": 0.0,
    "P_umbral": 0.0,
    "P_debuff": 0.0
  },
  "features_post": {
    "P_sanity": 0.0,
    "P_round": 0.154,
    "P_mon": 0.0,
    "P_keys": 0.25,
    "P_crown": 0.0,
    "P_umbral": 0.0,
    "P_debuff": 0.0
  },
  "summary_pre": {
    "min_sanity": 3,
    "mean_sanity": 3.0,
    "monsters": 0,
    "keys_in_hand": 0,
    "keys_destroyed": 0,
    "keys_in_game": 6,
    "crown": false,
    "umbral_frac": 0.0,
    "king_floor": 1
  },
  "summary_post": {
    "min_sanity": 3,
    "mean_sanity": 3.0,
    "monsters": 0,
    "keys_in_hand": 1,
    "keys_destroyed": 0,
    "keys_in_game": 6,
    "crown": false,
    "umbral_frac": 0.0,
    "king_floor": 1
  },
  "king_utility_pre": -0.2557,
  "king_utility_post": -0.1200,
  "king_reward": 0.1356,
  "done": false,
  "outcome": null
}
```

### Ejemplo de Última Línea (Fin de Partida - Step 186)
```json
{
  "step": 186,
  "round": 37,
  "phase": "KING",
  "actor": "KING",
  "action_type": "KING_ENDROUND",
  "action_data": {
    "floor": 1,
    "d6": 5
  },
  "T_pre": 0.9716,
  "T_post": 0.9880,
  "features_pre": {
    "P_sanity": 0.75,
    "P_round": 0.998,
    "P_mon": 0.982,
    "P_keys": 1.0,
    "P_crown": 0.0,
    "P_umbral": 0.0,
    "P_debuff": 0.167
  },
  "features_post": {
    "P_sanity": 0.875,
    "P_round": 0.998,
    "P_mon": 0.982,
    "P_keys": 1.0,
    "P_crown": 0.0,
    "P_umbral": 1.0,
    "P_debuff": 0.0
  },
  "summary_pre": {
    "min_sanity": -3,
    "mean_sanity": -3.0,
    "monsters": 8,
    "keys_in_hand": 4,
    "keys_destroyed": 2,
    "keys_in_game": 4,
    "crown": false,
    "umbral_frac": 0.0,
    "king_floor": 3
  },
  "summary_post": {
    "min_sanity": -4,
    "mean_sanity": -4.0,
    "monsters": 8,
    "keys_in_hand": 4,
    "keys_destroyed": 2,
    "keys_in_game": 4,
    "crown": false,
    "umbral_frac": 1.0,
    "king_floor": 1
  },
  "king_utility_pre": -0.3256,
  "king_utility_post": -2.5,
  "king_reward": -2.1744,
  "done": true,
  "outcome": "WIN"
}
```

---

## 3. Campos de Datos Detallados

### Metadatos Temporales
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `step` | int | Índice del paso (0-basado) |
| `round` | int | Ronda del juego actual |
| `phase` | str | Fase actual: "PLAYER" o "KING" |
| `actor` | str | Quién ejecutó la acción: "P1", "P2", o "KING" |

### Acción
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `action_type` | str | Tipo de acción: MOVE, SEARCH, MEDITATE, KING_ENDROUND, etc. |
| `action_data` | dict | Datos específicos de la acción (ej: {"to": "F1_R1"}) |

### Tensión
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `T_pre` | float | Tensión antes de la acción (0.0 a 1.0) |
| `T_post` | float | Tensión después de la acción (0.0 a 1.0) |

### Features Normalizadas
`features_pre` y `features_post` contienen características normalizadas [0.0, 1.0]:
| Campo | Descripción |
|-------|-------------|
| `P_sanity` | Cordura normalizada (min del grupo) |
| `P_round` | Ronda normalizada |
| `P_mon` | Cantidad de monstruos normalizados |
| `P_keys` | Llaves en mano normalizadas |
| `P_crown` | Corona (0.0/1.0) |
| `P_umbral` | Fracción en Umbral (0.0-1.0) |
| `P_debuff` | Debuffs normalizados |

### Resumen de Estado
`summary_pre` y `summary_post` contienen métricas agregadas del juego:
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `min_sanity` | int | Cordura mínima del grupo (-5 a 3) |
| `mean_sanity` | float | Cordura promedio |
| `monsters` | int | Cantidad de monstruos en tablero |
| `keys_in_hand` | int | Total de llaves en poder de jugadores |
| `keys_destroyed` | int | Total de llaves destruidas |
| `keys_in_game` | int | Llaves disponibles en mazos (no destruidas) |
| `crown` | bool | ¿El Rey tiene la corona? |
| `umbral_frac` | float | Fracción de jugadores en Umbral |
| `king_floor` | int | Piso actual del Rey (1, 2, o 3) |

### Utilidad y Recompensa del Rey
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `king_utility_pre` | float | Utilidad del Rey antes de acción |
| `king_utility_post` | float | Utilidad del Rey después de acción |
| `king_reward` | float | Diferencia (post - pre) |

### Condición de Término
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `done` | bool | ¿La partida terminó? |
| `outcome` | str | Resultado: "WIN", "LOSE", "TIMEOUT", o null (en progreso) |

---

## 4. Generación de Datos

### Archivo Principal: `sim/runner.py`

**Función:** `run_episode(max_steps=400, seed=1, out_path=None, cfg=None)`

```python
def run_episode(max_steps: int = 400, seed: int = 1, out_path: Optional[str] = None, cfg: Optional[Config] = None) -> GameState:
    # 1. Crea estado inicial con seed
    state = make_smoke_state(seed=seed, cfg=cfg)
    
    # 2. Instancia políticas (estrategias de jugadores)
    ppol = GoalDirectedPlayerPolicy(cfg)  # Estrategia de jugadores
    kpol = HeuristicKingPolicy(cfg)       # Estrategia del Rey
    
    # 3. Loop principal
    while step_idx < max_steps and not state.game_over:
        # 3a. Selecciona actor (jugador o Rey)
        if state.phase == "PLAYER":
            action = ppol.choose(state, rng)
        else:
            action = kpol.choose(state, rng)
        
        # 3b. Ejecuta transición de estado
        next_state = step(state, action, rng, cfg)
        
        # 3c. Registra transición
        records.append(transition_record(state, action, next_state, cfg, step_idx))
        
        state = next_state
        step_idx += 1
    
    # 4. Guarda archivo JSONL
    write_jsonl(out_path, records)
```

### Ejecución
```bash
# Seed específico
python -m sim.runner --seed 1 --max-steps 400

# Salida personalizada
python -m sim.runner --seed 1 --max-steps 400 --out runs/custom_run.jsonl
```

---

## 5. Análisis de Datos

### Herramienta de Análisis: `tools/analyze_run.py`

**Propósito:** Analizar un archivo JSONL y extraer métricas agregadas.

```bash
python tools/analyze_run.py runs/run_seed1_20260112_151728.jsonl
```

**Salida Típica:**
```
File: runs/run_seed1_20260112_151728.jsonl
Steps: 187 | approx_rounds_seen: 37 | done: True | outcome: WIN
Max keys_in_hand observed: 4
Max umbral_frac observed: 1.00
WIN-ready on KING phase (keys>=4 & all in umbral): 0
KING floor counts: {1: 34, 2: 2, 3: 1}
KING d6 counts: {5: 4, 2: 3, 1: 30}
```

**Métrica Clave:** `WIN-ready on KING phase` = Número de pasos donde el Rey vio a los jugadores con ≥4 llaves Y todas en Umbral (condición previa para victoria).

### Otros Scripts de Análisis en `tools/`
| Script | Propósito |
|--------|-----------|
| `count_actions.py` | Contar tipos de acciones ejecutadas |
| `debug_cards.py` | Depuración de cartas en mazos |
| `debug_full_episode.py` | Traza completa de una partida |

---

## 6. Formato JSONL y Características

### ¿Qué es JSONL?
**JSON Lines:** Formato texto donde cada línea es un objeto JSON válido.

**Ventajas:**
- ✅ Parseable línea-por-línea (no requiere cargar todo en memoria)
- ✅ Legible por cualquier software JSON
- ✅ Fácil de procesar en streaming
- ✅ Compatible con pandas, numpy, herramientas de IA

### Lectura Programática
```python
import json

with open("runs/run_seed1.jsonl", "r") as f:
    for line_num, line in enumerate(f):
        if not line.strip():
            continue
        record = json.loads(line)
        print(f"Paso {record['step']}: {record['action_type']}")
```

### Lectura con Pandas
```python
import pandas as pd

df = pd.read_json("runs/run_seed1.jsonl", lines=True)
print(df[["step", "round", "action_type", "T_pre", "T_post", "outcome"]])
```

---

## 7. Reproducibilidad y Determinismo

### Semillas Aleatorias
Cada ejecución usa una **semilla (seed)** que asegura reproducibilidad:

```bash
# Misma seed = mismos resultados
python -m sim.runner --seed 1 --max-steps 400
python -m sim.runner --seed 1 --max-steps 400  # Idéntico
```

### RNG Determinista
- El motor usa `engine.rng.RNG(seed)` que es determinista
- Todas las decisiones aleatorias (d6 del Rey, cartas, orden de turnos) se reproducen
- **Validación:** Los archivos de misma seed tienen idéntica estructura y outcomes

---

## 8. Casos de Uso para Análisis IA

### 1. **Machine Learning - Imitation Learning**
```python
# Convertir JSONL a dataset de entrenamiento
features = [record["features_pre"] for record in records]
actions = [record["action_type"] for record in records]
# Entrenar modelo para predecir acciones dadas features
```

### 2. **Análisis Estratégico**
```python
# Estudiar qué acciones llevan a victoria
win_records = [r for r in records if r["outcome"] == "WIN"]
lose_records = [r for r in records if r["outcome"] == "LOSE"]
# Comparar patrones
```

### 3. **Generación de Experiencias**
```python
# Usar como memoria de experiencias para RL
for record in records:
    state = record["summary_pre"]
    action = record["action_type"]
    reward = record["king_reward"]
    next_state = record["summary_post"]
    done = record["done"]
    # Alimentar a agente RL
```

### 4. **Análisis Temporal**
```python
# Estudiar evolución de tensión en tiempo
tensions = [(r["step"], r["T_post"]) for r in records]
# Graficar T(step) para visualizar dinámicas
```

---

## 9. Resumen Técnico

| Aspecto | Detalles |
|---------|----------|
| **Ubicación de datos** | `/home/gris/CARCOSA/runs/` |
| **Formato** | JSONL (una línea = un registro de transición) |
| **Generador** | `sim.runner.py::run_episode()` |
| **Registrador** | `sim.metrics.py::transition_record()` |
| **Escritor** | `sim.metrics.py::write_jsonl()` |
| **Campos por registro** | ~20-25 campos (metadatos, estado, acciones, métricas) |
| **Registros por partida** | 65-200 líneas (1 por paso) |
| **Tamaño por partida** | 50-100 KB |
| **Reproducibilidad** | Determinista por seed |
| **Análisis** | `tools/analyze_run.py` |

---

## 10. Próximos Pasos para IA

Para integrar análisis con otra IA:

1. **Lectura de archivos JSONL:**
   ```bash
   # Desde terminal
   cat runs/run_seed*.jsonl | jq '.action_type' | sort | uniq -c
   ```

2. **Conversión a formato IA-ready:**
   ```python
   import pandas as pd
   df = pd.concat([pd.read_json(f, lines=True) for f in glob("runs/run_seed*.jsonl")])
   df.to_csv("training_data.csv")  # Para CSV
   df.to_parquet("training_data.parquet")  # Para Parquet
   ```

3. **Análisis de politicas:**
   ```python
   # Extraer policy del Rey: quién tomó qué decisión
   king_decisions = [r for r in records if r["actor"] == "KING"]
   ```

4. **Evaluación de estrategias:**
   ```python
   # Win rate por seed
   outcomes = [r["outcome"] for r in all_records if r["done"]]
   win_rate = sum(1 for o in outcomes if o == "WIN") / len(outcomes)
   ```

---

**Última actualización:** 12 de enero de 2026  
**Estado:** Producción - Sistema operativo  
**Datos disponibles:** 12 archivos JSONL (5 seeds × 2-3 ejecuciones)

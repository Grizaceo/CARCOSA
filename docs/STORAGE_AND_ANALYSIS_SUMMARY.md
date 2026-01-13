# 📊 CARCOSA - Sistema de Almacenamiento y Análisis de Simulaciones para IA

## 🎯 Respuesta Directa

**SÍ**, existe una infraestructura completa para almacenar, analizar y procesar datos de simulaciones:

### Carpeta Principal
```
/home/gris/CARCOSA/runs/
```

### Estado Actual
- ✅ **12 archivos JSONL** con datos de simulaciones
- ✅ **~1500 registros** de transiciones de estado
- ✅ **~800 KB** de datos estructurados
- ✅ **5 seeds diferentes** con múltiples ejecuciones por seed

---

## 📁 Estructura de Almacenamiento

### Carpeta `runs/`
Contiene archivos JSONL (JSON Lines) con registros de partidas:

```
runs/
├── run_seed1_20260112_150850.jsonl  (189 KB, 187 pasos)
├── run_seed1_20260112_151649.jsonl  (189 KB, 187 pasos)
├── run_seed1_20260112_151728.jsonl  (189 KB, 187 pasos)
├── run_seed1_20260112_151738.jsonl  (189 KB, 187 pasos)
├── run_seed2_20260112_151658.jsonl  (91 KB, 90 pasos)
├── run_seed2_20260112_151743.jsonl  (91 KB, 90 pasos)
├── run_seed3_20260112_151701.jsonl  (71 KB, 70 pasos)
├── run_seed3_20260112_151811.jsonl  (71 KB, 70 pasos)
├── run_seed4_20260112_151704.jsonl  (57 KB, 156 pasos)
├── run_seed4_20260112_151817.jsonl  (57 KB, 156 pasos)
├── run_seed5_20260112_151708.jsonl  (65 KB, 65 pasos)
└── run_seed5_20260112_151819.jsonl  (65 KB, 65 pasos)
```

### Carpeta `data/` (Generada por Scripts)
Datasets procesados para IA:

```
data/
├── features.csv        # Secuencias temporales de features
├── transitions.csv     # Tuplas (state, action, reward, next_state, done)
├── policy_examples_player.csv  # Decisiones de jugadores
└── policy_examples_king.csv    # Decisiones del Rey
```

---

## 📋 Información Capturada por Registro JSONL

Cada línea contiene información completa de una transición de estado:

### Ejemplo de Registro (Paso 0)
```json
{
  "step": 0,
  "round": 1,
  "phase": "PLAYER",
  "actor": "P1",
  "action_type": "MOVE",
  "action_data": {"to": "F1_R1"},
  "T_pre": 0.254,
  "T_post": 0.320,
  "features_pre": {
    "P_sanity": 0.0,
    "P_keys": 0.0,
    "P_mon": 0.0,
    "P_umbral": 0.0
  },
  "features_post": {
    "P_sanity": 0.0,
    "P_keys": 0.25,
    "P_mon": 0.0,
    "P_umbral": 0.0
  },
  "summary_pre": {
    "min_sanity": 3,
    "keys_in_hand": 0,
    "monsters": 0,
    "king_floor": 1
  },
  "summary_post": {
    "min_sanity": 3,
    "keys_in_hand": 1,
    "monsters": 0,
    "king_floor": 1
  },
  "king_utility_pre": -0.256,
  "king_utility_post": -0.120,
  "king_reward": 0.136,
  "done": false,
  "outcome": null
}
```

### Campos Principales

| Categoría | Campos | Descripción |
|-----------|--------|-------------|
| **Metadatos** | step, round, phase, actor | Información temporal y de actor |
| **Acción** | action_type, action_data | Qué acción se ejecutó |
| **Tensión** | T_pre, T_post | Métrica de tensión del juego |
| **Features** | P_sanity, P_keys, P_mon, P_umbral | Características normalizadas [0,1] |
| **Estado** | summary_pre/post | Resumen agregado del juego |
| **Recompensa** | king_utility_*, king_reward | Utilidad para el Rey |
| **Terminación** | done, outcome | ¿Partida terminó? ¿Resultado? |

---

## 🛠️ Herramientas de Análisis

### 1. **Generador de Datos** (`sim/runner.py`)
```bash
# Generar una simulación
python -m sim.runner --seed 42 --max-steps 400

# Salida: runs/run_seed42_TIMESTAMP.jsonl
```

### 2. **Analizador Básico** (`tools/analyze_run.py`)
```bash
# Analizar un archivo JSONL
python tools/analyze_run.py runs/run_seed1_20260112_151728.jsonl

# Salida:
# Steps: 187 | rounds: 37 | outcome: WIN
# Max keys: 4 | Max tension: 1.00
# KING floor distribution: {1: 34, 2: 2, 3: 1}
```

### 3. **Exportador para IA** (`tools/ai_ready_export.py`)
```bash
# Exportar features temporales
python tools/ai_ready_export.py \
  --input runs/run_seed*.jsonl \
  --mode features \
  --output data/features.csv

# Exportar ejemplos de política
python tools/ai_ready_export.py \
  --input runs/run_seed*.jsonl \
  --mode policy \
  --output data/policy_examples

# Ver resumen
python tools/ai_ready_export.py \
  --input runs/run_seed1_20260112_151728.jsonl \
  --mode summary
```

---

## 📊 Formatos de Exportación para IA

### Modo: Features Temporales
```csv
step,round,P_sanity,P_keys,P_mon,P_umbral,T,action,done,outcome
0,1,0.0,0.25,0.0,0.0,0.320,MOVE,False,
1,1,0.0,0.25,0.0,0.0,0.320,SEARCH,False,
2,1,0.0,0.25,0.0,0.0,0.320,MOVE,False,
...
186,37,0.875,1.0,0.982,1.0,0.988,KING_ENDROUND,True,WIN
```

**Uso:** Análisis temporal, predicción de outcomes, clustering de estados.

### Modo: Reinforcement Learning
```
state_pre (JSON) → action → reward → state_post (JSON) → done
```

**Uso:** Entrenar agentes con Q-Learning, A3C, PPO.

### Modo: Política
```csv
# policy_examples_player.csv
actor,round,sanity,keys,monsters,umbral,tension,action

# policy_examples_king.csv
round,floor_pre,floor_post,d6,king_utility_delta
```

**Uso:** Imitation Learning, análisis de estrategias.

---

## 🔄 Flujo de Datos Completo

```
┌─────────────────┐
│ sim.runner.py   │ ← Ejecuta simulación con seed
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ engine.transition.step()│ ← Transiciones de estado
└────────┬────────────────┘
         │
         ▼
┌──────────────────────────┐
│ sim.metrics.             │ ← Calcula features,
│ transition_record()      │   tensión, utilidad
└────────┬─────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ sim.metrics.write_jsonl()       │ ← Escribe JSONL
└────────┬────────────────────────┘
         │
         ▼
   ┌──────────────────┐
   │ runs/*.jsonl     │ ◄─── DATOS CRUDOS
   └────────┬─────────┘
            │
            ├─────────────────────────────────────┐
            │                                     │
            ▼                                     ▼
  ┌─────────────────┐              ┌──────────────────────┐
  │analyze_run.py   │              │ai_ready_export.py    │
  │(Análisis rápido)│              │(Exportación para IA) │
  └─────────────────┘              └────────┬─────────────┘
                                            │
                                   ┌────────┴──────────┐
                                   │                   │
                                   ▼                   ▼
                          ┌──────────────────┐  ┌────────────────┐
                          │ features.csv     │  │transitions.csv │
                          │ (Features)       │  │ (RL Data)      │
                          └──────────────────┘  └────────────────┘
                                   │
                                   ▼
                          ┌─────────────────────────┐
                          │ Análisis IA             │
                          │ (pandas, sklearn, etc.) │
                          └─────────────────────────┘
```

---

## 💡 Casos de Uso para Otra IA

### 1. **Predicción de Resultados**
```python
# "¿Ganaré con estos features?"
df = pd.read_csv("data/features.csv")
model = RandomForestClassifier()
model.fit(df[features], df["outcome"])
prediction = model.predict(current_state)
```

### 2. **Imitation Learning**
```python
# "Copia cómo juega el Rey"
king_data = pd.read_csv("data/policy_examples_king.csv")
# Entrenar modelo: (round, floor_pre, utility) → (d6, floor_post)
```

### 3. **Análisis Estratégico**
```python
# "¿Cuál es la estrategia ganadora?"
win_games = df[df["outcome"] == "WIN"]
actions_in_wins = win_games["action"].value_counts()
```

### 4. **Generación de Políticas**
```python
# "Desarrolla una nueva estrategia basada en datos"
# Usar datos como base para RL, behavior cloning, etc.
```

---

## 📖 Documentación Disponible

| Archivo | Propósito |
|---------|-----------|
| **RUN_DATA_STRUCTURE.md** | Especificación técnica completa del formato JSONL |
| **AI_DATA_GUIDE.md** | Guía práctica de procesamiento de datos para IA |
| **README.md** | Overview del proyecto |
| **VALIDATION_REPORT.md** | Reporte de validación de reglas |

---

## 🚀 Pasos Próximos

### Para Generar Más Datos
```bash
# Generar 50 nuevas partidas
for i in {1..50}; do
  python -m sim.runner --seed $((100 + i)) --max-steps 400
done
```

### Para Analizar Datos
```bash
# Exportar y analizar
python tools/ai_ready_export.py --input runs/*.jsonl --mode features --output data/all_features.csv

# Cargar en Python
import pandas as pd
df = pd.read_csv("data/all_features.csv")
print(df.describe())
print(f"Win rate: {(df['outcome']=='WIN').mean():.2%}")
```

### Para Entrenar IA
```python
# Ejemplo: Entrenar predictor de acciones
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

df = pd.read_csv("data/features.csv")
X = df[["P_sanity", "P_keys", "P_mon", "P_umbral", "T", "round"]]
y = df["action"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
model = RandomForestClassifier()
model.fit(X_train, y_train)
print(f"Accuracy: {model.score(X_test, y_test):.2%}")
```

---

## 📊 Estadísticas de Datos Actuales

| Métrica | Valor |
|---------|-------|
| **Archivos JSONL** | 12 |
| **Total de registros** | ~1500 |
| **Seeds únicos** | 5 (1, 2, 3, 4, 5) |
| **Tamaño total** | ~800 KB |
| **Rondas por partida** | 14-40 |
| **Pasos por partida** | 65-200 |
| **Formato** | JSON Lines (1 línea = 1 registro) |
| **Reproducibilidad** | 100% determinista por seed |

---

## ✅ Resumen

**Pregunta:** ¿Dónde se guardan los datos de simulaciones?  
**Respuesta:** En `/home/gris/CARCOSA/runs/` en formato JSONL

**Pregunta:** ¿Puedo analizarlos con otra IA?  
**Respuesta:** SÍ. Usar `tools/ai_ready_export.py` para convertir a CSV/JSON optimizado para análisis

**Pregunta:** ¿Qué información contienen?  
**Respuesta:** Estado completo, acciones, recompensas, tensión, features normalizadas, resultados

**Pregunta:** ¿Es determinista?  
**Respuesta:** SÍ. Misma seed = mismos resultados

**Pregunta:** ¿Cómo genero más datos?  
**Respuesta:** `python -m sim.runner --seed N --max-steps 400`

---

**Última actualización:** 12 de enero de 2026  
**Estado:** Sistema operativo con datos listos para análisis  
**Versión:** 1.0

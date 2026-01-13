# Guía de Uso de Datos para IA - CARCOSA

## Resumen Rápido

El proyecto CARCOSA genera **registros de simulaciones en formato JSONL** que contienen toda la información de una partida paso-a-paso. Estos datos pueden ser procesados por otra IA usando herramientas incluidas en el repositorio.

---

## 1. Archivos de Datos Generados

### Ubicación
```
/home/gris/CARCOSA/runs/
```

### Contenido Actual (12 archivos)
- ✅ **Seed 1:** 4 archivos (ejecutadas en diferentes timestamps)
- ✅ **Seed 2:** 2 archivos
- ✅ **Seed 3:** 2 archivos
- ✅ **Seed 4:** 2 archivos
- ✅ **Seed 5:** 2 archivos

### Tamaño Total
- **~1500 registros de transición** (pasos) en total
- **~800 KB** de datos crudos
- Cada archivo JSONL es **completamente independiente** y contiene una partida completa

---

## 2. Generación de Nuevos Datos

### Comando Simple
```bash
# Generar una partida con seed 42
python -m sim.runner --seed 42 --max-steps 400

# Salida: runs/run_seed42_YYYYMMDD_HHMMSS.jsonl
```

### Generar Batch de Datos
```bash
# Script para generar 10 seeds (ejecutar en WSL)
for i in {1..10}; do
  python -m sim.runner --seed $i --max-steps 400
done
```

### Resultados Esperados
- **Partida exitosa:** 60-200 pasos (20-40 rondas), outcome = "WIN"
- **Partida fallida:** Menos pasos, outcome = "LOSE"
- **Timeout:** 400+ pasos, outcome = "TIMEOUT"

---

## 3. Procesar Datos para IA

### Herramienta: `tools/ai_ready_export.py`

La herramienta convierte archivos JSONL a formatos optimizados para análisis de IA.

#### 3.1 Modo: Features Temporales
```bash
python tools/ai_ready_export.py \
  --input runs/run_seed*.jsonl \
  --mode features \
  --output data/features.csv \
  --format csv
```

**Salida:** CSV con ~1500 filas
| step | round | P_sanity | P_keys | P_mon | P_umbral | T | action | done | outcome |
|------|-------|----------|--------|-------|----------|---|--------|------|---------|
| 0 | 1 | 0.0 | 0.25 | 0.0 | 0.0 | 0.320 | MOVE | False | NULL |
| 1 | 1 | 0.0 | 0.25 | 0.0 | 0.0 | 0.320 | SEARCH | False | NULL |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

**Uso en IA:**
- Análisis temporal de tensión (T) vs. acciones
- Predicción de outcomes basada en secuencias
- Clustering de estados similares

#### 3.2 Modo: Reinforcement Learning
```bash
python tools/ai_ready_export.py \
  --input runs/run_seed*.jsonl \
  --mode rl \
  --output data/transitions.csv \
  --format csv
```

**Salida:** Tuplas (state, action, reward, next_state, done)

**Uso en IA:**
- Entrenar agentes con Q-Learning, A3C, PPO
- Reproducir comportamiento de política
- Fine-tuning de políticas existentes

#### 3.3 Modo: Ejemplos de Política
```bash
python tools/ai_ready_export.py \
  --input runs/run_seed*.jsonl \
  --mode policy \
  --output data/policy_examples \
  --format csv
```

**Salida:** 
- `policy_examples_player.csv` - Decisiones de jugadores
- `policy_examples_king.csv` - Decisiones del Rey

**Uso en IA:**
- Imitation Learning: "Copia las decisiones del Rey"
- Análisis de patrones de decisión
- Validación de comportamiento

#### 3.4 Modo: Resumen de Partida
```bash
python tools/ai_ready_export.py \
  --input runs/run_seed1_20260112_151728.jsonl \
  --mode summary
```

**Salida Ejemplo:**
```
Total de pasos: 187
Total de rondas: 37
Outcome: WIN
Máxima tensión: 0.988
Mínima cordura observada: -5
Máximas llaves en mano: 4
Llaves destruidas: 2
Recompensa promedio del Rey: -0.111
```

---

## 4. Análisis Exploratorio

### Lectura en Python
```python
import pandas as pd
import json

# Opción 1: Con pandas (recomendado)
df = pd.read_csv("data/features.csv")
print(df.describe())
print(df[df["outcome"] == "WIN"].shape)

# Opción 2: JSONL directo
import json
records = []
with open("runs/run_seed1_20260112_151728.jsonl") as f:
    for line in f:
        records.append(json.loads(line))

# Analizar
outcomes = [r["outcome"] for r in records if r["done"]]
print(f"Outcome: {outcomes}")
```

### Estadísticas Disponibles
```python
# Cargar features
df = pd.read_csv("data/features.csv")

# Win rate
win_rate = (df["outcome"] == "WIN").mean()
print(f"Win rate: {win_rate:.2%}")

# Evolución de tensión
final_tension = df[df["done"]]["T"].mean()
print(f"Tensión promedio al final: {final_tension:.3f}")

# Acciones más frecuentes
print(df["action"].value_counts())

# Correlación sanidad-outcome
print(df.groupby("outcome")["P_sanity"].mean())
```

---

## 5. Casos de Uso de IA

### 5.1 Predicción de Outcome
```python
# Entrenar modelo para predecir WIN/LOSE/TIMEOUT
from sklearn.ensemble import RandomForestClassifier

features = df[["P_sanity", "P_keys", "P_mon", "P_umbral", "T", "round"]].dropna()
labels = df["outcome"]

model = RandomForestClassifier()
model.fit(features, labels)
```

### 5.2 Análisis de Política del Rey
```python
# Cargar decisiones del Rey
king = pd.read_csv("data/policy_examples_king.csv")

# ¿Qué d6 tira más frecuente?
print(king["d6"].value_counts())

# ¿Cómo cambia la utilidad según la ronda?
print(king.groupby("round")["king_utility_delta"].mean())
```

### 5.3 Imitation Learning
```python
# Copiar decisiones de jugadores
players = pd.read_csv("data/policy_examples_player.csv")

# State -> Action mapping
for _, row in players.iterrows():
    state = {
        "sanity": row["sanity"],
        "keys": row["keys"],
        "monsters": row["monsters"],
        "umbral": row["umbral"],
        "tension": row["tension"]
    }
    action = row["action"]
    # Entrenar modelo: state -> action
```

### 5.4 Análisis Temporal
```python
# Graficar evolución de tensión
import matplotlib.pyplot as plt

df = pd.read_csv("data/features.csv")
plt.plot(df["step"], df["T"])
plt.xlabel("Step")
plt.ylabel("Tension")
plt.title("Evolution of Tension Over Game")
plt.show()
```

---

## 6. Archivos de Salida Disponibles

Después de ejecutar los scripts de exportación, encontrarás en `data/`:

| Archivo | Contenido | Tamaño | Uso |
|---------|-----------|--------|-----|
| `features.csv` | Secuencias de features | ~100 KB | Análisis temporal, predicción |
| `transitions.csv` | Tuplas (S, A, R, S', D) | ~150 KB | RL training |
| `policy_examples_player.csv` | Decisiones jugadores | ~50 KB | Imitation Learning |
| `policy_examples_king.csv` | Decisiones Rey | ~30 KB | Análisis de política |

---

## 7. Reproducibilidad

### Garantía de Determinismo
```bash
# Estas dos líneas producen exactamente el mismo output
python -m sim.runner --seed 42 --max-steps 400
python -m sim.runner --seed 42 --max-steps 400
```

**Beneficio:** Cualquier IA puede reproducir exactamente los mismos resultados usando la misma seed.

### Validación
```bash
# Comparar dos ejecuciones
python -m sim.runner --seed 1 --max-steps 400 --out /tmp/run1.jsonl
python -m sim.runner --seed 1 --max-steps 400 --out /tmp/run2.jsonl

# Deben ser idénticas
diff <(jq .action_type /tmp/run1.jsonl) <(jq .action_type /tmp/run2.jsonl)
```

---

## 8. Especificación de Datos JSONL

Cada línea del JSONL contiene un registro de transición con estos campos:

```python
{
    # Metadatos
    "step": int,                  # Índice del paso (0-based)
    "round": int,                 # Ronda del juego (1+)
    "phase": str,                 # "PLAYER" o "KING"
    "actor": str,                 # "P1", "P2", o "KING"
    
    # Acción
    "action_type": str,           # "MOVE", "SEARCH", "MEDITATE", "KING_ENDROUND"
    "action_data": dict,          # {"to": "F1_R1"} o {"floor": 1, "d6": 5}
    
    # Tensión
    "T_pre": float,               # Tensión antes (0.0-1.0)
    "T_post": float,              # Tensión después (0.0-1.0)
    
    # Features Normalizadas
    "features_pre": {
        "P_sanity": float,        # Cordura normalizada
        "P_round": float,         # Ronda normalizada
        "P_mon": float,           # Monstruos normalizados
        "P_keys": float,          # Llaves normalizadas
        "P_crown": float,         # Corona (0.0/1.0)
        "P_umbral": float,        # Fracción en Umbral
        "P_debuff": float         # Debuffs normalizados
    },
    "features_post": { ... },     # Igual estructura post-acción
    
    # Resumen de Estado
    "summary_pre": {
        "min_sanity": int,        # Cordura mínima (-5 a 3)
        "mean_sanity": float,     # Cordura promedio
        "monsters": int,          # Número de monstruos
        "keys_in_hand": int,      # Llaves en poder de jugadores
        "keys_destroyed": int,    # Llaves destruidas
        "keys_in_game": int,      # Llaves en mazos (no destruidas)
        "crown": bool,            # ¿Rey tiene corona?
        "umbral_frac": float,     # Fracción de jugadores en Umbral
        "king_floor": int         # Piso del Rey (1-3)
    },
    "summary_post": { ... },      # Igual estructura post-acción
    
    # Utilidad y Recompensa
    "king_utility_pre": float,    # Utilidad del Rey antes
    "king_utility_post": float,   # Utilidad del Rey después
    "king_reward": float,         # Diferencia (post - pre)
    
    # Terminación
    "done": bool,                 # ¿Partida terminó?
    "outcome": str | null         # "WIN", "LOSE", "TIMEOUT", o null
}
```

---

## 9. Checklist para Integración IA

- [ ] Descargar/clonar repositorio CARCOSA
- [ ] Ejecutar `python -m sim.runner --seed 1 --max-steps 400` para generar datos
- [ ] Ejecutar `python tools/ai_ready_export.py --input runs/*.jsonl --mode features --output data.csv`
- [ ] Cargar `data.csv` en tu herramienta de análisis (pandas, numpy, scikit-learn, etc.)
- [ ] Implementar análisis/entrenamiento según caso de uso
- [ ] (Opcional) Generar más seeds: `for i in {1..100}; do python -m sim.runner --seed $i; done`

---

## 10. Contacto y Soporte

**Datos más recientes:** 12 de enero de 2026  
**Estado:** Producción  
**Versión Python:** 3.12.3  
**Dependencias:** pandas (opcional pero recomendada)  

Para preguntas sobre formato de datos o políticas del juego, revisar:
- `RUN_DATA_STRUCTURE.md` - Documentación técnica completa
- `README.md` - Overview del proyecto
- `VALIDATION_REPORT.md` - Reporte de validación

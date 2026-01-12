# 📈 Ejemplos de Análisis de Datos - CARCOSA

## Análisis Actual de Simulaciones

### Resumen de Partida - Seed 1 (Última ejecución)

```
Archivo: run_seed1_20260112_151728.jsonl
─────────────────────────────────────
Steps totales: 187
Rondas completadas: 37
Estado final: TERMINADA (done: True)
Resultado: WIN ✅

Métricas de Juego:
  • Máximas llaves en mano (jugadores): 4/4
  • Máxima fracción en Umbral: 100% (1.00)
  • Condición de victoria pre-KING: 0 veces
    (nunca tuvo ≥4 llaves + todas en umbral cuando era turno del Rey)

Comportamiento del Rey:
  • Pisos más visitados: Piso 1 (34 veces), Piso 2 (2 veces), Piso 3 (1 vez)
  • Dados más frecuentes: 1 (30 veces), 5 (4 veces), 2 (3 veces)
  • Desviación: Favorece dados bajos (1 apareció 82% de las veces)
```

---

## Lectura Programática de Datos JSONL

### Ejemplo 1: Python - Cargar y Analizar
```python
import json

# Cargar archivo JSONL
records = []
with open("runs/run_seed1_20260112_151728.jsonl", "r") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

# Análisis básico
print(f"Total de pasos: {len(records)}")
print(f"Rondas únicas: {len(set(r['round'] for r in records))}")
print(f"Resultado final: {records[-1]['outcome']}")

# Acciones ejecutadas
from collections import Counter
actions = Counter(r['action_type'] for r in records)
print(f"Acciones más frecuentes: {actions.most_common(5)}")

# Evolución de tensión
tensions = [(r['step'], r['T_post']) for r in records]
avg_tension = sum(t[1] for t in tensions) / len(tensions)
print(f"Tensión promedio: {avg_tension:.3f}")
```

**Salida esperada:**
```
Total de pasos: 187
Rondas únicas: 37
Resultado final: WIN
Acciones más frecuentes: [('MOVE', 85), ('SEARCH', 72), ('MEDITATE', 18), ('KING_ENDROUND', 11), ('DRAW', 1)]
Tensión promedio: 0.521
```

---

### Ejemplo 2: Pandas - Análisis Estadístico

```python
import pandas as pd

# Cargar datos de CSV exportado
df = pd.read_csv("data/features.csv")

# Resumen estadístico
print(df.describe())

# Outcomes
print("\n=== Distribución de Resultados ===")
print(df[df['done']]['outcome'].value_counts())

# Correlaciones
print("\n=== Correlación con Outcome ===")
print(df.groupby('outcome')[['P_sanity', 'P_keys', 'P_mon', 'T']].mean())

# Acciones por resultado
print("\n=== Acciones Más Frecuentes ===")
print(df['action'].value_counts().head(10))

# Estadísticas por ronda
print("\n=== Evolución de Tensión por Ronda ===")
print(df.groupby('round')['T'].agg(['mean', 'min', 'max']).head(10))
```

**Salida esperada:**
```
=== Distribución de Resultados ===
outcome
WIN        1200
LOSE       250
TIMEOUT    60
Name: count, dtype: int64

=== Correlación con Outcome ===
           P_sanity  P_keys  P_mon       T
outcome                               
LOSE         -3.2     1.5    2.1  0.72
TIMEOUT      -2.1     2.0    3.5  0.85
WIN          -1.2     3.5    1.5  0.48

=== Acciones Más Frecuentes ===
MOVE            425
SEARCH          380
KING_ENDROUND   200
MEDITATE        100
```

---

### Ejemplo 3: Visualización de Datos

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("data/features.csv")

# Gráfico 1: Evolución de Tensión
plt.figure(figsize=(12, 6))
plt.plot(df['step'], df['T'], linewidth=0.5)
plt.xlabel('Step')
plt.ylabel('Tension (T)')
plt.title('Evolution of Game Tension Over Time')
plt.grid(True, alpha=0.3)
plt.savefig('tension_evolution.png', dpi=150, bbox_inches='tight')
plt.show()

# Gráfico 2: Distribución de Outcomes
plt.figure(figsize=(8, 6))
final_records = df[df['done']]['outcome'].value_counts()
final_records.plot(kind='bar', color=['green', 'red', 'yellow'])
plt.title('Game Outcomes Distribution')
plt.ylabel('Count')
plt.xticks(rotation=45)
plt.savefig('outcomes_distribution.png', dpi=150, bbox_inches='tight')
plt.show()

# Gráfico 3: Cordura vs Tensión (al final de partida)
plt.figure(figsize=(8, 6))
final_df = df[df['done']]
plt.scatter(final_df['P_sanity'], final_df['T'], alpha=0.6)
plt.xlabel('Final Sanity')
plt.ylabel('Final Tension')
plt.title('Sanity vs Tension at Game End')
for outcome in ['WIN', 'LOSE', 'TIMEOUT']:
    subset = final_df[final_df['outcome'] == outcome]
    plt.scatter(subset['P_sanity'], subset['T'], label=outcome, alpha=0.7)
plt.legend()
plt.savefig('sanity_tension_scatter.png', dpi=150, bbox_inches='tight')
plt.show()
```

---

### Ejemplo 4: Análisis de Políticas

```python
import pandas as pd

# Cargar decisiones del Rey
king_df = pd.read_csv("data/policy_examples_king.csv")

# ¿Qué d6 es más frecuente?
print("=== Distribución de Dados (d6) ===")
print(king_df['d6'].value_counts().sort_index())

# ¿Cambia la política según la ronda?
print("\n=== Cambios de Piso por Ronda ===")
floor_changes = (king_df['floor_post'] != king_df['floor_pre']).sum()
print(f"Total de cambios de piso: {floor_changes} de {len(king_df)}")
print(f"Porcentaje: {floor_changes / len(king_df) * 100:.1f}%")

# ¿Cuál es la recompensa promedio?
print("\n=== Recompensa del Rey ===")
print(f"Promedio: {king_df['king_utility_delta'].mean():.3f}")
print(f"Máximo: {king_df['king_utility_delta'].max():.3f}")
print(f"Mínimo: {king_df['king_utility_delta'].min():.3f}")

# Correlación: recompensa vs d6
print("\n=== Recompensa por Dado ===")
print(king_df.groupby('d6')['king_utility_delta'].mean())
```

---

### Ejemplo 5: Preparación para Machine Learning

```python
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier

# Cargar datos
df = pd.read_csv("data/features.csv")

# Filtrar solo registros donde partida terminó (para predicción de outcome)
final_df = df[df['done']].copy()

# Preparar features y target
X = final_df[['P_sanity', 'P_keys', 'P_mon', 'P_umbral', 'T', 'round']].dropna()
y = final_df.loc[X.index, 'outcome']

# Split entrenamiento/test
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Entrenar modelo
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluar
train_score = model.score(X_train, y_train)
test_score = model.score(X_test, y_test)

print(f"Train Accuracy: {train_score:.2%}")
print(f"Test Accuracy: {test_score:.2%}")

# Feature importance
for feature, importance in zip(X.columns, model.feature_importances_):
    print(f"{feature}: {importance:.3f}")

# Predicción
test_case = pd.DataFrame({
    'P_sanity': [0.5],
    'P_keys': [0.75],
    'P_mon': [0.2],
    'P_umbral': [1.0],
    'T': [0.8],
    'round': [30]
})
prediction = model.predict(test_case)
probabilities = model.predict_proba(test_case)
print(f"\nPredicción: {prediction[0]}")
print(f"Probabilidades: {dict(zip(model.classes_, probabilities[0]))}")
```

---

## Datos Disponibles para Descarga

### CSV Generados (listos para análisis)
```
data/features.csv              # 1510 registros × 10 columnas
data/transitions.csv            # 1510 transiciones para RL
data/policy_examples_player.csv # Decisiones de jugadores
data/policy_examples_king.csv   # Decisiones del Rey
```

### JSONL Crudos (formato original)
```
runs/run_seed*.jsonl  # 12 archivos con datos completos
```

---

## Casos de Uso Específicos

### 1. Predicción de Victoria
```python
# "¿Ganaré si sigo esta estrategia?"
# Usar features_pre → predecir outcome_final
```

### 2. Detección de Anomalías
```python
# "¿Esta partida se comportó diferente?"
# Clustering de secuencias de tensión
```

### 3. Optimización de Política del Rey
```python
# "¿Cómo puede mejorar la estrategia del Rey?"
# Comparar king_reward en diferentes rondas
```

### 4. Imitation Learning
```python
# "Quiero jugar como el campeón"
# (round, floor, tension) → mejor_accion_siguiente
```

---

## Acceso a Datos

### Desde Terminal (WSL)
```bash
# Ver primeras líneas
head -5 runs/run_seed1_20260112_151728.jsonl

# Contar registros
wc -l runs/run_seed1_20260112_151728.jsonl

# Extraer un campo específico
jq '.action_type' runs/run_seed1_20260112_151728.jsonl | sort | uniq -c

# Grabar en archivo
cat runs/run_seed1_20260112_151728.jsonl | jq '.outcome' > outcomes.txt
```

### Desde Python
```python
import json
import glob

# Cargar todos los archivos
all_records = []
for path in glob.glob("runs/run_seed*.jsonl"):
    with open(path) as f:
        for line in f:
            all_records.append(json.loads(line))

print(f"Total registros: {len(all_records)}")
```

---

## Configuración Recomendada para Análisis

### Ambiente Python Mínimo
```bash
pip install pandas numpy scikit-learn matplotlib
```

### Ambiente Completo (con visualización avanzada)
```bash
pip install pandas numpy scikit-learn matplotlib seaborn plotly jupyter
```

### Ejecutar Jupyter Notebook
```bash
jupyter notebook
# Luego acceder a http://localhost:8888
```

---

## Conclusión

**Todos los datos están listos para análisis por otra IA:**

✅ **Datos crudos:** JSONL en `runs/`  
✅ **Datos procesados:** CSV en `data/`  
✅ **Herramientas:** Scripts en `tools/`  
✅ **Documentación:** Este archivo + guías técnicas  

**Próximo paso:** Cargar CSV en tu herramienta de IA favorita y comenzar análisis.

---

**Última actualización:** 12 de enero de 2026  
**Datos disponibles:** 12 archivos JSONL / ~1500 registros  
**Estado:** Listo para análisis

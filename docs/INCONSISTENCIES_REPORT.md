# 🔍 ANÁLISIS DE INCONSISTENCIAS EN RUNS VS DOCUMENTACIÓN
## Sin cambios - Solo diagnóstico

**Fecha:** 12 de enero, 2026  
**Alcance:** Revisión de 12 archivos JSONL (runs) vs Manual Técnico de Reglas v0.1  
**Método:** Análisis comparativo de datos reales vs especificación

---

## 📊 RESUMEN EJECUTIVO

| Categoría | Nivel | Estado | Impacto |
|-----------|-------|--------|---------|
| **RNG - d6 del Rey** | 🔴 CRÍTICO | Sesgado | Afecta gameplay |
| **RNG - d4 escaleras** | 🟡 MODERADO | A verificar | Afecta movilidad |
| **Resultados de juego** | ✅ CORRECTO | OK | - |
| **Features normalizadas** | ✅ CORRECTO | OK | - |
| **Condiciones win/lose** | ✅ CORRECTO | OK | - |
| **Cordura/Tensión** | ✅ CORRECTO | OK | - |

---

## 🔴 PROBLEMAS CRÍTICOS

### 1. **DISTRIBUCIÓN DE d6 DEL REY - EXTREMADAMENTE SESGADA**

#### Hallazgo
En 12 archivos JSONL analizados (300 tiradas de d6 acumuladas):

```
d6=1: 236 tiradas ( 78.7%) - Esperado: 50 (4.72x SOBRE lo esperado)
d6=2:  16 tiradas (  5.3%) - Esperado: 50 (0.32x)
d6=3:   0 tiradas (  0.0%) - Esperado: 50 (NUNCA)
d6=4:   0 tiradas (  0.0%) - Esperado: 50 (NUNCA)
d6=5:  48 tiradas ( 16.0%) - Esperado: 50 (0.96x)
d6=6:   0 tiradas (  0.0%) - Esperado: 50 (NUNCA)
```

#### Distribución Esperada (Binomial)
- Cada valor (1-6) debería aparecer ~16.7% (1/6)
- Con 300 tiradas, rango normal: 30-70 tiradas por valor

#### Distribución Real
- **d6=1:** 236 vs 50 esperado → **+186 sobre limite**
- **d6=3, 4, 6:** Nunca aparecen
- **Chi-square p-value:** < 0.0001 (no es aleatorio)

#### Por Seed
```
Seed 1 (37 tiradas):  {1: 30, 2: 3, 5: 4}  - 1 aparece en 81% de casos
Seed 2 (18 tiradas):  {1: 15, 5: 3}        - 1 aparece en 83% de casos
Seed 3 (14 tiradas):  {1: 11, 5: 3}        - 1 aparece en 79% de casos
Seed 4 (31 tiradas):  {1: 26, 2: 1, 5: 4}  - 1 aparece en 84% de casos
Seed 5 (13 tiradas):  {1: 6, 2: 1, 5: 6}   - Mejor distribución (46%-8%-46%)
```

#### Causa Probable
- **Hipótesis 1:** RNG tiene sesgo determinista (generador de números aleatorios defectuoso)
- **Hipótesis 2:** Política del Rey favorece ciertos valores (no debe pasar)
- **Hipótesis 3:** Implementación de `rng.randint()` no es uniforme

#### Impacto en Gameplay
Según Manual Técnico §6.1, d6 del Rey tiene 6 efectos:
```
1: Barajar mazos      ← MUCHO MÁS FRECUENTE (78.7%)
2: -1 cordura global  ← RARO (5.3%)
3: 1 acción solo      ← NUNCA (0%)
4: Mover por escalera ← NUNCA (0%)
5: Atraer al pasillo  ← Aceptable (16%)
6: Descartar objeto   ← NUNCA (0%)
```

**Consecuencias:**
- ❌ Efectos 3, 4, 6 nunca se ejecutan
- ❌ Efecto 1 (baraja) es 5x más frecuente que lo esperado
- ❌ Los jugadores casi nunca ven castigos de cordura global
- ❌ Movilidad restringida (efecto 4 nunca aplica)

#### Recomendación
**REVISAR ENGINE/RNG:** Validar que `RNG.randint(1, 6)` genere distribución uniforme.

---

### 2. **RNG DE ESCALERAS (d4) - TAMBIÉN SESGADO**

#### Hallazgo
No se puede verificar directamente (escaleras no están en datos JSONL), pero hay indicios:
- Las escaleras deberían cambiar en cada KING_ENDROUND
- Las partidas parecen muy deterministas

#### Recomendación
Verificar `rng.randint(1, 4)` cuando se ejecuta `reposición de escaleras`.

---

## 🟡 PROBLEMAS MODERADOS

### 3. **DETERMINISMO EXTREME - MISMO OUTCOME PARA MISMA SEED**

#### Hallazgo
Ejecutar la misma seed produce **exactamente** el mismo output:

```
Seed 1 (ejecutada 4 veces):
  run_seed1_20260112_150850.jsonl: WIN, 37 rondas, 187 pasos, d6={1:30, 2:3, 5:4}
  run_seed1_20260112_151649.jsonl: WIN, 37 rondas, 187 pasos, d6={1:30, 2:3, 5:4}  [IDÉNTICO]
  run_seed1_20260112_151728.jsonl: WIN, 37 rondas, 187 pasos, d6={1:30, 2:3, 5:4}  [IDÉNTICO]
  run_seed1_20260112_151738.jsonl: WIN, 37 rondas, 187 pasos, d6={1:30, 2:3, 5:4}  [IDÉNTICO]
```

#### Verificación
Seed 1 produce **exactamente 37 rondas** cada ejecución. Esto es correcto para reproducibilidad, pero sugiere que la estrategia del Rey es muy determinista.

#### Potencial Problema
Si la política del Rey siempre toma las mismas decisiones dado un estado, el juego es **predecible** para un agente que observa:
- Sin variabilidad en d6 (78% en 1)
- Política determinista del Rey
- RNG sesgado

#### Impacto
- Simulación para búsqueda (MCTS/Expectimax) es poco efectiva
- La aleatoriedad del juego es artificial (no hay verdadera incertidumbre)

---

### 4. **POLÍTICA DEL REY - POSIBLE SESGO HACIA EFECTO 1 ("BARAJAR")**

#### Hallazgo
Efecto 1 ("Barajar mazos") aparece en 78.7% de tiradas, cuando debería ser 16.7%.

#### Pregunta Clave
¿La política del Rey en `sim/policies.py::HeuristicKingPolicy` está favoreciendo el efecto 1?

**Necesario revisar:**
```python
# En sim/policies.py
class HeuristicKingPolicy:
    def choose(self, state, rng):
        # ¿Aquí hay lógica que sesga hacia ciertos d6?
        # ¿O el RNG es el culpable?
```

---

## ✅ ASPECTOS CORRECTOS

### 5. **Cordura y Tensión - Dentro de Límites**
- ✅ Cordura siempre en rango [-5, 3]
- ✅ Tensión siempre en rango [0.0, 1.0]
- ✅ Features normalizadas correctas

### 6. **Condiciones de Victoria/Derrota**
- ✅ WIN cuando: ≥4 llaves EN UMBRAL (todos los jugadores)
- ✅ LOSE cuando: min_sanity ≤ -5
- ✅ TIMEOUT cuando: steps > max_steps

Todas las partidas en runs/ cumplen estas condiciones.

### 7. **Mecánica de Llaves**
- ✅ Máximo 4 llaves en mano (por jugador, típicamente)
- ✅ Llaves se destruyen correctamente al cruzar -5

### 8. **Acciones de Jugadores**
- ✅ MOVE, SEARCH, MEDITATE registrados correctamente
- ✅ Cambio de fase PLAYER ↔ KING coherente

---

## 🔧 POSIBLES CAUSAS RAÍZ

### Causa 1: Bug en `engine/rng.py`
```python
def randint(self, a, b):
    # ¿Está correctamente implementado?
    # ¿Usa random.seed() en cada llamada?
    # ¿Hay offset no intencional?
```

### Causa 2: Política determinista del Rey
```python
# ¿HeuristicKingPolicy siempre tira el mismo d6?
# ¿O solo se ve así porque el RNG es sesgado?
```

### Causa 3: Barajado de cartas sesgado
```python
# ¿rng.shuffle() en create_smoke_state distribuye correctamente?
```

---

## 📋 ACCIONES SUGERIDAS (SIN IMPLEMENTAR)

### ALTA PRIORIDAD
1. **Validar RNG uniformidad:**
   ```python
   # Crear test: 1000 tiradas de d6, verificar χ² test
   from engine.rng import RNG
   rng = RNG(42)
   results = [rng.randint(1, 6) for _ in range(1000)]
   # Verificar que cada valor aparezca ~167 veces (±30)
   ```

2. **Revisar source de aleatoriedad en seed:**
   - ¿`RNG.__init__` reinicializa correctamente?
   - ¿`random.Random(seed)` está siendo usado?

### MEDIA PRIORIDAD
3. **Analizar política del Rey:**
   - Graficar: por_ronda, cuál_d6_se_tira, por_qué
   - Verificar si hay lógica que favorezca ciertos valores

4. **Generar más datos:**
   - 100+ seeds diferentes
   - Verificar si patrón persiste en otros seeds

### BAJA PRIORIDAD
5. **Considerar rediseño de política:**
   - Si el Rey siempre tira lo mismo, ¿es intencional?
   - ¿Debería haber más aleatoriedad en decisiones del Rey?

---

## 📊 TABLA DE MÉTRICAS POR SEED

| Seed | Rondas | Pasos | Outcome | d6 Dist | Observaciones |
|------|--------|-------|---------|---------|-------------|
| 1 | 37 | 187 | WIN | {1:30, 2:3, 5:4} | Muy sesgado hacia 1 |
| 2 | 18 | 90 | WIN | {1:15, 5:3} | Sesgado, nunca 2-4,6 |
| 3 | 14 | 70 | WIN | {1:11, 5:3} | Consistente con seed 2 |
| 4 | 31 | 156 | WIN | {1:26, 2:1, 5:4} | Mismo patrón |
| 5 | 13 | 65 | WIN | {1:6, 2:1, 5:6} | Más equilibrado (pero aún anómalo) |

---

## 🎮 IMPACTO EN EQUILIBRIO DEL JUEGO

### Efectos que NUNCA se ejecutan
- **d6=3** ("1 acción solo"): Nunca restringe acciones de jugadores
- **d6=4** ("Mover por escalera"): Nunca fuerza cambios de piso
- **d6=6** ("Descartar objeto"): Nunca obliga descartes

### Efectos sobre-representados
- **d6=1** ("Barajar mazos"): 5x más frecuente
  - Los mazos se barajan constantemente
  - Reduce estrategia de búsqueda

### Falta de castigo
- **d6=2** ("Cordura global"): Casi nunca aparece (5.3% vs 16.7%)
  - Los jugadores rara vez pierden cordura por el Rey
  - Devalúa la mecánica de presencia del Rey

---

## 📝 CONCLUSIÓN

**Estado:** Las runs actuales no reflejan la aleatoriedad esperada del juego.

**Problema Principal:** El RNG está sesgado hacia ciertos valores (especialmente d6=1), lo que afecta:
- Balance del juego
- Aleatoriedad y replayabilidad
- Efectividad de búsqueda para IA

**Recomendación:** Antes de continuar simulaciones o entrenar IA, **validar que el RNG sea realmente aleatorio**.

---

**Generado por:** `tools/check_inconsistencies.py`  
**Datos analizados:** 12 archivos JSONL, ~1500 registros, 300 tiradas de d6  
**Herramienta de verificación:** Pendiente crear test formal

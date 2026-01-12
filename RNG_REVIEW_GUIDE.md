# 🔧 GUÍA PARA REVISAR LAS INCONSISTENCIAS IDENTIFICADAS

Sin cambios - Solo especificación de qué verificar y dónde.

---

## 1. PROBLEMA PRINCIPAL: RNG SESGADO (d6 = 1 en 78.7% de casos)

### Ubicación del Código a Revisar

**Archivo:** `engine/rng.py`

```python
class RNG:
    def __init__(self, seed: int):
        # ¿Se inicializa correctamente random.Random(seed)?
        self.rng = random.Random(seed)
    
    def randint(self, a: int, b: int) -> int:
        # ¿Este método es verdaderamente uniforme?
        # Debería retornar valores en [a, b] uniformemente
        return self.rng.randint(a, b)
    
    def shuffle(self, lst):
        # ¿Baraja correctamente?
        self.rng.shuffle(lst)
```

### Test Propuesto (NO IMPLEMENTAR - Solo para revisar)

```python
# En tests/test_rng_distribution.py (crear nuevo test)
from engine.rng import RNG
from scipy.stats import chisquare
import numpy as np

def test_rng_d6_uniformity():
    """Verificar que d6 es uniforme"""
    rng = RNG(seed=42)
    
    # Generar 1000 tiradas
    rolls = [rng.randint(1, 6) for _ in range(1000)]
    
    # Contar ocurrencias
    observed = np.bincount(rolls, minlength=7)[1:]  # Exclude 0
    
    # Esperado: 1000/6 ≈ 166.67 por valor
    expected = np.ones(6) * (1000 / 6)
    
    # Chi-square test
    statistic, p_value = chisquare(observed, expected)
    
    # p-value > 0.05 indica distribución uniforme
    assert p_value > 0.05, f"RNG no uniforme: p={p_value}, chi2={statistic}"
    
    # Bonus: verificar rango correcto
    assert min(rolls) == 1 and max(rolls) == 6
```

### Qué Verificar Manualmente

1. **En `engine/rng.py::__init__`:**
   ```python
   # ¿Esto está correcto?
   self.rng = random.Random(seed)
   
   # O hay algo como:
   random.seed(seed)  # ← MALO: afecta random global
   ```

2. **En `engine/rng.py::randint`:**
   ```python
   # ¿Es simplemente?
   return self.rng.randint(a, b)
   
   # O hay modificaciones que sesgan el resultado?
   ```

3. **Verificar si `randint` se llama múltiples veces por acción:**
   ```python
   # Si se llama así:
   for _ in range(algo):
       value = rng.randint(1, 6)
   
   # ¿Se pierde algún roll?
   ```

---

## 2. UBICACIÓN DE LLAMADAS A d6

### Dónde se tira d6 en el código

**Archivo:** `engine/transition.py` (probablemente)

Buscar líneas que hagan:
```python
d6 = rng.randint(1, 6)  # ← Aquí se tira d6
```

**Contexto:**
```python
# En la resolución de fin de ronda, bloque "Rey (efecto d6)"
# Debe haber algo como:
if state.phase == "KING" and es_fin_de_ronda:
    d6 = rng.randint(1, 6)
    # Aplicar efecto según d6
```

**Pregunta clave:** ¿Se tira EXACTAMENTE UNA VEZ por fin de ronda?

---

## 3. POSIBLE SESGO EN POLÍTICA DEL REY

### Ubicación: `sim/policies.py::HeuristicKingPolicy`

```python
class HeuristicKingPolicy:
    def choose(self, state, rng):
        # ¿Esta función siempre retorna la misma acción?
        # ¿O favorece ciertos valores?
        
        # Buscar patrones como:
        # - if value < threshold: preferred_action
        # - hardcoded values
        # - falta de aleatoriedad
```

### Qué Verificar

```python
# ¿Hay algo como esto (que sería MALO)?
def choose(self, state, rng):
    # MALO - Policy determinista
    if state.round < 10:
        return Action(type=ActionType.KING_ENDROUND, data={"d6": 1})
    else:
        return Action(type=ActionType.KING_ENDROUND, data={"d6": 5})

# ¿O está correctamente aleatorio?
def choose(self, state, rng):
    # BUENO - Deja que RNG decida
    d6 = rng.randint(1, 6)
    return Action(type=ActionType.KING_ENDROUND, data={"d6": d6})
```

---

## 4. CÓMO VERIFICAR LOCALMENTE

### Opción A: Test Rápido (Sin escribir código nuevo)

```bash
# En terminal
cd /home/gris/CARCOSA

# Ejecutar análisis de distribución
source .venv/bin/activate
python tools/analyze_d6_distribution.py

# Resultado esperado si está BIEN:
# Debería ver distribución más uniforme (no 78% en d6=1)
```

### Opción B: Inspeccionar Código Directamente

```bash
# Revisar qué se hace con d6
grep -n "d6" engine/*.py sim/*.py
grep -n "randint(1, 6)" engine/*.py sim/*.py
grep -n "KING_ENDROUND" engine/*.py
```

### Opción C: Agregar Logging (Temporalmente)

Sin cambios, pero aquí está el patrón:

```python
# En engine/rng.py, modificar (temporalmente):
def randint(self, a, b):
    result = self.rng.randint(a, b)
    print(f"RNG.randint({a}, {b}) → {result}")  # LOGGING
    return result

# Ejecutar una simulación:
python -m sim.runner --seed 1 --max-steps 400

# Observar salida: ¿d6 siempre es 1, 2, 5?
```

---

## 5. VERIFICACIÓN DE d4 ESCALERAS

### Ubicación: Búsqueda de reposición de escaleras

```bash
# Donde se generan d4 para escaleras
grep -n "randint(1, 4)" engine/*.py
grep -n "stairs_room" engine/*.py
grep -n "d4" engine/*.py
```

### Posible Ubicación: `engine/transition.py` o `engine/board.py`

Buscar bloque similar a:
```python
# Al final de ronda, bloque "Escaleras"
stairs_room[1] = rng.randint(1, 4)
stairs_room[2] = rng.randint(1, 4)
stairs_room[3] = rng.randint(1, 4)
```

**Pregunta:** ¿Se reutiliza el mismo RNG o se crea uno nuevo?

---

## 6. VERIFICACIÓN DE SHUFFLE EN SETUP

### Ubicación: `sim/runner.py::make_smoke_state`

Buscar:
```python
# Barajado inicial de mazos
rng.shuffle(room_ids)
rng.shuffle(deck)

# ¿Se usa el mismo rng, o random.shuffle()?
```

**Problema potencial:**
```python
# MALO - usa random global
random.shuffle(deck)

# BUENO - usa RNG local
rng.shuffle(deck)
```

---

## 7. DATOS PARA COMPARACIÓN

### Si arreglan el RNG, esperamos ver:

**Distribución de d6 - DESPUÉS DE FIX:**
```
d6=1: ~50 tiradas (16.7%) ✓
d6=2: ~50 tiradas (16.7%) ✓
d6=3: ~50 tiradas (16.7%) ✓
d6=4: ~50 tiradas (16.7%) ✓
d6=5: ~50 tiradas (16.7%) ✓
d6=6: ~50 tiradas (16.7%) ✓
```

**Vs. ACTUAL:**
```
d6=1: 236 tiradas (78.7%) ✗
d6=2:  16 tiradas (5.3%)  ✗
d6=3:   0 tiradas (0.0%)  ✗
d6=4:   0 tiradas (0.0%)  ✗
d6=5:  48 tiradas (16.0%) ✗
d6=6:   0 tiradas (0.0%)  ✗
```

---

## 8. CHECKLIST DE REVISIÓN

- [ ] ¿`RNG.__init__` usa `random.Random(seed)` correctamente?
- [ ] ¿`RNG.randint()` es simplemente `self.rng.randint(a, b)`?
- [ ] ¿No hay modificaciones aleatorias (offsets, multiplicaciones)?
- [ ] ¿Se usa `rng.shuffle()` en todos lados (no `random.shuffle()`)?
- [ ] ¿Se tira d6 exactamente UNA VEZ por fin de ronda?
- [ ] ¿Se tira d4 exactamente 3 veces por fin de ronda (escaleras)?
- [ ] ¿`HeuristicKingPolicy` deja que `rng.randint()` decida (no hardcodea)?
- [ ] ¿Chi-square test de distribución d6 pasa con p > 0.05?

---

## 9. RELACIÓN CON DOCUMENTACIÓN

Según **Manual Técnico §6.1:**
```
d6 Efectos (cada uno debe ~16.7% de probabilidad):
1 - Barajar mazos
2 - Pérdida de cordura global (-1)
3 - 1 acción solo (para jugadores en piso del Rey)
4 - Mover por escalera (expulsar a piso contiguo)
5 - Atraer (mover al pasillo)
6 - Descartar objeto
```

**Actual en runs:** Efectos 3, 4, 6 nunca se ejecutan.  
**Esperado después de fix:** Cada efecto ~16.7% de veces.

---

## 10. TESTING POST-FIX

```bash
# Después de arreglar:

# 1. Ejecutar test de uniformidad
pytest tests/test_rng_distribution.py -v

# 2. Generar nuevas runs
for s in {1..5}; do
  python -m sim.runner --seed $s --max-steps 400
done

# 3. Analizar distribución nueva
python tools/analyze_d6_distribution.py

# 4. Verificar changelog de efectos del Rey
# (Debería ver más variedad en efectos)
```

---

## RESUMEN

| Paso | Acción | Ubicación | Impacto |
|------|--------|-----------|--------|
| 1 | Revisar `RNG.randint()` | `engine/rng.py` | CRÍTICO |
| 2 | Revisar uso de `rng` | `engine/*.py` | ALTO |
| 3 | Revisar política | `sim/policies.py` | MEDIO |
| 4 | Test uniformidad | (nuevo test) | VALIDACIÓN |
| 5 | Generar runs nuevas | Terminal | VERIFICACIÓN |

---

**Generado por:** Análisis de runs vs documentación  
**Fecha:** 12 de enero, 2026  
**Estado:** Pendiente revisión manual de código

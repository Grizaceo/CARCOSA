# Plan de Implementación - 19 Enero 2026

## CORRECCIÓN DE INFORME

### ❌ ERROR IDENTIFICADO: Costo de SEARCH

**Informe Incorrecto Indicaba:**
```
| SEARCH | 1 | -1 | Revela en sala actual |
```

**Estado Real del Código:**
```python
# engine/transition.py línea 458-461
elif action.type == ActionType.SEARCH:
    card = _reveal_one(s, p.room)
    if card is not None:
        _resolve_card_minimal(s, pid, card, cfg, rng)
```

**CORRECCIÓN:**
- ✅ SEARCH cuesta **1 acción**
- ✅ SEARCH **NO cuesta cordura**
- ✅ Solo revela carta y resuelve efecto

**Tabla Correcta:**
| Acción | Costo Acciones | Costo Cordura | Efectos |
|--------|----------------|---------------|---------|
| SEARCH | 1 | 0 | Revela carta en sala actual |
| MEDITATE | 1 | +1 (ganancia) | Recupera 1 cordura |

**Nota:** NO confundir con TABERNA (habitación especial, pendiente implementar) que permite ver cartas pagando cordura.

---

## PARTE 1: HOOKS PENDIENTES (P0-B6)

### 1.1 Destrucción de Armería por Monstruo (B6)

**Archivo:** `engine/transition.py`

**Ubicación:** Función `_resolve_card_minimal()` (línea ~200-250)

**Implementación:**
```python
def _resolve_card_minimal(s, pid, card, cfg, rng):
    """
    Resuelve carta revelada.
    Agregar hook: si MONSTER entra a ARMERÍA → destruir + vaciar
    """

    # ... código existente ...

    if card_type == "MONSTER":
        # ... código existente de crear monstruo ...

        # NUEVO: Hook destrucción de Armería
        if "_ARMERY" in str(p.room):  # Si monstruo aparece en Armería
            s.flags[f"ARMORY_DESTROYED_{p.room}"] = True
            s.armory_storage[p.room] = []  # Vaciar almacenamiento
```

**Tests a Agregar:**
```python
# tests/test_armory.py
def test_armory_destroyed_by_monster():
    """Monstruo destruye armería y vacía storage"""

def test_armory_destroyed_prevents_drop_take():
    """Armería destruida no permite DROP/TAKE"""
```

**Estimación:** 15 minutos código + 10 minutos tests

---

### 1.2 Reset Automático de Peek al Final del Turno (B5)

**Archivo:** `engine/transition.py`

**Ubicación:** Función `_start_new_round()` (línea ~373-400)

**Implementación:**
```python
def _start_new_round(s: GameState, cfg: Config) -> None:
    """
    Reset de flags al inicio de nueva ronda.
    Agregar: reset peek_used_this_turn
    """
    s.round += 1
    s.turn_pos = 0

    # NUEVO: Reset de Peek
    s.peek_used_this_turn = {}

    # ... resto del código existente ...
```

**Tests a Agregar:**
```python
# tests/test_peek_rooms.py
def test_peek_resets_at_new_round():
    """Peek se puede usar nuevamente al iniciar nueva ronda"""
```

**Estimación:** 5 minutos código + 5 minutos tests

---

### 1.3 Sistema de Habitaciones Especiales + Pool de Llaves (B3)

**CONTEXTO (Canon Confirmado):**

Durante el setup del juego:
1. Se eligen **3 habitaciones especiales al azar** de las 5 disponibles:
   - B2: Motemey
   - B3: Cámara Letal
   - B4: Puertas Amarillas
   - B5: Peek (Mirador)
   - B6: Armería

2. **Cámara Letal** (habitación especial):
   - NO tiene eventos asociados (a diferencia del Motemey)
   - Solo existe como habitación si sale en el sorteo de las 3
   - Cuando es **revelada**, se habilita la posibilidad de obtener la 7ª llave
   - Los jugadores activan un **ritual** en la Cámara Letal para obtener la llave

3. **Motemey** (habitación especial + eventos):
   - Es una habitación especial (puede salir en sorteo de 3)
   - **ADEMÁS** tiene eventos de Motemey que aparecen en otras habitaciones
   - Su mazo **siempre se arma** en setup (independiente del sorteo)

**ESTADO ACTUAL DEL CÓDIGO:**
- ❌ No existe lógica de sorteo de 3 habitaciones especiales
- ✅ Motemey implementado (habitación + mazo de eventos)
- ✅ Puertas, Peek, Armería implementados
- ❌ Cámara Letal NO implementada

---

**IMPLEMENTACIÓN REQUERIDA:**

**Paso 1: Sistema de Sorteo de Habitaciones Especiales**

**Archivo:** `sim/runner.py` (nuevo `engine/setup.py` en el futuro)

**Ubicación:** Función `make_smoke_state()` (línea 18-77)

```python
def make_smoke_state(seed: int = 1, cfg: Optional[Config] = None) -> GameState:
    """
    Setup del juego con sorteo de habitaciones especiales.
    """
    cfg = cfg or Config()
    rng = RNG(seed)

    # NUEVO: Sortear 3 habitaciones especiales
    available_special_rooms = [
        "MOTEMEY",      # B2
        "CAMARA_LETAL", # B3
        "PUERTAS",      # B4 (Puertas Amarillas)
        "PEEK",         # B5 (Mirador)
        "ARMERY"        # B6 (Armería)
    ]

    selected_special_rooms = rng.sample(available_special_rooms, 3)

    # Marcar en flags cuáles fueron seleccionadas
    state.flags["SPECIAL_ROOMS_SELECTED"] = selected_special_rooms
    state.flags["CAMARA_LETAL_PRESENT"] = "CAMARA_LETAL" in selected_special_rooms

    # Determinar pool de llaves
    # NOTA: La 7ª llave se obtiene mediante ritual en Cámara Letal DESPUÉS de revelarla
    # Por ahora, siempre empezamos con 6 llaves distribuidas
    keys_total = 6

    # Distribución de llaves:
    # - 5 llaves en mazos de habitaciones (F1_R1 a F1_R4, F2_R1)
    # - 1 llave en MOTEMEY deck (siempre, independiente del sorteo)

    # ... resto de distribución existente ...

    # SIEMPRE armar mazo de Motemey (independiente del sorteo)
    motemey_cards = [
        CardId("COMPASS"), CardId("COMPASS"), CardId("COMPASS"),
        CardId("VIAL"), CardId("VIAL"), CardId("VIAL"),
        CardId("BLUNT"), CardId("BLUNT"),
        CardId("TREASURE_RING"), CardId("TREASURE_CROWN"),
        CardId("TREASURE_SCROLL"), CardId("TREASURE_PENDANT"),
        CardId("KEY"),
        CardId("STORY"),
    ]
    rng.shuffle(motemey_cards)
    state.motemey_deck = DeckState(cards=motemey_cards, top=0)
```

**Paso 2: Implementar Habitación Cámara Letal**

**Archivo:** `engine/actions.py`

Agregar nueva acción:
```python
# Cámara Letal (B3)
USE_CAMARA_LETAL_RITUAL = "USE_CAMARA_LETAL_RITUAL"
```

**Archivo:** `engine/legality.py`

Agregar legalidad (después de línea 119):
```python
# B3 - Cámara Letal: Ritual para obtener 7ª llave
camara_letal_pattern = "_CAMARA_LETAL"
is_in_camara_letal = camara_letal_pattern in str(p.room)

if is_in_camara_letal and s.flags.get("CAMARA_LETAL_PRESENT", False):
    # Solo se puede hacer el ritual una vez por partida
    if not s.flags.get("CAMARA_LETAL_RITUAL_COMPLETED", False):
        # Verificar que hay exactamente 2 jugadores en la habitación
        players_in_room = [
            player for player in s.players
            if player.room == p.room
        ]

        if len(players_in_room) == 2:
            # NOTA: Requiere interacción entre jugadores para decidir:
            # - Quién paga qué según el D6
            # - Quién porta la llave resultante
            # Por ahora, permitimos la acción si hay 2 jugadores
            legal_actions.append(Action(
                type=ActionType.USE_CAMARA_LETAL_RITUAL,
                data={}
            ))
```

**Archivo:** `engine/transition.py`

Agregar transición (después de línea 563):
```python
elif action.type == ActionType.USE_CAMARA_LETAL_RITUAL:
    # Ritual en Cámara Letal: agrega 7ª llave al pool
    if not s.flags.get("CAMARA_LETAL_RITUAL_COMPLETED", False):
        # Verificar que hay 2 jugadores en la habitación
        players_in_room = [
            pid for pid, player in enumerate(s.players)
            if player.room == p.room
        ]

        if len(players_in_room) == 2:
            # Lanzar D6 para determinar costo de cordura
            d6 = rng.randint(1, 6)

            # NOTA: En implementación real, esto requiere interacción
            # entre jugadores. Por ahora, usamos una heurística:
            # - action.data debe contener:
            #   - "sanity_distribution": [cost_p1, cost_p2]
            #   - "key_recipient": índice del jugador que recibe la llave

            sanity_costs = action.data.get("sanity_distribution", [0, 0])
            key_recipient = action.data.get("key_recipient", players_in_room[0])

            # Validar distribución según D6
            valid = False
            if d6 in [1, 2]:
                # Un jugador paga 7 (el otro 0)
                valid = sorted(sanity_costs) == [0, 7]
            elif d6 in [3, 4]:
                # Reparto fijo: 3 y 4
                valid = sorted(sanity_costs) == [3, 4]
            elif d6 in [5, 6]:
                # Reparto libre: suma total = 7
                valid = sum(sanity_costs) == 7

            if valid:
                # Aplicar costos de cordura
                for i, cost in enumerate(sanity_costs):
                    player_idx = players_in_room[i]
                    s.players[player_idx].sanity -= cost
                    # Aplicar límite de -5
                    if s.players[player_idx].sanity < -5:
                        # Jugador puede elegir sacrificarse (según reglas generales)
                        s.players[player_idx].sanity = -5

                # Agregar llave al inventario del jugador designado
                s.players[key_recipient].objects.append(CardId("KEY"))

                # Marcar ritual como completado
                s.flags["CAMARA_LETAL_RITUAL_COMPLETED"] = True
                s.flags["CAMARA_LETAL_D6"] = d6  # Para tracking
```

**Paso 3: Sistema de Asignación de Ubicaciones con D4**

**Archivo:** `sim/runner.py` (continuación de Paso 1)

**Implementación:**
```python
def make_smoke_state(seed: int = 1, cfg: Optional[Config] = None) -> GameState:
    # ... (código anterior de sorteo) ...

    selected_special_rooms = rng.sample(available_special_rooms, 3)

    # NUEVO: Asignar ubicaciones con D4
    # Para cada habitación especial, tirar D4 por cada piso
    special_room_locations = {}

    for special_room in selected_special_rooms:
        # Tirar D4 para cada piso (F1 y F2)
        # PENDIENTE: Confirmar si van en ambos pisos o solo uno
        # Por ahora, asumimos que van en ambos pisos

        f1_roll = rng.randint(1, 4)  # D4 para piso 1
        f2_roll = rng.randint(1, 4)  # D4 para piso 2

        # Mapeo: 1→R1, 2→R2, 3→R3, 4→R4
        f1_room = f"F1_R{f1_roll}"
        f2_room = f"F2_R{f2_roll}"

        special_room_locations[special_room] = {
            "F1": f1_room,
            "F2": f2_room
        }

    # Guardar en state para referencia
    s.flags["SPECIAL_ROOM_LOCATIONS"] = special_room_locations

    # AHORA: Crear habitaciones con nombres apropiados
    # Ejemplo: si MOTEMEY sale en F1_R2, crear "F1_R2_MOTEMEY"

    # ... resto del código de creación de habitaciones ...
    # Cuando se crea una habitación, verificar si debe ser especial:

    for floor in ["F1", "F2"]:
        for room_num in [1, 2, 3, 4]:
            base_room_id = f"{floor}_R{room_num}"

            # Verificar si esta ubicación tiene una habitación especial
            special_suffix = None
            for special_type, locations in special_room_locations.items():
                if locations.get(floor) == base_room_id:
                    special_suffix = special_type
                    break

            if special_suffix:
                room_id = f"{base_room_id}_{special_suffix}"
            else:
                room_id = base_room_id

            # Crear habitación con deck, etc.
            # ...
```

**⚠️ DECISIÓN DE DISEÑO REQUERIDA:**
¿Qué pasa si dos habitaciones especiales caen en la misma ubicación (ej: ambas en F1_R2)?
- Opción A: Re-tirar D4 hasta que no haya colisión
- Opción B: Permitir colisión y solo crear una (la primera)
- Opción C: Cada habitación especial solo va en UN piso (no en ambos)

**Tests a Agregar:**
```python
# tests/test_special_rooms_setup.py (NUEVO)
def test_setup_selects_3_special_rooms():
    """Setup sortea exactamente 3 habitaciones especiales"""

def test_camara_letal_flag_set_when_selected():
    """Flag CAMARA_LETAL_PRESENT se marca si sale en sorteo"""

def test_motemey_deck_always_created():
    """Mazo de Motemey se crea independiente del sorteo"""

# tests/test_camara_letal.py (NUEVO)
def test_camara_letal_ritual_adds_7th_key():
    """Ritual en Cámara Letal agrega 7ª llave al pool"""

def test_ritual_only_once():
    """Ritual solo se puede hacer una vez por partida"""
```

**Estimación:** 60 minutos código + 30 minutos tests

**✅ DETALLES CONFIRMADOS:**

**Ritual de Cámara Letal:**
- Requiere **exactamente 2 jugadores** en la habitación
- **NO consume acciones** (acción gratuita)
- **Costo de cordura (D6):**
  - `1-2`: Un jugador (a elección de ambos) sacrifica 7 cordura (mín -5, con opción de sacrificio)
  - `3-4`: Reparto fijo: un jugador 3, otro 4 (a elección de ambos quién paga qué)
  - `5-6`: Reparto libre de 7 puntos entre ambos (a elección de ambos)
- **Resultado:** Obtienen 7ª llave, ellos deciden quién la porta
- **Solo se puede activar una vez por partida**

**Revelación de Habitaciones Especiales:**
- **Automática** cuando un jugador entra por primera vez
- **NO consume acciones**
- Revelar ≠ Activar efecto (activar efecto sí puede costar acciones)

**Asignación de Ubicaciones:**
1. Se eligen 3 habitaciones especiales al azar
2. Para cada habitación especial:
   - Se lanza D4 por piso (2 pisos = 2 tiradas por habitación)
   - Resultado D4: `1→R1, 2→R2, 3→R3, 4→R4`
   - Ejemplo: Si sale `[2, 3]` → habitación va en `F1_R2` y `F2_R3`

**⚠️ PREGUNTA ADICIONAL:**
- ¿Las habitaciones especiales aparecen en AMBOS pisos (F1 y F2) o solo en uno?
- Si aparecen en ambos: ¿Se tiran 2 D4 por cada habitación especial (total 6 tiradas)?
- Si solo en uno: ¿Cómo se decide en qué piso va cada habitación?

---

## PARTE 2: ANÁLISIS EXTENDIDO DE RNG

### 2.1 Tracking Completo de Elementos Aleatorios

**Elementos a Trackear:**

1. **d6 del Rey** (ya implementado) ✅
2. **d4 Manifestación Rey** (ruleta pisos) ⏳
3. **d4 Escaleras** (3 tiradas por fin de ronda) ⏳
4. **Shuffles de Mazos** (efecto d6=1) ⏳
5. **Orden de Setup Inicial** (distribución de cartas) ⏳
6. **Elecciones de Policy** (si tienen componente aleatorio) ⏳

**Archivo:** `engine/rng.py`

**Implementación:**
```python
@dataclass
class RNG:
    seed: int
    _r: random.Random = None
    log: List[Tuple[str, Any]] = None

    # Tracking específico
    last_king_d6: int = None
    last_king_d4: int = None

    # NUEVO: Historial completo
    d6_history: List[int] = field(default_factory=list)
    d4_history: List[int] = field(default_factory=list)
    shuffle_count: int = 0
    choice_history: List[Tuple[str, Any]] = field(default_factory=list)

    def randint(self, a: int, b: int) -> int:
        """Genera entero aleatorio con tracking"""
        result = self._r.randint(a, b)

        # Track específico por rango
        if (a, b) == (1, 6):
            self.d6_history.append(result)
        elif (a, b) == (1, 4):
            self.d4_history.append(result)

        # Log general
        self.log.append(("randint", (a, b, result)))
        return result

    def shuffle(self, seq):
        """Shuffle con tracking"""
        self._r.shuffle(seq)
        self.shuffle_count += 1
        self.log.append(("shuffle", len(seq)))

    def choice(self, seq):
        """Choice con tracking"""
        result = self._r.choice(seq)
        self.choice_history.append(("choice", result))
        self.log.append(("choice", result))
        return result
```

**Archivo:** `sim/metrics.py`

**Agregar a `transition_record()`:**
```python
def transition_record(
    state: GameState,
    action: Dict[str, Any],
    next_state: GameState,
    cfg: Config,
    step_idx: int,
    rng: RNG,  # NUEVO parámetro
) -> Dict[str, Any]:

    # ... código existente ...

    rec: Dict[str, Any] = {
        # ... campos existentes ...

        # NUEVO: RNG statistics
        "rng_stats": {
            "d6_count": len(rng.d6_history),
            "d4_count": len(rng.d4_history),
            "shuffle_count": rng.shuffle_count,
            "d6_distribution": _compute_distribution(rng.d6_history),
            "d4_distribution": _compute_distribution(rng.d4_history),
        }
    }
    return rec

def _compute_distribution(history: List[int]) -> Dict[int, int]:
    """Calcula frecuencia de valores"""
    from collections import Counter
    return dict(Counter(history))
```

**Estimación:** 30 minutos código + 15 minutos tests

---

### 2.2 Herramienta de Análisis RNG Completo

**Archivo NUEVO:** `tools/analyze_rng_complete.py`

```python
"""
Analiza TODOS los elementos aleatorios de una o más partidas:
- d6 del Rey (distribución, chi-square test)
- d4 Manifestación (distribución, uniformidad)
- d4 Escaleras (distribución por piso)
- Shuffles (frecuencia por ronda)
- Choices de policies (si aplica)
"""

import json
import sys
from pathlib import Path
from collections import Counter
from scipy.stats import chisquare

def analyze_rng_from_jsonl(jsonl_path: str):
    """Analiza RNG completo de una partida"""

    d6_history = []
    d4_history = []
    shuffle_counts = []

    with open(jsonl_path, 'r') as f:
        for line in f:
            record = json.loads(line)

            # d6 del Rey
            if record['action_type'] == 'KING_ENDROUND':
                d6 = record['action_data'].get('d6')
                if d6:
                    d6_history.append(d6)

            # Extraer stats de RNG
            rng_stats = record.get('rng_stats', {})
            if rng_stats:
                # Acumular datos
                pass

    # Análisis estadístico
    print(f"\n=== ANÁLISIS RNG: {Path(jsonl_path).name} ===\n")

    # d6 del Rey
    print("d6 del Rey:")
    d6_dist = Counter(d6_history)
    expected = len(d6_history) / 6
    print(f"  Total tiradas: {len(d6_history)}")
    print(f"  Distribución: {dict(d6_dist)}")
    print(f"  Esperado por valor: {expected:.1f}")

    # Chi-square test
    observed = [d6_dist.get(i, 0) for i in range(1, 7)]
    expected_arr = [expected] * 6
    chi2, p_value = chisquare(observed, expected_arr)
    print(f"  χ² = {chi2:.4f}, p-value = {p_value:.4f}")

    if p_value < 0.05:
        print(f"  ⚠️ SESGO DETECTADO (p < 0.05)")
    else:
        print(f"  ✅ UNIFORME (p >= 0.05)")

    # Similar para d4, shuffles, etc.
    # ...

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analyze_rng_complete.py <jsonl_path>")
        sys.exit(1)

    analyze_rng_from_jsonl(sys.argv[1])
```

**Estimación:** 45 minutos

---

## PARTE 3: SISTEMA DE GUARDADO VERSIONADO Y ORGANIZADO

### 3.1 Estructura de Carpetas Propuesta

```
runs/
├── v{COMMIT_HASH}/                    # Por versión de código
│   ├── 2026-01-19_14-30-00/          # Por sesión de simulación
│   │   ├── metadata.json              # Info versión + timestamp
│   │   ├── seed_001.jsonl             # Partida seed 1
│   │   ├── seed_002.jsonl             # Partida seed 2
│   │   ├── seed_003.jsonl
│   │   ├── seed_004.jsonl
│   │   └── seed_005.jsonl
│   │
│   ├── 2026-01-19_15-45-00/          # Otra sesión mismo día
│   │   └── ...
│   │
│   └── analysis/                      # Análisis de esta versión
│       ├── 2026-01-19_14-30-00_analysis.json
│       └── 2026-01-19_15-45-00_analysis.json
│
├── v{OTRO_COMMIT}/
│   └── ...
│
└── archive/                           # Backups antiguos
    └── pre_2026-01-15/
```

**Ventajas:**
- ✅ Aislamiento por versión de código (commit hash)
- ✅ Aislamiento por fecha/hora de simulación
- ✅ Análisis guardados junto a runs
- ✅ Fácil comparación entre versiones
- ✅ Fácil limpieza de datos antiguos

---

### 3.2 Actualización de `tools/run_versioned.py`

**Modificaciones:**

```python
"""
Genera runs versionados con estructura organizada.

Mejoras:
- Guardar en runs/v{COMMIT}/{TIMESTAMP}/
- Generar metadata.json con info de versión
- Soportar múltiples seeds en una sesión
- Crear carpeta analysis/ automáticamente
"""

import subprocess
import json
from datetime import datetime
from pathlib import Path

def get_git_info():
    """Obtiene commit hash, branch, y timestamp"""
    commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode().strip()
    branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return commit, branch, timestamp

def create_run_directory():
    """Crea estructura de carpetas para esta sesión"""
    commit, branch, timestamp = get_git_info()

    # runs/v{commit}/{timestamp}/
    base_dir = Path(f"runs/v{commit}")
    session_dir = base_dir / timestamp
    analysis_dir = base_dir / "analysis"

    session_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    # Crear metadata.json
    metadata = {
        "commit": commit,
        "branch": branch,
        "timestamp": timestamp,
        "iso_timestamp": datetime.now().isoformat(),
        "seeds_generated": [],
    }

    metadata_path = session_dir / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return session_dir, metadata_path

def run_versioned_session(seeds=[1, 2, 3, 4, 5], max_steps=400):
    """
    Ejecuta sesión de simulaciones con múltiples seeds.
    """
    from sim.runner import run_episode

    session_dir, metadata_path = create_run_directory()

    print(f"📁 Sesión: {session_dir}")

    results = []
    for i, seed in enumerate(seeds, 1):
        seed_path = session_dir / f"seed_{i:03d}.jsonl"
        print(f"🎲 Ejecutando seed {seed} → {seed_path.name}")

        final_state = run_episode(
            max_steps=max_steps,
            seed=seed,
            out_path=str(seed_path),
        )

        results.append({
            "seed": seed,
            "file": seed_path.name,
            "outcome": final_state.outcome,
            "rounds": final_state.round,
        })

    # Actualizar metadata con resultados
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    metadata["seeds_generated"] = results
    metadata["total_seeds"] = len(results)

    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"\n✅ Sesión completada: {len(results)} partidas")
    print(f"📊 Metadata: {metadata_path}")

    return session_dir

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs='+', default=[1, 2, 3, 4, 5])
    ap.add_argument("--max-steps", type=int, default=400)
    args = ap.parse_args()

    run_versioned_session(seeds=args.seeds, max_steps=args.max_steps)
```

**Estimación:** 45 minutos

---

## PARTE 4: HERRAMIENTA DE ANÁLISIS COMPREHENSIVO

### 4.1 Especificación de Métricas a Extraer

**Métricas Solicitadas:**

| Categoría | Métrica | Fuente |
|-----------|---------|--------|
| **General** | Número de jugadores | `len(state.players)` |
| | Número de rondas | `max(record['round'])` |
| | Outcome final | `record['outcome']` (última línea) |
| | Duración (steps) | `max(record['step'])` |
| **Llaves** | Llaves conseguidas (total) | `sum(keys_in_hand)` por jugador |
| | Llaves máximas en mano | `max(summary_post['keys_in_hand'])` |
| | Llaves destruidas | `summary_post['keys_destroyed']` (última línea) |
| | Veces que se llegó a 4 llaves | Contar steps con `keys_in_hand >= 4` |
| **Monstruos** | Cantidad revelados | Contar eventos `MONSTER` en `_resolve_card` |
| | Cantidad stuneados | Contar aplicaciones de STUN |
| | Monstruos activos al final | `len(state.monsters)` (última línea) |
| **Objetos** | Objetos usados | Contar `USE_*` actions |
| | Tesoros vendidos | Contar `USE_MOTEMEY_SELL` con `TREASURE_*` |
| | Objetos en inventario final | `len(p.objects)` (última línea) |
| **Habitaciones Especiales** | MOTEMEY (compras) | Contar `USE_MOTEMEY_BUY` |
| | MOTEMEY (ventas) | Contar `USE_MOTEMEY_SELL` |
| | PUERTAS (teleport) | Contar `USE_YELLOW_DOORS` |
| | PEEK (mirar) | Contar `USE_PEEK_ROOMS` |
| | ARMERÍA (drop/take) | Contar `USE_ARMORY_DROP/TAKE` |
| **Cordura** | Veces en -5 | Contar `min_sanity <= -5` |
| | Sacrificios realizados | Contar `SACRIFICE` actions |
| | Cordura mínima alcanzada | `min(summary_post['min_sanity'])` |
| | Cordura promedio | `mean(summary_post['mean_sanity'])` |
| **Rey** | Pisos visitados | Contar cambios en `king_floor` |
| | d6 efectos aplicados | Distribución de `action_data['d6']` |
| | Expulsiones | Contar efecto d6=4 |
| | Atracciones | Contar efecto d6=5 |
| **Tensión** | Tensión máxima | `max(T_post)` |
| | Tensión promedio | `mean(T_post)` |
| | Tensión al ganar/perder | `T_post` (última línea) |

---

### 4.2 Implementación: `tools/analyze_comprehensive.py`

**Archivo NUEVO:** `tools/analyze_comprehensive.py`

```python
"""
Análisis comprehensivo de una partida JSONL.

Genera reporte detallado con TODAS las métricas solicitadas.

Uso:
    python tools/analyze_comprehensive.py runs/v{commit}/{timestamp}/seed_001.jsonl

Output:
    runs/v{commit}/analysis/{timestamp}_seed_001_analysis.json
"""

import json
import sys
from pathlib import Path
from collections import Counter
from typing import Dict, List, Any

def analyze_game(jsonl_path: str) -> Dict[str, Any]:
    """
    Analiza partida completa y extrae todas las métricas.
    """

    records = []
    with open(jsonl_path, 'r') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    if not records:
        return {"error": "No records found"}

    first = records[0]
    last = records[-1]

    # ===== GENERAL =====
    general = {
        "num_players": len(first['summary_pre'].get('players', [])) if 'players' in first['summary_pre'] else 2,
        "num_rounds": last['round'],
        "num_steps": last['step'] + 1,
        "outcome": last['outcome'],
        "game_over": last['done'],
    }

    # ===== LLAVES =====
    keys_in_hand_history = [r['summary_post']['keys_in_hand'] for r in records]
    keys_destroyed_history = [r['summary_post']['keys_destroyed'] for r in records]

    keys = {
        "max_keys_in_hand": max(keys_in_hand_history),
        "final_keys_in_hand": last['summary_post']['keys_in_hand'],
        "keys_destroyed": last['summary_post']['keys_destroyed'],
        "times_reached_4_keys": sum(1 for k in keys_in_hand_history if k >= 4),
        "keys_in_hand_history": keys_in_hand_history,  # Para gráficos
    }

    # ===== MONSTRUOS =====
    monsters_history = [r['summary_post']['monsters'] for r in records]

    # Contar eventos de monstruos (aproximado: cuando monsters incrementa)
    monster_reveals = 0
    for i in range(1, len(records)):
        if monsters_history[i] > monsters_history[i-1]:
            monster_reveals += 1

    # Contar STUNs (buscar en features o logs)
    stun_count = 0
    for r in records:
        # Aproximado: buscar 'STUN' en action_data o features
        if 'STUN' in str(r.get('action_data', {})):
            stun_count += 1

    monsters = {
        "total_revealed": monster_reveals,
        "final_monsters_active": last['summary_post']['monsters'],
        "max_monsters": max(monsters_history),
        "stuns_applied": stun_count,  # Aproximado
    }

    # ===== ACCIONES =====
    action_counts = Counter(r['action_type'] for r in records)

    actions = {
        "total_actions": len(records),
        "action_distribution": dict(action_counts),
        "moves": action_counts.get('MOVE', 0),
        "searches": action_counts.get('SEARCH', 0),
        "meditates": action_counts.get('MEDITATE', 0),
    }

    # ===== HABITACIONES ESPECIALES =====
    special_rooms = {
        "motemey_buys": action_counts.get('USE_MOTEMEY_BUY', 0),
        "motemey_sells": action_counts.get('USE_MOTEMEY_SELL', 0),
        "yellow_doors_teleports": action_counts.get('USE_YELLOW_DOORS', 0),
        "peek_uses": action_counts.get('USE_PEEK_ROOMS', 0),
        "armory_drops": action_counts.get('USE_ARMORY_DROP', 0),
        "armory_takes": action_counts.get('USE_ARMORY_TAKE', 0),
    }

    # ===== OBJETOS Y TESOROS =====
    # Contar tesoros vendidos (revisar action_data de MOTEMEY_SELL)
    treasure_sells = 0
    object_sells = 0

    for r in records:
        if r['action_type'] == 'USE_MOTEMEY_SELL':
            item = r['action_data'].get('item_name', '')
            if 'TREASURE' in item:
                treasure_sells += 1
            else:
                object_sells += 1

    objects = {
        "treasures_sold": treasure_sells,
        "objects_sold": object_sells,
        "total_sells": treasure_sells + object_sells,
    }

    # ===== CORDURA =====
    sanity_history = [r['summary_post']['min_sanity'] for r in records]
    sanity_mean_history = [r['summary_post']['mean_sanity'] for r in records]

    times_at_minus5 = sum(1 for s in sanity_history if s <= -5)
    sacrifices = action_counts.get('SACRIFICE', 0)

    sanity = {
        "min_sanity_reached": min(sanity_history),
        "final_min_sanity": last['summary_post']['min_sanity'],
        "mean_sanity_avg": sum(sanity_mean_history) / len(sanity_mean_history),
        "times_at_minus5": times_at_minus5,
        "sacrifices_performed": sacrifices,
    }

    # ===== REY =====
    king_floors = [r['summary_post']['king_floor'] for r in records]
    king_floor_changes = sum(1 for i in range(1, len(king_floors)) if king_floors[i] != king_floors[i-1])

    # d6 del Rey
    d6_values = []
    for r in records:
        if r['action_type'] == 'KING_ENDROUND':
            d6 = r['action_data'].get('d6')
            if d6:
                d6_values.append(d6)

    d6_dist = Counter(d6_values)

    king = {
        "floors_visited": len(set(king_floors)),
        "floor_changes": king_floor_changes,
        "d6_total_rolls": len(d6_values),
        "d6_distribution": dict(d6_dist),
        "d6_effect_1_shuffles": d6_dist.get(1, 0),
        "d6_effect_2_sanity_loss": d6_dist.get(2, 0),
        "d6_effect_3_limited_actions": d6_dist.get(3, 0),
        "d6_effect_4_expulsions": d6_dist.get(4, 0),
        "d6_effect_5_attractions": d6_dist.get(5, 0),
        "d6_effect_6_discard_objects": d6_dist.get(6, 0),
    }

    # ===== TENSIÓN =====
    tension_history = [r['T_post'] for r in records]

    tension = {
        "max_tension": max(tension_history),
        "avg_tension": sum(tension_history) / len(tension_history),
        "final_tension": last['T_post'],
    }

    # ===== COMPILAR REPORTE =====
    analysis = {
        "file": Path(jsonl_path).name,
        "general": general,
        "keys": keys,
        "monsters": monsters,
        "actions": actions,
        "special_rooms": special_rooms,
        "objects": objects,
        "sanity": sanity,
        "king": king,
        "tension": tension,
    }

    return analysis


def save_analysis(analysis: Dict[str, Any], jsonl_path: str):
    """
    Guarda análisis en runs/v{commit}/analysis/{timestamp}_seed_XXX_analysis.json
    """
    jsonl_path = Path(jsonl_path)

    # Detectar estructura: runs/v{commit}/{timestamp}/seed_XXX.jsonl
    # Guardar en: runs/v{commit}/analysis/{timestamp}_seed_XXX_analysis.json

    parts = jsonl_path.parts
    if 'runs' in parts:
        runs_idx = parts.index('runs')
        if len(parts) > runs_idx + 2:
            version_dir = Path(*parts[:runs_idx+2])  # runs/v{commit}
            timestamp_dir = parts[runs_idx+2]
            seed_name = jsonl_path.stem  # seed_001

            analysis_dir = version_dir / "analysis"
            analysis_dir.mkdir(parents=True, exist_ok=True)

            analysis_filename = f"{timestamp_dir}_{seed_name}_analysis.json"
            analysis_path = analysis_dir / analysis_filename
        else:
            # Fallback: guardar al lado del JSONL
            analysis_path = jsonl_path.with_suffix('.analysis.json')
    else:
        # Fallback
        analysis_path = jsonl_path.with_suffix('.analysis.json')

    with open(analysis_path, 'w') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    print(f"💾 Análisis guardado: {analysis_path}")
    return analysis_path


def print_summary(analysis: Dict[str, Any]):
    """Imprime resumen legible del análisis"""

    print("\n" + "="*60)
    print(f"📊 ANÁLISIS COMPREHENSIVO: {analysis['file']}")
    print("="*60)

    g = analysis['general']
    print(f"\n🎮 GENERAL:")
    print(f"  Jugadores: {g['num_players']}")
    print(f"  Rondas: {g['num_rounds']}")
    print(f"  Steps: {g['num_steps']}")
    print(f"  Outcome: {g['outcome']}")

    k = analysis['keys']
    print(f"\n🔑 LLAVES:")
    print(f"  Máximo en mano: {k['max_keys_in_hand']}")
    print(f"  Final en mano: {k['final_keys_in_hand']}")
    print(f"  Destruidas: {k['keys_destroyed']}")
    print(f"  Veces con 4+ llaves: {k['times_reached_4_keys']}")

    m = analysis['monsters']
    print(f"\n👹 MONSTRUOS:")
    print(f"  Revelados: {m['total_revealed']}")
    print(f"  Activos al final: {m['final_monsters_active']}")
    print(f"  STUNs aplicados: {m['stuns_applied']}")

    a = analysis['actions']
    print(f"\n⚙️ ACCIONES:")
    print(f"  Total: {a['total_actions']}")
    print(f"  MOVE: {a['moves']}")
    print(f"  SEARCH: {a['searches']}")
    print(f"  MEDITATE: {a['meditates']}")

    sr = analysis['special_rooms']
    print(f"\n🏠 HABITACIONES ESPECIALES:")
    print(f"  MOTEMEY (compras): {sr['motemey_buys']}")
    print(f"  MOTEMEY (ventas): {sr['motemey_sells']}")
    print(f"  PUERTAS (teleport): {sr['yellow_doors_teleports']}")
    print(f"  PEEK: {sr['peek_uses']}")
    print(f"  ARMERÍA (drop/take): {sr['armory_drops']}/{sr['armory_takes']}")

    s = analysis['sanity']
    print(f"\n❤️ CORDURA:")
    print(f"  Mínima alcanzada: {s['min_sanity_reached']}")
    print(f"  Final: {s['final_min_sanity']}")
    print(f"  Veces en -5: {s['times_at_minus5']}")
    print(f"  Sacrificios: {s['sacrifices_performed']}")

    ki = analysis['king']
    print(f"\n👑 REY:")
    print(f"  Pisos visitados: {ki['floors_visited']}")
    print(f"  Cambios de piso: {ki['floor_changes']}")
    print(f"  d6 tiradas: {ki['d6_total_rolls']}")
    print(f"  d6 distribución: {ki['d6_distribution']}")

    t = analysis['tension']
    print(f"\n📈 TENSIÓN:")
    print(f"  Máxima: {t['max_tension']:.3f}")
    print(f"  Promedio: {t['avg_tension']:.3f}")
    print(f"  Final: {t['final_tension']:.3f}")

    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/analyze_comprehensive.py <jsonl_path>")
        sys.exit(1)

    jsonl_path = sys.argv[1]

    print(f"🔍 Analizando: {jsonl_path}")
    analysis = analyze_game(jsonl_path)

    # Guardar análisis
    analysis_path = save_analysis(analysis, jsonl_path)

    # Imprimir resumen
    print_summary(analysis)

    print(f"✅ Análisis completo guardado en: {analysis_path}")
```

**Estimación:** 90 minutos

---

### 4.3 Batch Analysis: Analizar Sesión Completa

**Archivo NUEVO:** `tools/analyze_session_batch.py`

```python
"""
Analiza TODOS los seeds de una sesión y genera reporte agregado.

Uso:
    python tools/analyze_session_batch.py runs/v{commit}/{timestamp}/

Output:
    runs/v{commit}/analysis/{timestamp}_session_aggregate.json
"""

import json
from pathlib import Path
import sys

def analyze_session(session_dir: str):
    """
    Analiza todos los seed_*.jsonl de una sesión.
    Genera análisis individual + reporte agregado.
    """
    from tools.analyze_comprehensive import analyze_game, save_analysis

    session_path = Path(session_dir)
    jsonl_files = sorted(session_path.glob("seed_*.jsonl"))

    if not jsonl_files:
        print(f"❌ No se encontraron archivos seed_*.jsonl en {session_dir}")
        return

    print(f"📁 Sesión: {session_path}")
    print(f"🎲 Seeds encontrados: {len(jsonl_files)}\n")

    all_analyses = []

    for jsonl_file in jsonl_files:
        print(f"🔍 Analizando: {jsonl_file.name}")
        analysis = analyze_game(str(jsonl_file))
        save_analysis(analysis, str(jsonl_file))
        all_analyses.append(analysis)

    # Crear reporte agregado
    aggregate = {
        "session": session_path.name,
        "total_games": len(all_analyses),
        "outcomes": {
            "WIN": sum(1 for a in all_analyses if a['general']['outcome'] == 'WIN'),
            "LOSE": sum(1 for a in all_analyses if a['general']['outcome'] == 'LOSE'),
            "TIMEOUT": sum(1 for a in all_analyses if a['general']['outcome'] == 'TIMEOUT'),
        },
        "avg_rounds": sum(a['general']['num_rounds'] for a in all_analyses) / len(all_analyses),
        "avg_steps": sum(a['general']['num_steps'] for a in all_analyses) / len(all_analyses),
        "avg_keys_obtained": sum(a['keys']['max_keys_in_hand'] for a in all_analyses) / len(all_analyses),
        "avg_monsters_revealed": sum(a['monsters']['total_revealed'] for a in all_analyses) / len(all_analyses),
        "total_sacrifices": sum(a['sanity']['sacrifices_performed'] for a in all_analyses),

        # d6 agregado de todos los juegos
        "d6_aggregate": _aggregate_d6(all_analyses),

        "individual_analyses": [a['file'] for a in all_analyses],
    }

    # Guardar reporte agregado
    version_dir = session_path.parent
    analysis_dir = version_dir / "analysis"
    aggregate_path = analysis_dir / f"{session_path.name}_session_aggregate.json"

    with open(aggregate_path, 'w') as f:
        json.dump(aggregate, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Reporte agregado: {aggregate_path}")
    print(f"\n📊 RESUMEN SESIÓN:")
    print(f"  Total partidas: {aggregate['total_games']}")
    print(f"  WIN: {aggregate['outcomes']['WIN']}")
    print(f"  LOSE: {aggregate['outcomes']['LOSE']}")
    print(f"  TIMEOUT: {aggregate['outcomes']['TIMEOUT']}")
    print(f"  Promedio rondas: {aggregate['avg_rounds']:.1f}")
    print(f"  Promedio llaves: {aggregate['avg_keys_obtained']:.1f}")

    return aggregate_path

def _aggregate_d6(analyses):
    """Agrega d6 de todos los juegos"""
    from collections import Counter
    total_d6 = Counter()

    for a in analyses:
        d6_dist = a['king']['d6_distribution']
        for value, count in d6_dist.items():
            total_d6[int(value)] += count

    return dict(total_d6)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/analyze_session_batch.py <session_dir>")
        sys.exit(1)

    analyze_session(sys.argv[1])
```

**Estimación:** 30 minutos

---

## PARTE 5: OPTIMIZACIÓN PARA ANÁLISIS LLM

### 5.1 Formato Optimizado para LLM

**Objetivo:** Crear archivos JSON que un LLM pueda leer fácilmente para generar insights.

**Estructura Propuesta:**

```json
{
  "meta": {
    "game_id": "v{commit}_{timestamp}_seed_001",
    "version": "{commit}",
    "timestamp": "2026-01-19T14:30:00",
    "outcome": "WIN"
  },

  "summary": {
    "players": 2,
    "rounds": 37,
    "steps": 187,
    "duration_seconds": 1.2,
    "win": true
  },

  "narrative": {
    "opening": "Partida de 2 jugadores que duró 37 rondas y terminó en victoria.",
    "key_events": [
      "Ronda 5: Se obtuvieron 2 llaves en F1_R1",
      "Ronda 12: Monstruo apareció en F2_R3",
      "Ronda 20: Jugador P1 llegó a -5 cordura",
      "Ronda 35: Se alcanzaron 4 llaves en mano",
      "Ronda 37: Victoria - todos en umbral con 4 llaves"
    ],
    "closing": "Victoria después de 37 rondas con tensión final de 0.988"
  },

  "statistics": {
    "keys": { /* ... */ },
    "monsters": { /* ... */ },
    "actions": { /* ... */ },
    "sanity": { /* ... */ },
    "king": { /* ... */ }
  },

  "timeline": [
    {
      "round": 1,
      "events": ["P1 moved to F1_R1", "P1 found KEY"],
      "sanity_min": 3,
      "keys_total": 1,
      "tension": 0.32
    },
    /* ... más rondas ... */
  ],

  "insights": {
    "critical_moments": [
      "Ronda 20: Cordura crítica (-5), riesgo alto",
      "Ronda 35: Punto de inflexión - 4 llaves alcanzadas"
    ],
    "player_performance": {
      "efficiency": "Alta - promedio 5 steps por llave",
      "risk_taking": "Moderada - 1 sacrificio realizado"
    },
    "king_pressure": {
      "effectiveness": "Alta - 15 cambios de piso",
      "d6_variance": "Baja - 81% efecto 1 (shuffle)"
    }
  }
}
```

**Archivo NUEVO:** `tools/export_for_llm.py`

```python
"""
Exporta análisis en formato optimizado para LLM.

- Narrativa legible
- Eventos clave
- Insights automáticos
- Timeline comprimido

Output: runs/v{commit}/analysis/{timestamp}_seed_XXX_llm_ready.json
"""

import json
from pathlib import Path
import sys

def generate_narrative(analysis):
    """Genera narrativa legible del juego"""
    g = analysis['general']
    k = analysis['keys']

    opening = f"Partida de {g['num_players']} jugadores que duró {g['num_rounds']} rondas "
    opening += f"y terminó en {g['outcome']}."

    key_events = []

    # Llaves
    if k['max_keys_in_hand'] >= 4:
        key_events.append(f"Se alcanzaron {k['max_keys_in_hand']} llaves en mano")

    if k['keys_destroyed'] > 0:
        key_events.append(f"{k['keys_destroyed']} llaves fueron destruidas")

    # Cordura
    s = analysis['sanity']
    if s['times_at_minus5'] > 0:
        key_events.append(f"Llegó a cordura -5 en {s['times_at_minus5']} ocasiones")

    if s['sacrifices_performed'] > 0:
        key_events.append(f"{s['sacrifices_performed']} sacrificios realizados")

    # Monstruos
    m = analysis['monsters']
    if m['total_revealed'] > 5:
        key_events.append(f"{m['total_revealed']} monstruos revelados")

    closing = f"{g['outcome']} después de {g['num_rounds']} rondas con tensión final de {analysis['tension']['final_tension']:.3f}"

    return {
        "opening": opening,
        "key_events": key_events,
        "closing": closing
    }

def generate_insights(analysis):
    """Genera insights automáticos"""
    insights = {
        "critical_moments": [],
        "player_performance": {},
        "king_pressure": {},
    }

    # Detectar momentos críticos
    s = analysis['sanity']
    if s['min_sanity_reached'] <= -4:
        insights['critical_moments'].append(
            f"Cordura crítica alcanzada: {s['min_sanity_reached']}"
        )

    k = analysis['keys']
    if k['times_reached_4_keys'] > 0:
        insights['critical_moments'].append(
            f"4 llaves alcanzadas (condición de victoria) en {k['times_reached_4_keys']} ocasiones"
        )

    # Performance de jugadores
    efficiency = k['max_keys_in_hand'] / max(analysis['general']['num_rounds'], 1)
    insights['player_performance']['key_efficiency'] = f"{efficiency:.2f} llaves/ronda"

    risk = "Alta" if s['sacrifices_performed'] > 0 else "Moderada" if s['times_at_minus5'] > 0 else "Baja"
    insights['player_performance']['risk_taking'] = risk

    # Presión del Rey
    ki = analysis['king']
    d6_dist = ki['d6_distribution']
    if d6_dist:
        most_common = max(d6_dist, key=d6_dist.get)
        percentage = (d6_dist[most_common] / sum(d6_dist.values())) * 100
        insights['king_pressure']['d6_most_common'] = f"Efecto {most_common} ({percentage:.0f}%)"

    insights['king_pressure']['floor_changes'] = ki['floor_changes']

    return insights

def export_for_llm(analysis_path: str):
    """
    Lee análisis comprehensivo y exporta versión optimizada para LLM.
    """
    with open(analysis_path, 'r') as f:
        analysis = json.load(f)

    # Generar versión LLM-optimizada
    llm_data = {
        "meta": {
            "game_id": Path(analysis_path).stem,
            "source_file": analysis['file'],
        },
        "summary": {
            "players": analysis['general']['num_players'],
            "rounds": analysis['general']['num_rounds'],
            "steps": analysis['general']['num_steps'],
            "outcome": analysis['general']['outcome'],
        },
        "narrative": generate_narrative(analysis),
        "statistics": analysis,  # Todo el análisis comprehensivo
        "insights": generate_insights(analysis),
    }

    # Guardar
    llm_path = Path(analysis_path).with_name(Path(analysis_path).stem + "_llm_ready.json")

    with open(llm_path, 'w') as f:
        json.dump(llm_data, f, indent=2, ensure_ascii=False)

    print(f"🤖 Exportado para LLM: {llm_path}")
    return llm_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/export_for_llm.py <analysis_path>")
        sys.exit(1)

    export_for_llm(sys.argv[1])
```

**Estimación:** 45 minutos

---

## RESUMEN DE ESTIMACIONES

| Tarea | Tiempo Estimado |
|-------|-----------------|
| **PARTE 1: Hooks Pendientes** | |
| 1.1 Destrucción Armería | 25 min |
| 1.2 Reset Peek | 10 min |
| 1.3 Habitaciones Especiales + Cámara Letal | 90 min |
| **PARTE 2: Análisis RNG** | |
| 2.1 Tracking Completo | 45 min |
| 2.2 Herramienta Análisis | 45 min |
| **PARTE 3: Guardado Versionado** | |
| 3.1-3.2 Sistema Versionado | 45 min |
| **PARTE 4: Análisis Comprehensivo** | |
| 4.2 Analyze Comprehensive | 90 min |
| 4.3 Batch Analysis | 30 min |
| **PARTE 5: Optimización LLM** | |
| 5.1 Export for LLM | 45 min |
| **TESTING Y VALIDACIÓN** | 60 min |
| **TOTAL** | **~485 min (~8 horas)** |

---

## ORDEN DE IMPLEMENTACIÓN RECOMENDADO

### Fase 1: Hooks Básicos (45 min)
1. ✅ Destrucción Armería (25 min)
2. ✅ Reset Peek (10 min)

### Fase 1.5: Sistema de Habitaciones Especiales (1.5 horas)
3. ✅ Sorteo de 3 habitaciones especiales en setup (30 min)
4. ✅ Implementación de Cámara Letal (60 min)
   - Acción de ritual
   - Lógica de 7ª llave
   - Tests (requiere clarificación sobre detalles del ritual)

### Fase 2: Sistema de Guardado (45 min)
5. ✅ Actualizar `run_versioned.py`
6. ✅ Crear estructura de carpetas

### Fase 3: Análisis Comprehensivo (2 horas)
7. ✅ `analyze_comprehensive.py`
8. ✅ `analyze_session_batch.py`

### Fase 4: RNG Extendido (1.5 horas)
9. ✅ Tracking RNG completo
10. ✅ `analyze_rng_complete.py`

### Fase 5: Optimización LLM (1 hora)
11. ✅ `export_for_llm.py`

### Fase 6: Testing (1 hora)
12. ✅ Tests para hooks
13. ✅ Tests para habitaciones especiales
14. ✅ Validación de herramientas

---

## PREGUNTAS PARA CLARIFICACIÓN

1. **✅ RESPONDIDO - Pool de Llaves (B3):**
   - ✅ La 7ª llave se obtiene mediante ritual en Cámara Letal (NO en setup inicial)
   - ✅ Cámara Letal es una habitación especial (sorteada, sin eventos asociados)
   - ✅ Motemey es habitación especial + tiene eventos (mazo siempre se arma)

2. **✅ RESPONDIDO - Detalles de Cámara Letal:**
   - ✅ Ritual requiere 2 jugadores en la habitación
   - ✅ NO consume acciones (acción gratuita)
   - ✅ Costo determinado por D6: [1-2: 7 a uno], [3-4: 3 y 4], [5-6: reparto libre de 7]
   - ✅ Revelación automática al entrar (primera vez, sin costo de acción)
   - ✅ Asignación: D4 por piso (1→R1, 2→R2, 3→R3, 4→R4) para cada habitación especial

3. **⚠️ PENDIENTE - Detalles de Asignación:**
   - ¿Las habitaciones especiales van en AMBOS pisos o solo en uno?
   - Si van en ambos: ¿Qué pasa si dos especiales caen en misma ubicación? (re-tirar, colisión, etc.)
   - ¿Es posible que una habitación especial salga dos veces en el mismo piso?

4. **⚠️ PENDIENTE - Eventos:**
   - ¿Cuáles eventos son críticos para implementar ahora?
   - ¿O podemos dejarlo para después de la base completa?

5. **⚠️ PENDIENTE - Análisis:**
   - ¿Hay alguna métrica adicional que quieras trackear?
   - ¿Formato de salida para LLM es adecuado?

---

## GUÍA DE IMPLEMENTACIÓN POR FASES (MODULAR)

**Nota:** Este plan está diseñado para ser implementado en sesiones independientes. Cada fase puede completarse en una sesión separada sin dependencia de las otras (excepto Fase 1 que es prerrequisito).

### 🎯 FASE 0: PREPARACIÓN (5 min)
**Objetivo:** Verificar estado del código antes de comenzar

**Checklist:**
- [ ] Leer `docs/IMPLEMENTATION_PLAN_2026_01_19.md` (este archivo)
- [ ] Ejecutar `pytest` para verificar que tests actuales pasan
- [ ] Revisar `git status` para ver cambios pendientes
- [ ] Decidir qué fase implementar

**Archivos clave a tener en mente:**
- `sim/runner.py` - Setup del juego
- `engine/actions.py` - Tipos de acciones
- `engine/legality.py` - Acciones legales
- `engine/transition.py` - Efectos de acciones
- `engine/state.py` - Estructura de estado

---

### 📦 FASE 1: HOOKS BÁSICOS (45 min)
**Prerequisitos:** Ninguno
**Puede implementarse independiente de otras fases:** ✅ SÍ

**Tareas:**
1. **Destrucción de Armería (25 min)**
   - Archivo: `engine/transition.py:200-250` (_resolve_card_minimal)
   - Agregar: Hook cuando MONSTER entra a ARMERÍA
   - Tests: `tests/test_armory.py`
   - Ver: Sección 1.1 del plan (líneas 36-74)

2. **Reset Peek al Final de Turno (10 min)**
   - Archivo: `engine/transition.py:373-400` (_start_new_round)
   - Agregar: Reset de `peek_used_this_turn`
   - Tests: `tests/test_peek_rooms.py`
   - Ver: Sección 1.2 del plan (líneas 76-107)

3. **Verificación (10 min)**
   - Ejecutar: `pytest tests/test_armory.py tests/test_peek_rooms.py`
   - Commit: "Implementar hooks B5 y B6: reset peek + destrucción armería"

**Criterio de éxito:** Tests pasan, no hay regresiones

---

### 🏛️ FASE 1.5: SISTEMA DE HABITACIONES ESPECIALES (1.5 horas)
**Prerequisitos:** Ninguno (independiente de Fase 1)
**Puede implementarse independiente de otras fases:** ✅ SÍ

**⚠️ IMPORTANTE:** Esta fase requiere clarificación de preguntas pendientes (ver sección PREGUNTAS líneas 1478-1503)

**Sub-fase A: Sorteo de Habitaciones Especiales (30 min)**
- Archivo: `sim/runner.py:18-77` (make_smoke_state)
- Agregar: Sorteo de 3 de 5 habitaciones especiales
- Agregar: Sistema D4 para asignación de ubicaciones
- Tests: `tests/test_special_rooms_setup.py` (nuevo)
- Ver: Paso 1 y 3 de sección 1.3 (líneas 143-356)

**Sub-fase B: Implementación Cámara Letal (60 min)**
- Archivos:
  - `engine/actions.py` - Agregar USE_CAMARA_LETAL_RITUAL
  - `engine/legality.py:119+` - Verificar 2 jugadores
  - `engine/transition.py:563+` - Lógica D6 y distribución cordura
- Tests: `tests/test_camara_letal.py` (nuevo)
- Ver: Paso 2 de sección 1.3 (líneas 197-289)

**Verificación:**
- [ ] `pytest tests/test_special_rooms_setup.py`
- [ ] `pytest tests/test_camara_letal.py`
- [ ] Commit: "Implementar B3: sistema de habitaciones especiales + Cámara Letal"

**Criterio de éxito:**
- Sorteo de 3 habitaciones funciona
- Ritual de Cámara Letal implementado con D6
- 7ª llave se agrega correctamente

---

### 💾 FASE 2: SISTEMA DE GUARDADO VERSIONADO (45 min)
**Prerequisitos:** Ninguno
**Puede implementarse independiente de otras fases:** ✅ SÍ

**Tareas:**
1. Actualizar `tools/run_versioned.py` (o crear nuevo)
2. Implementar estructura de carpetas versionada
3. Generar metadata.json por sesión
4. Ver: Sección 3.1-3.2 del plan (líneas 460-602)

**Verificación:**
- [ ] Ejecutar: `python tools/run_versioned.py --seeds 1 2 3`
- [ ] Verificar estructura: `runs/v{commit}/{timestamp}/`
- [ ] Verificar metadata.json generado
- [ ] Commit: "Implementar sistema de guardado versionado"

---

### 📊 FASE 3: ANÁLISIS COMPREHENSIVO (2 horas)
**Prerequisitos:** Fase 2 (para estructura de carpetas)
**Puede implementarse independiente de otras fases:** Requiere Fase 2

**Tareas:**
1. Crear `tools/analyze_comprehensive.py` (90 min)
   - Extraer todas las métricas (keys, monsters, sanity, king, tension)
   - Ver: Sección 4.2 (líneas 650-960)

2. Crear `tools/analyze_session_batch.py` (30 min)
   - Analizar sesión completa
   - Generar reporte agregado
   - Ver: Sección 4.3 (líneas 962-1068)

**Verificación:**
- [ ] `python tools/analyze_comprehensive.py runs/.../seed_001.jsonl`
- [ ] `python tools/analyze_session_batch.py runs/.../timestamp/`
- [ ] Commit: "Implementar análisis comprehensivo de partidas"

---

### 🎲 FASE 4: TRACKING RNG EXTENDIDO (1.5 horas)
**Prerequisitos:** Ninguno
**Puede implementarse independiente de otras fases:** ✅ SÍ

**Tareas:**
1. Actualizar `engine/rng.py` con tracking completo (45 min)
   - d6, d4, shuffles, choices
   - Ver: Sección 2.1 (líneas 278-372)

2. Crear `tools/analyze_rng_complete.py` (45 min)
   - Análisis estadístico de RNG
   - Chi-square tests
   - Ver: Sección 2.2 (líneas 374-452)

**Verificación:**
- [ ] Ejecutar partida y verificar tracking en RNG
- [ ] `python tools/analyze_rng_complete.py runs/.../seed_001.jsonl`
- [ ] Commit: "Implementar tracking y análisis extendido de RNG"

---

### 🤖 FASE 5: OPTIMIZACIÓN PARA LLM (1 hora)
**Prerequisitos:** Fase 3 (análisis comprehensivo)
**Puede implementarse independiente de otras fases:** Requiere Fase 3

**Tareas:**
1. Crear `tools/export_for_llm.py`
   - Generar narrativa legible
   - Insights automáticos
   - Timeline comprimido
   - Ver: Sección 5.1 (líneas 1070-1281)

**Verificación:**
- [ ] `python tools/export_for_llm.py runs/.../analysis/..._analysis.json`
- [ ] Verificar formato JSON optimizado
- [ ] Commit: "Implementar exportación optimizada para análisis LLM"

---

### ✅ FASE 6: TESTING Y VALIDACIÓN (1 hora)
**Prerequisitos:** Todas las fases anteriores implementadas
**Puede implementarse independiente de otras fases:** ❌ NO (es fase final)

**Tareas:**
1. Ejecutar suite completa de tests
2. Validar que todas las herramientas funcionan
3. Generar run completo end-to-end
4. Documentar cualquier issue encontrado

**Verificación:**
- [ ] `pytest` - todos los tests pasan
- [ ] Generar sesión completa: setup → run → análisis → export
- [ ] Commit: "Testing completo y validación de todas las fases"

---

## 🔄 CÓMO REANUDAR EL TRABAJO

**Si la sesión se interrumpe:**

1. **Leer este documento** desde el inicio
2. **Verificar qué fase estabas implementando:**
   - Revisar últimos commits: `git log --oneline -5`
   - Ver archivos modificados: `git status`
3. **Consultar la sección de la fase correspondiente** (líneas indicadas arriba)
4. **Continuar desde el último checkpoint**

**Cada fase es autocontenida y puede implementarse independientemente** (excepto dependencias explícitas).

---

**Próximo Paso:** Responder preguntas pendientes y comenzar Fase 1 (Hooks Básicos).

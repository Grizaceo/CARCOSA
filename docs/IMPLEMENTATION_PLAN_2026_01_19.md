# Plan de Implementación CARCOSA - 19 Enero 2026
**Versión Unificada** | Integra sistema de eventos, objetos, estados y herramientas

---

## TABLA DE CONTENIDOS

1. [Corrección de Informe](#corrección-de-informe)
2. [Estado Actual del Engine](#estado-actual-del-engine)
3. [FASE 0: Sistema Base Requerido (CRÍTICO)](#fase-0-sistema-base-requerido-crítico)
4. [FASE 1: Hooks Básicos](#fase-1-hooks-básicos)
5. [FASE 1.5: Habitaciones Especiales](#fase-15-habitaciones-especiales)
6. [FASE 2: Eventos Existentes](#fase-2-eventos-existentes)
7. [FASE 3: Estados Canónicos](#fase-3-estados-canónicos)
8. [FASE 4: Objetos y Tesoros](#fase-4-objetos-y-tesoros)
9. [FASE 5: Habitaciones Especiales Pendientes](#fase-5-habitaciones-especiales-pendientes)
10. [FASE 6: Análisis y Tracking RNG](#fase-6-análisis-y-tracking-rng)
11. [FASE 7: Sistema de Guardado Versionado](#fase-7-sistema-de-guardado-versionado)
12. [FASE 8: Optimización para LLM](#fase-8-optimización-para-llm)
13. [Resumen de Estimaciones](#resumen-de-estimaciones)
14. [Orden de Implementación](#orden-de-implementación)
15. [Cómo Reanudar el Trabajo](#cómo-reanudar-el-trabajo)
16. [Propuestas No Aprobadas](#propuestas-no-aprobadas)
17. [Referencias](#referencias)

---

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

## ESTADO ACTUAL DEL ENGINE

### ✅ Implementado

```
engine/
├── actions.py      → MOVE, SEARCH, MEDITATE, END_TURN, SACRIFICE, ESCAPE_TRAPPED
│                     USE_MOTEMEY_BUY/SELL, USE_YELLOW_DOORS, USE_PEEK_ROOMS
│                     USE_ARMORY_DROP/TAKE, KING_ENDROUND
├── state.py        → PlayerState (sanity, keys, objects, statuses, soulbound_items)
│                     StatusInstance (status_id, remaining_rounds, stacks)
│                     MonsterState, DeckState, BoxState, GameState
├── transition.py   → _resolve_card_minimal() [KEY, MONSTER:*, STATE:*, CROWN]
│                     Fin de ronda: Casa, Ruleta d4, Presencia, d6, Estados
│                     ✅ Hook: Armería destruida por monstruo (Fase 1)
│                     ✅ Hook: Reset Peek al inicio de ronda (Fase 1)
├── legality.py     → Acciones legales por fase y condición
├── board.py        → Grafo de nodos, rotación sushi, escaleras
└── config.py       → KEYS_TOTAL=6, S_LOSS=-5, etc.
```

### ❌ NO Implementado

| Subsistema | Descripción | Fase |
|------------|-------------|------|
| **Resolución de EVENTOS** | `_resolve_card_minimal()` ignora `EVENT:*` | Fase 0 |
| **Sistema Total** | `Total = d6 + cordura_actual` no existe | Fase 0 |
| **Efectos de Objetos** | Brújula, Vial, Contundente son strings sin lógica | Fase 0 |
| **Estados Canónicos** | Sangrado, Maldito, Paranoia, Sanidad, Vanidad | Fase 3 |
| **Habitaciones** | Cámara Letal, Taberna, Salón de Belleza | Fase 1.5, 5 |
| **7 Eventos Existentes** | EVT-01 a EVT-07 del juego físico | Fase 2 |

### ⚠️ Parcialmente Implementado

| Elemento | Estado | Falta | Fase |
|----------|--------|-------|------|
| ILLUMINATED | Tests existen | No otorga +1 acción realmente | Fase 3 |
| TRAPPED | ESCAPE_TRAPPED funciona | No se aplica desde cartas | - |

---

## FASE 0: SISTEMA BASE REQUERIDO (CRÍTICO)

> **⚠️ BLOQUEANTE:** Esta fase debe completarse ANTES de implementar los 7 eventos existentes (Fase 2).

**Estimación Total:** 5-6 horas

---

### 0.1 Sistema de Resolución de Eventos 🔴

**Prioridad:** CRÍTICA (bloquea 7 eventos existentes)

**Archivo:** `engine/transition.py`

**Ubicación:** Función `_resolve_card_minimal()` (~línea 129)

**Implementación:**
```python
def _resolve_card_minimal(s, pid: PlayerId, card, cfg, rng: Optional[RNG] = None):
    s_str = str(card)
    p = s.players[pid]

    # ... código existente para KEY, MONSTER, STATE, CROWN ...

    # NUEVO: Resolución de eventos
    if s_str.startswith("EVENT:"):
        event_id = s_str.split(":", 1)[1]
        _resolve_event(s, pid, event_id, cfg, rng)
        return


def _resolve_event(s: GameState, pid: PlayerId, event_id: str, cfg: Config, rng: RNG):
    """
    Resuelve un evento por su ID.

    Convención: Total = d6 + cordura_actual (clamp mínimo 0)
    """
    p = s.players[pid]

    # Calcular Total (usado por muchos eventos)
    d6 = rng.randint(1, 6)
    total = max(0, d6 + p.sanity)

    # Dispatch por event_id
    if event_id == "REFLEJO_AMARILLO":
        _event_reflejo_amarillo(s, pid, cfg)
    elif event_id == "ESPEJO_AMARILLO":
        _event_espejo_amarillo(s, pid, cfg)
    elif event_id == "HAY_CADAVER":
        _event_hay_cadaver(s, pid, total, cfg, rng)
    elif event_id == "COMIDA_SERVIDA":
        _event_comida_servida(s, pid, total, cfg, rng)
    elif event_id == "DIVAN_AMARILLO":
        _event_divan_amarillo(s, pid, total, cfg)
    elif event_id == "CAMBIA_CARAS":
        _event_cambia_caras(s, pid, total, cfg)
    elif event_id == "FURIA_AMARILLO":
        _event_furia_amarillo(s, pid, total, cfg, rng)
    # ... más eventos ...

    # Evento vuelve al fondo del mazo (convención)
    # SUPUESTO: Los eventos no se descartan, vuelven al fondo
    from engine.board import active_deck_for_room
    deck = active_deck_for_room(s, p.room)
    if deck is not None:
        deck.cards.append(CardId(f"EVENT:{event_id}"))
```

**Tests requeridos:**
```python
# tests/test_event_resolution.py (NUEVO ARCHIVO)
def test_event_card_triggers_resolution():
    """EVENT:X en mazo debe llamar a _resolve_event()"""

def test_event_returns_to_bottom():
    """Evento resuelto vuelve al fondo del mazo"""

def test_total_calculation():
    """Total = d6 + cordura, clamp mínimo 0"""
    # Total con cordura positiva
    # Total con cordura negativa (clamp a 0)
    # Total con cordura 0
```

**Estimación:** 2-3 horas

---

### 0.2 Funciones de Utilidad para Eventos 🟡

**Prioridad:** ALTA (reutilizadas por múltiples eventos)

**Archivo:** `engine/effects/event_utils.py` (NUEVO)

**Implementación:**
```python
# engine/effects/event_utils.py

from engine.state import GameState, PlayerState, StatusInstance
from engine.types import PlayerId, RoomId
from typing import List


def swap_positions(s: GameState, pid1: PlayerId, pid2: PlayerId) -> None:
    """Intercambia ubicación de dos jugadores."""
    p1, p2 = s.players[pid1], s.players[pid2]
    p1.room, p2.room = p2.room, p1.room


def move_player_to_room(s: GameState, pid: PlayerId, room: RoomId) -> None:
    """Mueve un jugador a una habitación específica."""
    s.players[pid].room = room


def remove_all_statuses(p: PlayerState) -> None:
    """Remueve todos los estados de un jugador."""
    p.statuses = []


def remove_status(p: PlayerState, status_id: str) -> bool:
    """Remueve un estado específico. Retorna True si existía."""
    original_len = len(p.statuses)
    p.statuses = [st for st in p.statuses if st.status_id != status_id]
    return len(p.statuses) < original_len


def add_status(p: PlayerState, status_id: str, duration: int = 2) -> None:
    """Agrega un estado con duración."""
    p.statuses.append(StatusInstance(status_id=status_id, remaining_rounds=duration))


def get_player_by_turn_offset(s: GameState, pid: PlayerId, offset: int) -> PlayerId:
    """
    Obtiene jugador a la derecha (+1) o izquierda (-1) según orden de turno.
    """
    idx = s.turn_order.index(pid)
    new_idx = (idx + offset) % len(s.turn_order)
    return s.turn_order[new_idx]


def get_players_in_floor(s: GameState, floor: int) -> List[PlayerId]:
    """Retorna lista de jugadores en un piso."""
    from engine.board import floor_of
    return [pid for pid, p in s.players.items() if floor_of(p.room) == floor]


def invert_sanity(p: PlayerState) -> None:
    """Invierte la cordura: cordura_nueva = cordura_actual × (-1)"""
    p.sanity = -p.sanity
```

**Tests requeridos:**
```python
# tests/test_event_utils.py (NUEVO ARCHIVO)
def test_swap_positions():
    """Swap intercambia posiciones correctamente"""

def test_remove_status():
    """remove_status elimina estado específico"""

def test_get_player_by_turn_offset():
    """get_player_by_turn_offset obtiene jugador correcto"""
```

**Estimación:** 1 hora

---

### 0.3 Sistema de Objetos con Efectos 🟡

**Prioridad:** MEDIA (necesario para objetos existentes)

**Archivo:** `engine/objects.py` (NUEVO)

**Implementación:**
```python
# engine/objects.py
from dataclasses import dataclass
from typing import Optional
from engine.state import GameState, PlayerState
from engine.types import PlayerId


@dataclass
class ObjectDefinition:
    object_id: str
    name: str
    uses: Optional[int]  # None = infinito, 1 = consumible
    is_blunt: bool = False  # Objeto contundente
    is_treasure: bool = False


# Catálogo de objetos existentes
OBJECT_CATALOG = {
    "COMPASS": ObjectDefinition("COMPASS", "Brújula", uses=1, is_blunt=False),
    "VIAL": ObjectDefinition("VIAL", "Vial", uses=1, is_blunt=False),
    "BLUNT": ObjectDefinition("BLUNT", "Objeto Contundente", uses=1, is_blunt=True),
    "ROPE": ObjectDefinition("ROPE", "Cuerda", uses=1, is_blunt=False),
}


def use_object(s: GameState, pid: PlayerId, object_id: str, cfg, rng) -> bool:
    """
    Usa un objeto del inventario.
    Retorna True si se usó exitosamente.
    """
    p = s.players[pid]
    if object_id not in p.objects:
        return False

    obj_def = OBJECT_CATALOG.get(object_id)
    if obj_def is None:
        return False

    # Aplicar efecto según tipo
    if object_id == "COMPASS":
        _use_compass(s, pid, cfg)
    elif object_id == "VIAL":
        _use_vial(s, pid, cfg)
    elif object_id == "BLUNT":
        _use_blunt(s, pid, cfg)
    # ... más objetos ...

    # Consumir si tiene usos limitados
    if obj_def.uses is not None:
        p.objects.remove(object_id)

    return True


def _use_compass(s: GameState, pid: PlayerId, cfg) -> None:
    """Brújula: Mueve al pasillo del piso actual. Acción gratuita."""
    from engine.board import floor_of, corridor_id
    p = s.players[pid]
    floor = floor_of(p.room)
    p.room = corridor_id(floor)


def _use_vial(s: GameState, pid: PlayerId, cfg) -> None:
    """Vial: Recupera 2 de cordura. Acción gratuita."""
    p = s.players[pid]
    p.sanity = min(p.sanity + 2, p.sanity_max or p.sanity + 2)


def _use_blunt(s: GameState, pid: PlayerId, cfg) -> None:
    """
    Objeto Contundente: Aturde monstruo en la habitación por 2 rondas.
    SUPUESTO: Se marca en flags del GameState.
    """
    p = s.players[pid]
    for monster in s.monsters:
        if monster.room == p.room:
            s.flags[f"STUN_{monster.monster_id}_UNTIL_ROUND"] = s.round + 2
            break
```

**Tests requeridos:**
```python
# tests/test_objects.py (NUEVO ARCHIVO)
def test_use_vial():
    """Vial recupera 2 cordura"""

def test_use_compass():
    """Brújula mueve al pasillo"""

def test_use_blunt():
    """Contundente aturde monstruo"""
```

**Estimación:** 2 horas

---

## FASE 1: HOOKS BÁSICOS

> **✅ COMPLETADO** (Commit 334d9ec)

**Estimación Total:** 45 minutos

---

### 1.1 Destrucción de Armería por Monstruo (B6) ✅

**Archivo:** `engine/transition.py`

**Implementación:**
```python
# En _resolve_card_minimal(), línea 156-162
# B6: Hook destrucción de Armería cuando monstruo entra
if "_ARMERY" in str(p.room):
    # Marcar armería como destruida
    s.flags[f"ARMORY_DESTROYED_{p.room}"] = True
    # Vaciar almacenamiento de la armería
    if p.room in s.armory_storage:
        s.armory_storage[p.room] = []
```

**Tests agregados:**
- `tests/test_armory.py:test_armory_destroyed_by_monster()` (líneas 232-255)
- `tests/test_armory.py:test_armory_destroyed_prevents_drop_take()` (líneas 258-282)

**Estimación:** 25 minutos ✅

---

### 1.2 Reset Automático de Peek al Final del Turno (B5) ✅

**Archivo:** `engine/transition.py`

**Implementación:**
```python
# En _start_new_round(), línea 417
# B5: Reset de Peek al inicio de nueva ronda
s.peek_used_this_turn = {}
```

**Tests agregados:**
- `tests/test_peek_rooms.py:test_peek_resets_at_new_round()` (líneas 194-213)

**Estimación:** 10 minutos ✅

---

## FASE 1.5: HABITACIONES ESPECIALES (P1)

**Estimación Total:** 3 horas

**Referencia:** Plan P1 - Habitaciones Especiales (imágenes compartidas 2026-01-20)

---

### 1.5.0 Modelo de Datos para Habitaciones Especiales

**Archivo:** `engine/state.py`

**Implementación:**
```python
@dataclass
class RoomState:
    room_id: RoomId
    deck: DeckState
    revealed: int = 0

    # NUEVO P1: Sistema de habitaciones especiales
    special_card_id: Optional[str] = None  # ID de la habitación especial ("CAMARA_LETAL", "PEEK", etc.)
    special_revealed: bool = False          # Si la carta especial ha sido revelada
    special_destroyed: bool = False         # Si fue destruida por monstruo
    special_activation_count: int = 0       # Contador de activaciones (para Salón de Belleza, etc.)
```

**Tests:**
```python
# tests/test_special_rooms_model.py (NUEVO)
def test_room_state_has_special_fields():
    """RoomState tiene campos para habitaciones especiales"""
    room = RoomState(room_id="F1_R1", deck=DeckState(cards=[]))
    assert room.special_card_id is None
    assert room.special_revealed is False
    assert room.special_destroyed is False
    assert room.special_activation_count == 0
```

**Estimación:** 15 minutos

---

### 1.5.1 Sistema de Sorteo y Asignación (Setup)

**CONTEXTO (Canon Confirmado + P1):**

Durante el setup del juego:
1. Se eligen **3 habitaciones especiales al azar** de las 5 disponibles:
   - B2: Motemey
   - B3: Cámara Letal
   - B4: Puertas Amarillas
   - B5: Peek (Mirador)
   - B6: Armería

2. Para cada habitación especial seleccionada:
   - Se lanza **D4 para cada piso** (F1, F2, F3)
   - Resultado D4: `1→R1, 2→R2, 3→R3, 4→R4`
   - Se coloca la carta especial **boca abajo** en esas ubicaciones

3. **Cámara Letal** (habitación especial):
   - NO tiene eventos asociados (a diferencia del Motemey)
   - Solo existe como habitación si sale en el sorteo de las 3
   - Cuando es **revelada**, se habilita la posibilidad de obtener la 7ª llave
   - Los jugadores activan un **ritual** en la Cámara Letal para obtener la llave

4. **Motemey** (habitación especial + eventos):
   - Es una habitación especial (puede salir en sorteo de 3)
   - **ADEMÁS** tiene eventos de Motemey que aparecen en otras habitaciones
   - Su mazo **siempre se arma** en setup (independiente del sorteo)

**ESTADO ACTUAL DEL CÓDIGO:**
- ❌ No existe lógica de sorteo de 3 habitaciones especiales
- ❌ No existe asignación con D4
- ✅ Motemey implementado (habitación + mazo de eventos)
- ✅ Puertas, Peek, Armería implementados
- ❌ Cámara Letal NO implementada
- ❌ No existe sistema de revelación automática

---

**Paso 1: Sistema de Sorteo de Habitaciones Especiales**

**Archivo:** `sim/runner.py`

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

**Paso 2: Sistema de Asignación de Ubicaciones con D4**

**Asignación de Ubicaciones (Canon Confirmado):**
1. Se eligen 3 habitaciones especiales al azar
2. Para cada habitación especial:
   - Se lanza D4 secuencialmente para F1, F2, F3
   - Resultado D4: `1→R1, 2→R2, 3→R3, 4→R4`
   - Ejemplo: Si sale `[2, 3, 1]` → habitación va en `F1_R2`, `F2_R3`, `F3_R1`

```python
def make_smoke_state(seed: int = 1, cfg: Optional[Config] = None) -> GameState:
    # ... (código anterior de sorteo) ...

    selected_special_rooms = rng.sample(available_special_rooms, 3)

    # NUEVO: Asignar ubicaciones con D4
    special_room_locations = {}

    for special_room in selected_special_rooms:
        # Tirar D4 para cada piso (F1, F2, F3)
        f1_roll = rng.randint(1, 4)  # D4 para piso 1
        f2_roll = rng.randint(1, 4)  # D4 para piso 2
        f3_roll = rng.randint(1, 4)  # D4 para piso 3

        # Mapeo: 1→R1, 2→R2, 3→R3, 4→R4
        special_room_locations[special_room] = {
            "F1": f"F1_R{f1_roll}",
            "F2": f"F2_R{f2_roll}",
            "F3": f"F3_R{f3_roll}"
        }

    # Guardar en state para referencia
    s.flags["SPECIAL_ROOM_LOCATIONS"] = special_room_locations

    # Crear habitaciones con nombres apropiados
    for floor in ["F1", "F2", "F3"]:
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

**Paso 3: Hook - Revelación Automática al Entrar (P1)**

**Archivo:** `engine/transition.py`

**Ubicación:** En la función de `MOVE` o después de mover al jugador

**Implementación:**
```python
def _on_player_enters_room(s: GameState, pid: PlayerId, room: RoomId) -> None:
    """
    Hook P1: Cuando un jugador entra a una habitación, revelar carta especial si existe.
    Revelación NO consume acciones.
    """
    if room not in s.rooms:
        return

    room_state = s.rooms[room]

    # Si hay una carta especial boca abajo, revelarla
    if (room_state.special_card_id is not None and
        not room_state.special_revealed and
        not room_state.special_destroyed):

        room_state.special_revealed = True
        # Log o tracking de revelación
        s.flags[f"SPECIAL_REVEALED_{room}_{room_state.special_card_id}"] = s.round
```

**Tests:**
```python
# tests/test_special_rooms_reveal.py (NUEVO)
def test_player_enters_reveals_special():
    """Primera entrada a habitación especial la revela automáticamente"""

def test_reveal_is_idempotent():
    """Segunda entrada no vuelve a revelar (idempotente)"""

def test_reveal_does_not_consume_actions():
    """Revelar especial NO reduce actions_left"""
```

**Estimación:** 30 minutos

---

**Paso 4: Hook - Destrucción por Monstruo (P1)**

**Archivo:** `engine/transition.py`

**Ubicación:** En `_resolve_card_minimal()` cuando se resuelve `MONSTER:*`

**Implementación:**
```python
# En _resolve_card_minimal(), después de crear MonsterState
if s_str.startswith("MONSTER:"):
    # ... código existente que crea el monstruo ...

    # P1: Hook destrucción de habitación especial
    if p.room in s.rooms:
        room_state = s.rooms[p.room]
        if (room_state.special_card_id is not None and
            not room_state.special_destroyed):

            # Marcar como destruida
            room_state.special_destroyed = True

            # ESPECÍFICO: Armería vacía su almacenamiento
            if "_ARMERY" in str(p.room):
                if p.room in s.armory_storage:
                    s.armory_storage[p.room] = []
```

**Tests:**
```python
# tests/test_special_rooms_destruction.py (NUEVO)
def test_monster_destroys_special_room():
    """Monstruo entrando destruye habitación especial"""

def test_destroyed_room_prevents_activation():
    """Habitación destruida no puede activarse"""

def test_armory_specific_destruction():
    """Armería destruida vacía su almacenamiento"""
```

**Estimación:** 20 minutos

---

**Paso 5: Implementar Habitación Cámara Letal**

**Archivo:** `engine/actions.py`

Agregar nueva acción:
```python
# Cámara Letal (B3)
USE_CAMARA_LETAL_RITUAL = "USE_CAMARA_LETAL_RITUAL"
```

**Archivo:** `engine/legality.py`

Agregar legalidad:
```python
# B3 - Cámara Letal: Ritual para obtener 7ª llave
camara_letal_pattern = "_CAMARA_LETAL"
is_in_camara_letal = camara_letal_pattern in str(p.room)

if is_in_camara_letal and s.flags.get("CAMARA_LETAL_PRESENT", False):
    if not s.flags.get("CAMARA_LETAL_RITUAL_COMPLETED", False):
        # Verificar que hay exactamente 2 jugadores en la habitación
        players_in_room = [
            pid for pid in s.players
            if s.players[pid].room == p.room
        ]

        if len(players_in_room) == 2:
            legal_actions.append(Action(
                type=ActionType.USE_CAMARA_LETAL_RITUAL,
                data={}
            ))
```

**Archivo:** `engine/transition.py`

Agregar transición:
```python
elif action.type == ActionType.USE_CAMARA_LETAL_RITUAL:
    # Ritual en Cámara Letal: agrega 7ª llave
    if not s.flags.get("CAMARA_LETAL_RITUAL_COMPLETED", False):
        players_in_room = [
            pid for pid, player in s.players.items()
            if player.room == p.room
        ]

        if len(players_in_room) == 2:
            # Lanzar D6 para determinar costo de cordura
            d6 = rng.randint(1, 6)

            # action.data debe contener:
            #   - "sanity_distribution": [cost_p1, cost_p2]
            #   - "key_recipient": pid del jugador que recibe la llave

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
                for i, pid_in_room in enumerate(players_in_room):
                    cost = sanity_costs[i]
                    s.players[pid_in_room].sanity -= cost

                # Agregar llave al jugador designado
                s.players[key_recipient].keys += 1

                # Marcar ritual como completado
                s.flags["CAMARA_LETAL_RITUAL_COMPLETED"] = True
                s.flags["CAMARA_LETAL_D6"] = d6  # Para tracking
```

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
    """Ritual en Cámara Letal agrega 7ª llave"""

def test_ritual_only_once():
    """Ritual solo se puede hacer una vez por partida"""

def test_ritual_d6_distributions():
    """Verifica distribuciones de cordura según D6"""
```

**Estimación:** 45 minutos

---

**RESUMEN FASE 1.5:**

| Paso | Descripción | Tiempo | Acumulado |
|------|-------------|--------|-----------|
| 1.5.0 | Modelo de Datos | 15 min | 15 min |
| 1.5.1 | Sorteo y Asignación | 60 min | 75 min |
| 1.5.2 | Hook Revelación | 30 min | 105 min |
| 1.5.3 | Hook Destrucción | 20 min | 125 min |
| 1.5.4 | Cámara Letal | 45 min | 170 min |
| **TOTAL** | | **~3 horas** | |

**Definition of Done P1:**
- ✅ Setup crea exactamente 3 salas especiales boca abajo en habitaciones canónicas válidas
- ✅ Primera entrada revela 1 vez (idempotente)
- ✅ Activación no reduce actions_left
- ✅ Segunda activación: al menos 1 sala demuestra contador de activación
- ✅ Entrada/spawn de monstruo destruye la sala especial y esta deja de activarse
- ✅ pytest -q sin fallos: tests deterministas

---

## FASE 2: EVENTOS EXISTENTES

> **⚠️ Prerequisito:** FASE 0 debe estar completada

**Estimación Total:** 3.5-4 horas

**Orden de implementación:** Por dependencias técnicas (menor a mayor complejidad)

---

### 2.1 EVT-01: El Reflejo de Amarillo 🟢

**Prioridad:** 1 (más simple, sin dependencias)

**Regla física:** `-2 cordura`

**Dependencias:** Ninguna

**Implementación:**
```python
def _event_reflejo_amarillo(s: GameState, pid: PlayerId, cfg: Config) -> None:
    """
    El reflejo de Amarillo: -2 cordura.
    Canon: Efecto directo sin tirada.
    """
    p = s.players[pid]
    p.sanity -= 2
```

**Tests:**
```python
# tests/test_events.py (NUEVO)
def test_event_reflejo_amarillo():
    """Reflejo de Amarillo aplica -2 cordura"""
    s = setup_state_with_event("REFLEJO_AMARILLO")
    p1 = s.players[PlayerId("P1")]
    initial_sanity = p1.sanity

    trigger_event(s, "P1", "REFLEJO_AMARILLO")

    assert p1.sanity == initial_sanity - 2
```

**Estimación:** 15 minutos

---

### 2.2 EVT-02: Espejo de Amarillo 🟢

**Prioridad:** 2 (simple, sin dependencias)

**Regla física:** `Invierte la cordura del jugador (× -1)`

**Dependencias:** `invert_sanity()` de Fase 0.2

**Implementación:**
```python
def _event_espejo_amarillo(s: GameState, pid: PlayerId, cfg: Config) -> None:
    """
    Espejo de Amarillo: invierte la cordura (cordura × -1).
    Ejemplo: cordura 3 → -3, cordura -2 → 2
    """
    p = s.players[pid]
    p.sanity = -p.sanity
```

**Tests:**
```python
def test_event_espejo_amarillo_positive():
    """Espejo invierte cordura positiva a negativa"""
    s = setup_state_with_sanity(3)
    trigger_event(s, "P1", "ESPEJO_AMARILLO")
    assert s.players[PlayerId("P1")].sanity == -3

def test_event_espejo_amarillo_negative():
    """Espejo invierte cordura negativa a positiva"""
    s = setup_state_with_sanity(-2)
    trigger_event(s, "P1", "ESPEJO_AMARILLO")
    assert s.players[PlayerId("P1")].sanity == 2
```

**Estimación:** 15 minutos

---

### 2.3 EVT-03: Hay un Cadáver 🟡

**Prioridad:** 3 (requiere Total + skip turn + obtener objeto)

**Regla física:**
- `Total 0-2`: Pierdes un turno
- `Total 3-4`: -1 cordura
- `Total 5+`: Obtienes 1 objeto contundente

**Dependencias:**
- Fase 0.1 Sistema de Total ✅
- `skip_next_turn` flag (NUEVO)
- Sistema de obtener objeto desde evento

**Implementación:**
```python
def _event_hay_cadaver(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Hay un cadáver: según Total.
    0-2: Pierdes turno siguiente
    3-4: -1 cordura
    5+: Obtienes objeto contundente
    """
    p = s.players[pid]

    if total <= 2:
        # Pierdes turno: flag para saltar próximo turno
        s.flags[f"SKIP_TURN_{pid}"] = True
    elif total <= 4:
        p.sanity -= 1
    else:  # total >= 5
        # Obtener objeto contundente
        p.objects.append("BLUNT")
```

**Código adicional en `transition.py`:**
```python
# En inicio de turno (_advance_turn_or_king)
def _check_skip_turn(s: GameState, pid: PlayerId) -> bool:
    """Verifica y consume flag de saltar turno."""
    flag_key = f"SKIP_TURN_{pid}"
    if s.flags.get(flag_key, False):
        s.flags[flag_key] = False
        return True
    return False
```

**Tests:**
```python
def test_event_hay_cadaver_total_0_2():
    """Total 0-2: pierde turno siguiente"""

def test_event_hay_cadaver_total_3_4():
    """Total 3-4: -1 cordura"""

def test_event_hay_cadaver_total_5_plus():
    """Total 5+: obtiene contundente"""
```

**Estimación:** 45 minutos

---

### 2.4 EVT-04: Un Diván de Amarillo 🟡

**Prioridad:** 4 (requiere Total + remover estados + estado Sanidad)

**Regla física:**
- `Total 0-3`: Quita efectos activos
- `Total 4-7`: Quita efectos y +1 cordura
- `Total 8+`: Obtienes estado Sanidad

**Dependencias:**
- Fase 0.1 Sistema de Total ✅
- `remove_all_statuses()` de Fase 0.2
- Estado SANIDAD (Fase 3)

**Implementación:**
```python
def _event_divan_amarillo(s: GameState, pid: PlayerId, total: int, cfg: Config) -> None:
    """
    Un diván de Amarillo: según Total.
    0-3: Quita todos los estados
    4-7: Quita estados + 1 cordura
    8+: Obtiene estado Sanidad
    """
    from engine.effects.event_utils import add_status
    p = s.players[pid]

    if total <= 3:
        p.statuses = []
    elif total <= 7:
        p.statuses = []
        p.sanity = min(p.sanity + 1, p.sanity_max or p.sanity + 1)
    else:  # total >= 8
        add_status(p, "SANIDAD", duration=2)
```

**Tests:**
```python
def test_event_divan_total_0_3():
    """Total 0-3: remueve todos los estados"""

def test_event_divan_total_4_7():
    """Total 4-7: remueve estados + 1 cordura"""

def test_event_divan_total_8_plus():
    """Total 8+: obtiene estado Sanidad"""
```

**Estimación:** 30 minutos

---

### 2.5 EVT-05: Cambia Caras 🟡

**Prioridad:** 5 (requiere Total + swap posición + orden de turno)

**Regla física:**
- `Total 0-3`: Intercambias posición con el alma a tu derecha
- `Total 4+`: Intercambias posición con el alma a tu izquierda

**Dependencias:**
- Fase 0.1 Sistema de Total ✅
- `swap_positions()` de Fase 0.2
- `get_player_by_turn_offset()` de Fase 0.2

**Implementación:**
```python
def _event_cambia_caras(s: GameState, pid: PlayerId, total: int, cfg: Config) -> None:
    """
    Cambia caras: según Total.
    0-3: Swap con jugador a la derecha (orden turno +1)
    4+: Swap con jugador a la izquierda (orden turno -1)
    """
    from engine.effects.event_utils import swap_positions, get_player_by_turn_offset

    if len(s.turn_order) < 2:
        return  # No hay con quién intercambiar

    offset = 1 if total <= 3 else -1
    target_pid = get_player_by_turn_offset(s, pid, offset)
    swap_positions(s, pid, target_pid)
```

**Tests:**
```python
def test_event_cambia_caras_total_low():
    """Total 0-3: swap con derecha"""

def test_event_cambia_caras_total_high():
    """Total 4+: swap con izquierda"""

def test_event_cambia_caras_single_player():
    """Con 1 jugador, no hace nada"""
```

**Estimación:** 30 minutos

---

### 2.6 EVT-06: Una Comida Servida 🟡

**Prioridad:** 6 (requiere Total + mover otro jugador)

**Regla física:**
- `Total 0`: -3 cordura
- `Total 1-2`: Ganas estado Sangrado
- `Total 3-6`: +2 cordura
- `Total 7+`: Trae otra alma a tu habitación y ambos +2 cordura

**Dependencias:**
- Fase 0.1 Sistema de Total ✅
- `move_player_to_room()` de Fase 0.2
- Estado SANGRADO (Fase 3)

**Implementación:**
```python
def _event_comida_servida(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Una comida servida: según Total.
    0: -3 cordura
    1-2: Estado Sangrado
    3-6: +2 cordura
    7+: Trae otro jugador a tu habitación, ambos +2 cordura
    """
    from engine.effects.event_utils import add_status
    p = s.players[pid]

    if total == 0:
        p.sanity -= 3
    elif total <= 2:
        add_status(p, "SANGRADO", duration=2)
    elif total <= 6:
        p.sanity = min(p.sanity + 2, p.sanity_max or p.sanity + 2)
    else:  # total >= 7
        # Traer otro jugador (aleatorio)
        other_pids = [pid2 for pid2 in s.players if pid2 != pid]
        if other_pids:
            target_pid = rng.choice(other_pids)
            s.players[target_pid].room = p.room
            # Ambos +2 cordura
            p.sanity = min(p.sanity + 2, p.sanity_max or p.sanity + 2)
            target = s.players[target_pid]
            target.sanity = min(target.sanity + 2, target.sanity_max or target.sanity + 2)
```

**Tests:**
```python
def test_event_comida_total_0():
    """Total 0: -3 cordura"""

def test_event_comida_total_1_2():
    """Total 1-2: estado Sangrado"""

def test_event_comida_total_3_6():
    """Total 3-6: +2 cordura"""

def test_event_comida_total_7_plus():
    """Total 7+: trae otro jugador, ambos +2"""
```

**Estimación:** 45 minutos

---

### 2.7 EVT-07: La Furia de Amarillo 🔴

**Prioridad:** 7 (más complejo, requiere modificadores del Rey)

**Regla física:**
- `Total 0`: Dobla el efecto del Rey por 2 rondas
- `Total 1-4`: El Rey se mueve al piso del alma activa
- `Total 5+`: Aturde al Rey 1 ronda

**Dependencias:**
- Fase 0.1 Sistema de Total ✅
- `king_damage_modifier` (NUEVO en GameState)
- `king_vanish_ends` (ya existe)

**SUPUESTO:** "Dobla permanentemente" se limita a 2 rondas para balance.

**Implementación:**
```python
def _event_furia_amarillo(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    La furia de Amarillo: según Total.
    0: Dobla efecto del Rey por 2 rondas (SUPUESTO: no permanente)
    1-4: Rey se mueve al piso del jugador activo
    5+: Aturde al Rey 1 ronda (no se manifiesta)
    """
    from engine.board import floor_of
    p = s.players[pid]

    if total == 0:
        # SUPUESTO: Limitado a 2 rondas
        s.flags["KING_DAMAGE_DOUBLE_UNTIL"] = s.round + 2
    elif total <= 4:
        s.king_floor = floor_of(p.room)
    else:  # total >= 5
        s.king_vanish_ends = s.round + 1
```

**Código adicional en `transition.py` (KING_ENDROUND):**
```python
# En cálculo de presencia del Rey
def _presence_damage_for_round(round_num: int, s: GameState) -> int:
    base = _base_presence_damage(round_num)
    if s.flags.get("KING_DAMAGE_DOUBLE_UNTIL", 0) >= round_num:
        return base * 2
    return base
```

**Tests:**
```python
def test_event_furia_total_0():
    """Total 0: dobla daño del Rey por 2 rondas"""

def test_event_furia_total_1_4():
    """Total 1-4: Rey se mueve al piso del jugador"""

def test_event_furia_total_5_plus():
    """Total 5+: Rey aturdido 1 ronda"""
```

**Estimación:** 1 hora

---

## FASE 3: ESTADOS CANÓNICOS

**Estimación Total:** 3 horas

---

### 3.1 Estado: Sangrado 🟢

**Duración:** 2 rondas

**Efecto:** Al final de cada ronda, pierdes 1 cordura.

**Implementación:**
```python
# En transition.py - KING_ENDROUND, después de tick de estados
for pid, p in s.players.items():
    if any(st.status_id == "SANGRADO" for st in p.statuses):
        p.sanity -= 1
```

**Estimación:** 20 minutos

---

### 3.2 Estado: Maldito 🟡

**Duración:** 2 rondas

**Efecto:** Al final de ronda, todas las demás Pobres Almas en el piso pierden 1 cordura.

**Implementación:**
```python
def _apply_maldito_effect(s: GameState) -> None:
    from engine.board import floor_of
    for pid, p in s.players.items():
        if any(st.status_id == "MALDITO" for st in p.statuses):
            player_floor = floor_of(p.room)
            for other_pid, other in s.players.items():
                if other_pid != pid and floor_of(other.room) == player_floor:
                    other.sanity -= 1
```

**Estimación:** 30 minutos

---

### 3.3 Estado: Paranoia 🟡

**Duración:** 2 rondas

**Efecto:** No puede estar en misma habitación/pasillo que otra Pobre Alma.

**Implementación:**
```python
# En legality.py - MOVE
def _check_paranoia_move(s: GameState, pid: PlayerId, to_room: RoomId) -> bool:
    """Retorna False si el movimiento viola Paranoia."""
    p = s.players[pid]
    if any(st.status_id == "PARANOIA" for st in p.statuses):
        # No puede entrar a habitación con otros jugadores
        for other_pid, other in s.players.items():
            if other_pid != pid and other.room == to_room:
                return False

    # Otros no pueden entrar donde está alguien con Paranoia
    for other_pid, other in s.players.items():
        if other_pid != pid and other.room == to_room:
            if any(st.status_id == "PARANOIA" for st in other.statuses):
                return False

    return True
```

**Estimación:** 45 minutos

---

### 3.4 Estado: Sanidad 🟢

**Duración:** 2 rondas

**Efecto:**
- Recupera 1 cordura al final de cada turno
- Puede destruirse para eliminar todos los demás estados

**Implementación:**
```python
# En transition.py - fin de turno de jugador
for pid, p in s.players.items():
    if any(st.status_id == "SANIDAD" for st in p.statuses):
        p.sanity = min(p.sanity + 1, p.sanity_max or p.sanity + 1)

# Acción USE_SANIDAD (destruir para limpiar estados)
def _use_sanidad_cleanse(s: GameState, pid: PlayerId) -> None:
    p = s.players[pid]
    # Remover SANIDAD
    p.statuses = [st for st in p.statuses if st.status_id != "SANIDAD"]
    # Remover todos los demás estados
    p.statuses = []
```

**Estimación:** 30 minutos

---

### 3.5 Estado: Vanidad 🟢

**Duración:** Permanente

**Efecto:** Siempre que pierdas cordura, pierdes 1 adicional.

**Implementación:**
```python
# En cualquier función que aplique pérdida de cordura
def apply_sanity_loss(p: PlayerState, amount: int) -> None:
    """Aplica pérdida de cordura considerando Vanidad."""
    actual_loss = amount
    if any(st.status_id == "VANIDAD" for st in p.statuses):
        actual_loss += 1
    p.sanity -= actual_loss
```

**Estimación:** 30 minutos

---

### 3.6 Estado: ILLUMINATED (Completar implementación) 🟡

**Estado actual:** Tests existen pero NO otorga +1 acción.

**Corrección necesaria:**

```python
# En transition.py - _start_new_round() o inicio de turno
def _calculate_actions_for_turn(s: GameState, pid: PlayerId, cfg: Config) -> int:
    """Calcula acciones disponibles para el turno."""
    from engine.board import floor_of
    p = s.players[pid]
    base_actions = 2

    # Reducción por -5
    if p.at_minus5:
        base_actions = 1

    # Reducción por efecto d6=3 del Rey
    if s.limited_action_floor_next == floor_of(p.room):
        base_actions = 1

    # BONUS por ILLUMINATED
    if any(st.status_id == "ILLUMINATED" for st in p.statuses):
        base_actions += 1

    return base_actions
```

**Estimación:** 30 minutos

---

## FASE 4: OBJETOS Y TESOROS

**Estimación Total:** 3 horas

---

### 4.1 Objetos Básicos

**Ver Fase 0.3** para implementación de:
- Vial (+2 cordura)
- Brújula (mueve al pasillo)
- Objeto Contundente (aturde monstruo)

**Estimación:** Incluida en Fase 0 (2 horas)

---

### 4.2 Tesoro: Llavero 🟡

**Efecto:** +1 capacidad llaves, +1 cordura máxima

**Requiere:** Agregar `keys_capacity` a PlayerState

**Implementación:**
```python
# engine/state.py - agregar a PlayerState
keys_capacity: int = 1  # Default: 1 llave por jugador

# engine/objects.py
def _apply_llavero(s: GameState, pid: PlayerId) -> None:
    """
    Llavero (Tesoro): +1 capacidad de llaves, +1 cordura máxima.
    No consumible (permanente mientras lo tengas).
    """
    p = s.players[pid]
    p.keys_capacity += 1
    p.sanity_max = (p.sanity_max or 5) + 1
```

**Estimación:** 30 minutos

---

### 4.3 Tesoro: Escaleras 🔴

**Efecto:** 3 usos, coloca escalera temporal

**Requiere:** Sistema de escaleras temporales

**Implementación:**
```python
def _use_treasure_stairs(s: GameState, pid: PlayerId, cfg: Config) -> None:
    """
    Escaleras (Tesoro): 3 usos. Coloca escalera temporal en habitación actual.
    Dura hasta fin de ronda.
    """
    p = s.players[pid]
    # Registrar escalera temporal
    s.flags[f"TEMP_STAIRS_{p.room}"] = s.round  # Válida solo esta ronda

    # Decrementar usos
    uses_key = f"TREASURE_STAIRS_USES_{pid}"
    current_uses = s.flags.get(uses_key, 3)
    s.flags[uses_key] = current_uses - 1
    if s.flags[uses_key] <= 0:
        p.objects.remove("TREASURE_STAIRS")
```

**Estimación:** 30 minutos

---

## FASE 5: HABITACIONES ESPECIALES PENDIENTES

**Estimación Total:** 2 horas

---

### 5.1 Salón de Belleza 🟡

**Prioridad:** MEDIA

**Regla canon:**
- Mientras estés ahí, pérdida de cordura = 0
- 2 primeros usos: gratis (solo 1 acción)
- 3er uso: Sella habitación + otorga estado Vanidad

**Dependencias:**
- Estado VANIDAD (Fase 3)
- `room_sealed` flag

**Implementación:**
```python
# En legality.py
def is_room_sealed(s: GameState, room: RoomId) -> bool:
    return s.flags.get(f"SEALED_{room}", False)

# En transition.py - MOVE
if is_room_sealed(s, to_room):
    return s  # No se puede entrar/salir

# Acción USE_SALON_BELLEZA
def _use_salon_belleza(s: GameState, pid: PlayerId, cfg: Config) -> None:
    from engine.effects.event_utils import add_status
    p = s.players[pid]
    uses_key = f"SALON_USES_{p.room}"
    current_uses = s.flags.get(uses_key, 0) + 1
    s.flags[uses_key] = current_uses

    if current_uses >= 3:
        # Sellar habitación
        s.flags[f"SEALED_{p.room}"] = True
        # Otorgar Vanidad
        add_status(p, "VANIDAD", duration=999)  # Permanente
```

**Estimación:** 1 hora

---

### 5.2 Taberna 🟡

**Prioridad:** MEDIA

**Regla canon:**
- Penaliza exploración múltiple
- Si revelas primera carta de 2 habitaciones distintas en mismo turno: -1 cordura

**Dependencias:**
- Tracking de `first_reveal_this_turn` por jugador

**Implementación:**
```python
# En transition.py - _reveal_one() o después
def _track_first_reveal(s: GameState, pid: PlayerId, room: RoomId) -> None:
    """Trackea habitaciones donde el jugador reveló primera carta este turno."""
    key = f"FIRST_REVEALS_{pid}_ROUND_{s.round}"
    if key not in s.flags:
        s.flags[key] = []

    if room not in s.flags[key]:
        s.flags[key].append(room)

        # Si es la 2ª habitación distinta y TABERNA está activa
        if len(s.flags[key]) >= 2 and s.flags.get("TABERNA_ACTIVE", False):
            s.players[pid].sanity -= 1
```

**Estimación:** 45 minutos

---

## FASE 6: ANÁLISIS Y TRACKING RNG

**Estimación Total:** 2.5 horas

---

### 6.1 Tracking Completo de Elementos Aleatorios

**Elementos a Trackear:**

1. **d6 del Rey** (ya implementado) ✅
2. **d4 Manifestación Rey** (ruleta pisos) ⏳
3. **d4 Escaleras** (3 tiradas por fin de ronda) ⏳
4. **Shuffles de Mazos** (efecto d6=1) ⏳
5. **Orden de Setup Inicial** (distribución de cartas) ⏳
6. **D6 de Eventos** (Sistema Total) ⏳

**Archivo:** `engine/rng.py`

**Implementación:**
```python
from dataclasses import dataclass, field
from typing import List, Tuple, Any
import random


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

    def __post_init__(self):
        if self._r is None:
            self._r = random.Random(self.seed)
        if self.log is None:
            self.log = []

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

    def sample(self, population, k):
        """Sample con tracking"""
        result = self._r.sample(population, k)
        self.log.append(("sample", (len(population), k, result)))
        return result
```

**Estimación:** 45 minutos

---

### 6.2 Herramienta de Análisis RNG

**Archivo NUEVO:** `tools/analyze_rng_complete.py`

**Funcionalidades:**
- Distribución de d6 y d4
- Chi-square test para verificar aleatoriedad
- Análisis de patrones
- Comparación con distribución teórica

```python
"""
Análisis estadístico completo de RNG.

Usa:
    python tools/analyze_rng_complete.py runs/.../seed_001.jsonl

Output:
    - Distribución de d6 y d4
    - Chi-square test
    - Detección de patrones
    - Comparación con teórico
"""

import json
from pathlib import Path
import sys
from collections import Counter
from scipy.stats import chisquare


def analyze_rng(jsonl_path: str):
    """Analiza el RNG completo de una partida"""

    d6_rolls = []
    d4_rolls = []
    shuffle_count = 0

    with open(jsonl_path, 'r') as f:
        for line in f:
            rec = json.loads(line)
            if 'rng_stats' in rec:
                stats = rec['rng_stats']
                d6_rolls.extend(stats.get('d6_history', []))
                d4_rolls.extend(stats.get('d4_history', []))
                shuffle_count = max(shuffle_count, stats.get('shuffle_count', 0))

    # Análisis d6
    d6_dist = Counter(d6_rolls)
    d6_expected = len(d6_rolls) / 6
    d6_chi2, d6_p = chisquare([d6_dist.get(i, 0) for i in range(1, 7)],
                              f_exp=[d6_expected] * 6)

    # Análisis d4
    d4_dist = Counter(d4_rolls)
    d4_expected = len(d4_rolls) / 4
    d4_chi2, d4_p = chisquare([d4_dist.get(i, 0) for i in range(1, 5)],
                              f_exp=[d4_expected] * 4)

    report = {
        "file": jsonl_path,
        "d6": {
            "total_rolls": len(d6_rolls),
            "distribution": dict(d6_dist),
            "chi_square": d6_chi2,
            "p_value": d6_p,
            "is_random": d6_p > 0.05  # Si p > 0.05, no rechazamos H0 (es aleatorio)
        },
        "d4": {
            "total_rolls": len(d4_rolls),
            "distribution": dict(d4_dist),
            "chi_square": d4_chi2,
            "p_value": d4_p,
            "is_random": d4_p > 0.05
        },
        "shuffles": shuffle_count
    }

    # Guardar reporte
    output_path = Path(jsonl_path).with_suffix('.rng_analysis.json')
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"📊 Análisis RNG: {output_path}")
    print(f"  d6: {len(d6_rolls)} rolls, p-value={d6_p:.3f}, aleatorio={report['d6']['is_random']}")
    print(f"  d4: {len(d4_rolls)} rolls, p-value={d4_p:.3f}, aleatorio={report['d4']['is_random']}")
    print(f"  Shuffles: {shuffle_count}")

    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/analyze_rng_complete.py <jsonl_file>")
        sys.exit(1)

    analyze_rng(sys.argv[1])
```

**Estimación:** 1 hora

---

## FASE 7: SISTEMA DE GUARDADO VERSIONADO

**Estimación Total:** 45 minutos

**Archivo:** `tools/run_versioned.py`

**Funcionalidad:**
- Guardar runs en estructura versionada por commit
- Generar metadata.json por sesión
- Organizar por timestamp

**Estructura de carpetas:**
```
runs/
└── v{commit_hash}/
    ├── analysis/
    │   ├── {timestamp}_seed_001_analysis.json
    │   ├── {timestamp}_seed_002_analysis.json
    │   └── {timestamp}_session_aggregate.json
    └── {timestamp}/
        ├── metadata.json
        ├── seed_001.jsonl
        ├── seed_002.jsonl
        └── seed_003.jsonl
```

**Implementación:**
```python
"""
Runner con guardado versionado.

Uso:
    python tools/run_versioned.py --seeds 1 2 3 --max-steps 500

Output:
    runs/v{commit}/{timestamp}/seed_XXX.jsonl
    runs/v{commit}/{timestamp}/metadata.json
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime
import sys


def get_git_commit():
    """Obtiene hash corto del commit actual"""
    result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                          capture_output=True, text=True)
    return result.stdout.strip()


def run_versioned(seeds, max_steps=500):
    """Ejecuta simulación con guardado versionado"""
    commit = get_git_commit()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Crear estructura de carpetas
    base_dir = Path("runs") / f"v{commit}" / timestamp
    base_dir.mkdir(parents=True, exist_ok=True)

    analysis_dir = Path("runs") / f"v{commit}" / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    # Metadata
    metadata = {
        "commit": commit,
        "timestamp": timestamp,
        "seeds": seeds,
        "max_steps": max_steps,
        "config": "default"
    }

    with open(base_dir / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"🎯 Sesión: v{commit}/{timestamp}")
    print(f"🎲 Seeds: {seeds}")
    print(f"📁 Output: {base_dir}\n")

    # Ejecutar para cada seed
    for seed in seeds:
        output_file = base_dir / f"seed_{seed:03d}.jsonl"
        print(f"🏃 Ejecutando seed {seed}...")

        # Aquí llamarías a tu simulador
        # Por ahora, placeholder:
        # run_simulation(seed, output_file, max_steps)

    print(f"\n✅ Sesión completada: {base_dir}")
    return base_dir


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', nargs='+', type=int, required=True)
    parser.add_argument('--max-steps', type=int, default=500)

    args = parser.parse_args()
    run_versioned(args.seeds, args.max_steps)
```

**Estimación:** 45 minutos

---

## FASE 8: OPTIMIZACIÓN PARA LLM

**Estimación Total:** 1 hora

**Prerequisito:** Fase 6 (análisis comprehensivo)

**Archivo NUEVO:** `tools/export_for_llm.py`

**Funcionalidad:**
- Genera narrativa legible del juego
- Identifica eventos clave automáticamente
- Crea timeline comprimido
- Insights automáticos

**Formato de salida:**
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

**Implementación:** (Ver CONSOLIDATED líneas 1281-1466 para código completo)

**Estimación:** 1 hora

---

## RESUMEN DE ESTIMACIONES

| Fase | Descripción | Tiempo Estimado | Estado |
|------|-------------|-----------------|--------|
| **FASE 0** | Sistema Base Requerido (CRÍTICO) | 5-6 horas | ❌ Pendiente |
| 0.1 | Sistema Resolución Eventos | 2-3 horas | ❌ |
| 0.2 | Funciones Utilidad | 1 hora | ❌ |
| 0.3 | Sistema Objetos | 2 horas | ❌ |
| **FASE 1** | Hooks Básicos | 45 min | ✅ **COMPLETADO** |
| 1.1 | Destrucción Armería | 25 min | ✅ |
| 1.2 | Reset Peek | 10 min | ✅ |
| **FASE 1.5** | Habitaciones Especiales (P1) | 3 horas | ❌ Pendiente |
| 1.5.0 | Modelo de Datos | 15 min | ❌ |
| 1.5.1 | Sorteo y Asignación | 60 min | ❌ |
| 1.5.2 | Hook Revelación | 30 min | ❌ |
| 1.5.3 | Hook Destrucción | 20 min | ❌ |
| 1.5.4 | Cámara Letal | 45 min | ❌ |
| **FASE 2** | Eventos Existentes (7 eventos) | 3.5-4 horas | ❌ Pendiente |
| 2.1 | Reflejo de Amarillo | 15 min | ❌ |
| 2.2 | Espejo de Amarillo | 15 min | ❌ |
| 2.3 | Hay un Cadáver | 45 min | ❌ |
| 2.4 | Un Diván de Amarillo | 30 min | ❌ |
| 2.5 | Cambia Caras | 30 min | ❌ |
| 2.6 | Una Comida Servida | 45 min | ❌ |
| 2.7 | La Furia de Amarillo | 1 hora | ❌ |
| **FASE 3** | Estados Canónicos | 3 horas | ❌ Pendiente |
| 3.1 | Sangrado | 20 min | ❌ |
| 3.2 | Maldito | 30 min | ❌ |
| 3.3 | Paranoia | 45 min | ❌ |
| 3.4 | Sanidad | 30 min | ❌ |
| 3.5 | Vanidad | 30 min | ❌ |
| 3.6 | ILLUMINATED (completar) | 30 min | ❌ |
| **FASE 4** | Objetos y Tesoros | 1 hora | ❌ Pendiente |
| 4.2 | Llavero | 30 min | ❌ |
| 4.3 | Escaleras (tesoro) | 30 min | ❌ |
| **FASE 5** | Habitaciones Pendientes | 2 horas | ❌ Pendiente |
| 5.1 | Salón de Belleza | 1 hora | ❌ |
| 5.2 | Taberna | 45 min | ❌ |
| **FASE 6** | Análisis y Tracking RNG | 2.5 horas | ❌ Pendiente |
| 6.1 | Tracking RNG Completo | 45 min | ❌ |
| 6.2 | Herramienta Análisis RNG | 1 hora | ❌ |
| **FASE 7** | Guardado Versionado | 45 min | ❌ Pendiente |
| **FASE 8** | Optimización LLM | 1 hora | ❌ Pendiente |
| **TOTAL** | | **~22-24 horas** | |

---

## ORDEN DE IMPLEMENTACIÓN

### 🔴 PRIORIDAD CRÍTICA (BLOQUEAN OTRAS FASES)

```
FASE 0: Sistema Base Requerido
├── 0.1: Sistema de Resolución de Eventos (2-3h)
├── 0.2: Funciones de Utilidad (1h)
└── 0.3: Sistema de Objetos (2h)
```

**⚠️ IMPORTANTE:** La Fase 0 es prerequisito para Fase 2 (Eventos Existentes).

---

### 🟢 ORDEN RECOMENDADO COMPLETO

```
✅ FASE 1: Hooks Básicos [COMPLETADO]
├── 1.1: Destrucción Armería ✅
└── 1.2: Reset Peek ✅

🔴 FASE 0: Sistema Base Requerido [5-6h]
├── 0.1: Sistema Resolución Eventos
├── 0.2: Funciones Utilidad
└── 0.3: Sistema Objetos

🟡 FASE 1.5: Habitaciones Especiales (P1) [3h]
├── 1.5.0: Modelo de Datos
├── 1.5.1: Sorteo y Asignación
├── 1.5.2: Hook Revelación
├── 1.5.3: Hook Destrucción
└── 1.5.4: Cámara Letal

🟡 FASE 2: Eventos Existentes [3.5-4h]
├── EVT-01: Reflejo de Amarillo
├── EVT-02: Espejo de Amarillo
├── EVT-03: Hay un Cadáver
├── EVT-04: Un Diván de Amarillo
├── EVT-05: Cambia Caras
├── EVT-06: Una Comida Servida
└── EVT-07: La Furia de Amarillo

🟡 FASE 3: Estados Canónicos [3h]
├── Sangrado
├── Maldito
├── Paranoia
├── Sanidad
├── Vanidad
└── ILLUMINATED (completar)

🟢 FASE 4: Objetos y Tesoros [1h]
├── Llavero
└── Escaleras

🟢 FASE 5: Habitaciones Pendientes [2h]
├── Salón de Belleza
└── Taberna

🟢 FASE 6: Análisis y Tracking RNG [2.5h]
├── Tracking RNG Completo
└── Herramienta Análisis

🟢 FASE 7: Guardado Versionado [45min]

🟢 FASE 8: Optimización LLM [1h]
```

---

## CÓMO REANUDAR EL TRABAJO

**Si la sesión se interrumpe:**

1. **Leer este documento** desde el inicio
2. **Verificar qué fase estabas implementando:**
   - Revisar últimos commits: `git log --oneline -5`
   - Ver archivos modificados: `git status`
   - Consultar tabla de Estado en sección [Resumen de Estimaciones](#resumen-de-estimaciones)
3. **Consultar la sección de la fase correspondiente**
4. **Continuar desde el último checkpoint**

**Cada fase es autocontenida** (excepto dependencias explícitas como Fase 0 → Fase 2).

---

## PROPUESTAS NO APROBADAS

> **⚠️ IMPORTANTE:** El documento CONSOLIDATED_IMPLEMENTATION_PRIORITY.md Parte 6 contiene propuestas NO aprobadas.

**NO implementar hasta que sean playtested y aprobadas:**
- Eventos propuestos (EVT-01 a EVT-10 propuestos)
- Objetos propuestos (OBJ-01 a OBJ-10 propuestos)
- Habitaciones propuestas (ROOM-01 a ROOM-10)
- Roles propuestos (ROL-01 a ROL-10)
- Tesoros propuestos (TRE-01 a TRE-10)

**Ver:** CONSOLIDATED_IMPLEMENTATION_PRIORITY.md líneas 1046-1209 para lista completa.

---

## REFERENCIAS

### Documentos Base

- **Este documento**: Plan maestro unificado de implementación
- **CONSOLIDATED_IMPLEMENTATION_PRIORITY.md**: Referencia técnica detallada con código de implementación completo

### Referencias Cruzadas

| Este Documento | CONSOLIDATED | Descripción |
|----------------|--------------|-------------|
| Fase 0 | Parte 1 | Sistema Base Requerido |
| Fase 2 | Parte 2 | Eventos Existentes (EVT-01 a EVT-07) |
| Fase 3 | Parte 5 | Estados Canónicos |
| Fase 4 | Parte 3 | Objetos y Tesoros |
| Fase 1.5, 5 | Parte 4 | Habitaciones Especiales |
| Propuestas | Parte 6 | ⚠️ NO aprobadas (ignorar hasta aprobación) |

### Convenciones

| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado |
| ❌ | No implementado |
| ⚠️ | Parcialmente implementado |
| 🔴 | Prioridad crítica / Tarea compleja |
| 🟡 | Prioridad media / Tarea moderada |
| 🟢 | Prioridad baja / Tarea simple |

### Palabras Clave del Sistema

| Término | Definición |
|---------|------------|
| **Total** | `d6 + cordura_actual`, mínimo 0 |
| **Remover estado** | Eliminar completamente un StatusInstance |
| **Aturdir N rondas** | Monstruo no actúa por N rondas |
| **Sellar habitación** | Nadie entra ni sale |
| **Acción gratuita** | No consume acciones del turno |
| **Consumible** | Se destruye al usar |
| **Permanente** | Dura hasta fin de partida |
| **SOULbound** | No se puede intercambiar/vender/destruir |

---

**FIN DEL DOCUMENTO**

*Última actualización: 19 Enero 2026*
*Versión Unificada - Integra eventos, objetos, estados y herramientas*

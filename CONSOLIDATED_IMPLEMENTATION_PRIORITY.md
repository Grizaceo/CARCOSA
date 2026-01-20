# DOCUMENTO CONSOLIDADO DE IMPLEMENTACIÓN CARCOSA
## Priorización para Motor Determinista + Simulador
**Versión:** 1.0 | **Fecha:** 19 Enero 2026 | **Basado en:** Repositorio v0.2, Libro Técnico v0.2.3

---

## ÍNDICE

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Estado Actual del Engine](#2-estado-actual-del-engine)
3. [PARTE 1: Sistema Base Requerido](#parte-1-sistema-base-requerido)
4. [PARTE 2: Eventos Existentes (Físico → Código)](#parte-2-eventos-existentes-físico--código)
5. [PARTE 3: Objetos y Tesoros Existentes](#parte-3-objetos-y-tesoros-existentes)
6. [PARTE 4: Habitaciones Especiales Pendientes](#parte-4-habitaciones-especiales-pendientes)
7. [PARTE 5: Estados Canónicos Pendientes](#parte-5-estados-canónicos-pendientes)
8. [PARTE 6: Propuestas No Aprobadas](#parte-6-propuestas-no-aprobadas)
9. [Apéndices](#apéndices)

---

## 1. RESUMEN EJECUTIVO

### Objetivo
Este documento prioriza la implementación de mecánicas del juego físico CARCOSA al motor digital, ordenando por dependencias técnicas y facilidad de implementación.

### Convenciones

| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado en engine actual |
| ⚠️ | Parcialmente implementado |
| ❌ | No implementado |
| 🔒 | Requiere subsistema previo |
| 🟢 | Implementable de inmediato |
| 🟡 | Requiere 1-2 días de trabajo |
| 🔴 | Requiere refactor mayor |

### Regla de Oro
> **PROHIBIDO inventar reglas.** Si falta especificación: declarar SUPUESTO, justificarlo y mantenerlo determinista.

---

## 2. ESTADO ACTUAL DEL ENGINE

### 2.1 Implementado ✅

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
├── legality.py     → Acciones legales por fase y condición
├── board.py        → Grafo de nodos, rotación sushi, escaleras
└── config.py       → KEYS_TOTAL=6, S_LOSS=-5, etc.
```

### 2.2 NO Implementado ❌

| Subsistema | Descripción |
|------------|-------------|
| **Resolución de EVENTOS** | `_resolve_card_minimal()` ignora `EVENT:*` |
| **Sistema Total** | `Total = d6 + cordura_actual` no existe |
| **Efectos de Objetos** | Brújula, Vial, Contundente son strings sin lógica |
| **Estados Canónicos** | Sangrado, Maldito, Paranoia, Sanidad, Vanidad |
| **Habitaciones** | Cámara Letal, Taberna, Salón de Belleza |

### 2.3 Parcialmente Implementado ⚠️

| Elemento | Estado | Falta |
|----------|--------|-------|
| ILLUMINATED | Tests existen | No otorga +1 acción realmente |
| TRAPPED | ESCAPE_TRAPPED funciona | No se aplica desde cartas |

---

## PARTE 1: SISTEMA BASE REQUERIDO

> **CRÍTICO:** Estos subsistemas deben implementarse ANTES de los eventos existentes.

### P1.1 Sistema de Resolución de Eventos 🔴

**Prioridad:** CRÍTICA (bloquea 7 eventos existentes)

**Archivo:** `engine/transition.py`

**Ubicación:** Función `_resolve_card_minimal()` (~línea 129)

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
    deck = active_deck_for_room(s, p.room)
    if deck is not None:
        deck.cards.append(CardId(f"EVENT:{event_id}"))
```

**Tests requeridos:**
```python
# tests/test_event_resolution.py
def test_event_card_triggers_resolution():
    """EVENT:X en mazo debe llamar a _resolve_event()"""

def test_event_returns_to_bottom():
    """Evento resuelto vuelve al fondo del mazo"""

def test_total_calculation():
    """Total = d6 + cordura, clamp mínimo 0"""
```

**Estimación:** 2-3 horas

---

### P1.2 Sistema de Total (d6 + cordura) 🟡

**Prioridad:** ALTA (usado por 5 de 7 eventos existentes)

**Implementación:** Incluida en P1.1

**Fórmula canónica:**
```python
def calculate_total(rng: RNG, sanity: int) -> int:
    """
    Total = d6 + cordura_actual
    Si Total < 0, se considera 0 (clamp)
    """
    d6 = rng.randint(1, 6)
    return max(0, d6 + sanity)
```

---

### P1.3 Funciones de Utilidad para Eventos 🟡

**Prioridad:** ALTA (reutilizadas por múltiples eventos)

```python
# engine/effects/event_utils.py

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

**Estimación:** 1 hora

---

### P1.4 Sistema de Objetos con Efectos 🟡

**Prioridad:** MEDIA (necesario para objetos existentes)

**Archivo:** `engine/objects.py` (NUEVO)

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

**Estimación:** 2 horas

---

## PARTE 2: EVENTOS EXISTENTES (Físico → Código)

> **Orden:** Por dependencias técnicas (menor a mayor complejidad)

---

### EVT-01: El Reflejo de Amarillo 🟢

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
def test_event_reflejo_amarillo():
    """Reflejo de Amarillo aplica -2 cordura"""
    s = setup_state_with_event("REFLEJO_AMARILLO")
    p1 = s.players[PlayerId("P1")]
    initial_sanity = p1.sanity
    
    s_new = trigger_event(s, "P1", "REFLEJO_AMARILLO")
    
    assert s_new.players[PlayerId("P1")].sanity == initial_sanity - 2
```

**Estimación:** 15 minutos

---

### EVT-02: Espejo de Amarillo 🟢

**Prioridad:** 2 (simple, sin dependencias)

**Regla física:** `Invierte la cordura del jugador (× -1)`

**Dependencias:** `invert_sanity()` de P1.3

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
    s_new = trigger_event(s, "P1", "ESPEJO_AMARILLO")
    assert s_new.players[PlayerId("P1")].sanity == -3

def test_event_espejo_amarillo_negative():
    """Espejo invierte cordura negativa a positiva"""
    s = setup_state_with_sanity(-2)
    s_new = trigger_event(s, "P1", "ESPEJO_AMARILLO")
    assert s_new.players[PlayerId("P1")].sanity == 2
```

**Estimación:** 15 minutos

---

### EVT-03: Hay un Cadáver 🟡

**Prioridad:** 3 (requiere Total + skip turn + obtener objeto)

**Regla física:**
- `Total 0-2`: Pierdes un turno
- `Total 3-4`: -1 cordura
- `Total 5+`: Obtienes 1 objeto contundente

**Dependencias:**
- P1.1 Sistema de Total ✅
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
        # Obtener objeto contundente (si cabe en inventario)
        # SUPUESTO: Inventario ilimitado por ahora
        p.objects.append("BLUNT")
```

**Código adicional en `transition.py`:**
```python
# En _advance_turn_or_king() o inicio de turno
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
    # Forzar RNG para total <= 2

def test_event_hay_cadaver_total_3_4():
    """Total 3-4: -1 cordura"""

def test_event_hay_cadaver_total_5_plus():
    """Total 5+: obtiene contundente"""
```

**Estimación:** 45 minutos

---

### EVT-04: Un Diván de Amarillo 🟡

**Prioridad:** 4 (requiere Total + remover estados + estado Sanidad)

**Regla física:**
- `Total 0-3`: Quita efectos activos
- `Total 4-7`: Quita efectos y +1 cordura
- `Total 8+`: Obtienes estado Sanidad

**Dependencias:**
- P1.1 Sistema de Total ✅
- `remove_all_statuses()` de P1.3
- Estado SANIDAD (ver Parte 5)

**Implementación:**
```python
def _event_divan_amarillo(s: GameState, pid: PlayerId, total: int, cfg: Config) -> None:
    """
    Un diván de Amarillo: según Total.
    0-3: Quita todos los estados
    4-7: Quita estados + 1 cordura
    8+: Obtiene estado Sanidad
    """
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

### EVT-05: Cambia Caras 🟡

**Prioridad:** 5 (requiere Total + swap posición + orden de turno)

**Regla física:**
- `Total 0-3`: Intercambias posición con el alma a tu derecha
- `Total 4+`: Intercambias posición con el alma a tu izquierda

**Dependencias:**
- P1.1 Sistema de Total ✅
- `swap_positions()` de P1.3
- `get_player_by_turn_offset()` de P1.3

**Implementación:**
```python
def _event_cambia_caras(s: GameState, pid: PlayerId, total: int, cfg: Config) -> None:
    """
    Cambia caras: según Total.
    0-3: Swap con jugador a la derecha (orden turno +1)
    4+: Swap con jugador a la izquierda (orden turno -1)
    """
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

### EVT-06: Una Comida Servida 🟡

**Prioridad:** 6 (requiere Total + mover otro jugador)

**Regla física:**
- `Total 0`: -3 cordura
- `Total 1-2`: Ganas estado Envenenado → **ELIMINADO** → Sangrado
- `Total 3-6`: +2 cordura
- `Total 7+`: Trae otra alma a tu habitación y ambos +2 cordura

**Dependencias:**
- P1.1 Sistema de Total ✅
- `move_player_to_room()` de P1.3
- Estado SANGRADO (ver Parte 5)

**NOTA:** Se reemplaza Envenenado por Sangrado según instrucción.

**Implementación:**
```python
def _event_comida_servida(s: GameState, pid: PlayerId, total: int, cfg: Config, rng: RNG) -> None:
    """
    Una comida servida: según Total.
    0: -3 cordura
    1-2: Estado Sangrado (reemplaza Envenenado)
    3-6: +2 cordura
    7+: Trae otro jugador a tu habitación, ambos +2 cordura
    """
    p = s.players[pid]
    
    if total == 0:
        p.sanity -= 3
    elif total <= 2:
        add_status(p, "SANGRADO", duration=2)
    elif total <= 6:
        p.sanity = min(p.sanity + 2, p.sanity_max or p.sanity + 2)
    else:  # total >= 7
        # Traer otro jugador (el más cercano o aleatorio)
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

### EVT-07: La Furia de Amarillo 🔴

**Prioridad:** 7 (más complejo, requiere modificadores del Rey)

**Regla física:**
- `Total 0`: Dobla el efecto del Rey (**ADVERTENCIA: permanente rompe balance**)
- `Total 1-4`: El Rey se mueve al piso del alma activa
- `Total 5+`: Aturde al Rey 1 ronda

**Dependencias:**
- P1.1 Sistema de Total ✅
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
    
    ADVERTENCIA: El canon dice "permanentemente" pero se limita a 2 rondas
    para evitar romper balance.
    """
    p = s.players[pid]
    
    if total == 0:
        # SUPUESTO: Limitado a 2 rondas
        s.flags["KING_DAMAGE_DOUBLE_UNTIL"] = s.round + 2
    elif total <= 4:
        from engine.board import floor_of
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

## PARTE 3: OBJETOS Y TESOROS EXISTENTES

> **Canon:** Manual base + Libro Técnico v0.2.3

### 3.1 Objetos Existentes (por facilidad de implementación)

| # | Objeto | Efecto | Dependencias | Dificultad |
|---|--------|--------|--------------|------------|
| 1 | **Vial** | +2 cordura. Acción gratuita. | Ninguna | 🟢 |
| 2 | **Brújula** | Mueve al pasillo del piso actual. Acción gratuita. | `corridor_id()` | 🟢 |
| 3 | **Objeto Contundente** | Aturde monstruo 2 rondas. | Sistema de stun | 🟡 |

#### OBJ-01: Vial 🟢

```python
# En engine/objects.py
def _use_vial(s: GameState, pid: PlayerId, cfg: Config) -> None:
    """Vial: Recupera 2 de cordura. Acción gratuita. Consumible."""
    p = s.players[pid]
    p.sanity = min(p.sanity + 2, p.sanity_max or p.sanity + 2)
```

#### OBJ-02: Brújula 🟢

```python
def _use_compass(s: GameState, pid: PlayerId, cfg: Config) -> None:
    """Brújula: Mueve al pasillo del piso actual. Acción gratuita. Consumible."""
    from engine.board import floor_of, corridor_id
    p = s.players[pid]
    floor = floor_of(p.room)
    p.room = corridor_id(floor)
```

#### OBJ-03: Objeto Contundente 🟡

```python
def _use_blunt(s: GameState, pid: PlayerId, cfg: Config) -> None:
    """
    Objeto Contundente: Aturde monstruo en habitación por 2 rondas.
    Consumible. Requiere monstruo presente.
    """
    p = s.players[pid]
    for monster in s.monsters:
        if monster.room == p.room:
            # Flag de stun hasta ronda X
            s.flags[f"STUN_{monster.monster_id}_UNTIL"] = s.round + 2
            break
```

**Estimación total objetos:** 1 hora

---

### 3.2 Tesoros Existentes

| # | Tesoro | Efecto | Dependencias | Dificultad |
|---|--------|--------|--------------|------------|
| 1 | **Llavero** | +1 capacidad llaves, +1 cordura máxima | `keys_capacity` en PlayerState | 🟡 |
| 2 | **Escaleras (Tesoro)** | 3 usos, coloca escalera temporal | Sistema escaleras temp | 🔴 |

#### TRE-01: Llavero 🟡

**Requiere:** Agregar `keys_capacity` a PlayerState

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

#### TRE-02: Escaleras (Tesoro) 🔴

**Requiere:** Sistema de escaleras temporales

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
    # SUPUESTO: Tesoros con usos se trackean en flags
    uses_key = f"TREASURE_STAIRS_USES_{pid}"
    current_uses = s.flags.get(uses_key, 3)
    s.flags[uses_key] = current_uses - 1
    if s.flags[uses_key] <= 0:
        p.objects.remove("TREASURE_STAIRS")
```

**Estimación total tesoros:** 2 horas

---

## PARTE 4: HABITACIONES ESPECIALES PENDIENTES

### 4.1 Cámara Letal (B3) 🔴

**Prioridad:** ALTA (habilita 7ª llave)

**Regla canon:**
- Ritual (1 acción, máx 1/partida)
- Tirar d6 para distribuir 7 puntos de cordura
- `1-2`: Un jugador sacrifica 7 puntos
- `3-4`: Jugadores sacrifican 3 y 4 (a elección)
- `5-6`: Reparto libre de 7 puntos
- Resultado: Grupo obtiene 1 llave extra

**Dependencias:**
- Sorteo de habitaciones especiales (IMPLEMENTATION_PLAN Fase 1.5)
- `keys_in_ritual_reserve` flag

**Archivos a modificar:**
- `engine/actions.py`: Agregar `USE_CAMARA_LETAL_RITUAL`
- `engine/legality.py`: Condición de 2 jugadores en habitación
- `engine/transition.py`: Lógica del ritual

**Estimación:** 1.5 horas

---

### 4.2 Salón de Belleza 🟡

**Prioridad:** MEDIA

**Regla canon:**
- Mientras estés ahí, pérdida de cordura = 0
- 2 primeros usos: gratis (solo 1 acción)
- 3er uso: Sella habitación + otorga estado Vanidad

**Dependencias:**
- Estado VANIDAD (Parte 5)
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

### 4.3 Taberna 🟡

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

## PARTE 5: ESTADOS CANÓNICOS PENDIENTES

> **NOTA:** Envenenado ha sido ELIMINADO de esta lista.

### 5.1 Estado: Sangrado 🟢

**Duración:** 2 rondas

**Efecto:** Al final de cada ronda, pierdes 1 cordura.

```python
# En transition.py - KING_ENDROUND, después de tick de estados
for pid, p in s.players.items():
    if any(st.status_id == "SANGRADO" for st in p.statuses):
        p.sanity -= 1
```

---

### 5.2 Estado: Maldito 🟡

**Duración:** 2 rondas

**Efecto:** Al final de ronda, todas las demás Pobres Almas en el piso pierden 1 cordura.

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

---

### 5.3 Estado: Paranoia 🟡

**Duración:** 2 rondas

**Efecto:** No puede estar en misma habitación/pasillo que otra Pobre Alma.

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

---

### 5.4 Estado: Sanidad 🟢

**Duración:** 2 rondas

**Efecto:** 
- Recupera 1 cordura al final de cada turno
- Puede destruirse para eliminar todos los demás estados

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

---

### 5.5 Estado: Vanidad 🟢

**Duración:** Permanente

**Efecto:** Siempre que pierdas cordura, pierdes 1 adicional.

```python
# En cualquier función que aplique pérdida de cordura
def apply_sanity_loss(p: PlayerState, amount: int) -> None:
    """Aplica pérdida de cordura considerando Vanidad."""
    actual_loss = amount
    if any(st.status_id == "VANIDAD" for st in p.statuses):
        actual_loss += 1
    p.sanity -= actual_loss
```

---

### 5.6 Estado: ILLUMINATED (Completar implementación) 🟡

**Estado actual:** Tests existen pero NO otorga +1 acción.

**Corrección necesaria:**

```python
# En transition.py - _start_new_round() o inicio de turno
def _calculate_actions_for_turn(s: GameState, pid: PlayerId, cfg: Config) -> int:
    """Calcula acciones disponibles para el turno."""
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

---

## PARTE 6: PROPUESTAS NO APROBADAS

> **IMPORTANTE:** Estas propuestas NO han sido playtested ni aprobadas.
> Ordenadas por facilidad de implementación en el engine actual.

### 6.1 Eventos Propuestos (Tier 1 - Implementables de inmediato)

| # | ID | Nombre | Dependencias | Decisión |
|---|-----|--------|--------------|----------|
| 1 | EVT-10 | La Mirada del Público | Ninguna | ⬜ Pendiente |
| 2 | EVT-03 | Sangre en el Libreto | `remove_status()` | ⬜ Pendiente |
| 3 | EVT-04 | Pasos en el Pasillo | `corridor_id()` | ⬜ Pendiente |

#### PROP-EVT-10: La Mirada del Público 🟢

**Efecto:** Todos en tu piso -1 cordura; tú +2 cordura.

```python
def _event_mirada_publico(s: GameState, pid: PlayerId, cfg: Config) -> None:
    from engine.board import floor_of
    p = s.players[pid]
    player_floor = floor_of(p.room)
    
    for other_pid, other in s.players.items():
        if floor_of(other.room) == player_floor and other_pid != pid:
            other.sanity -= 1
    
    p.sanity = min(p.sanity + 2, p.sanity_max or p.sanity + 2)
```

**Decisión requerida:** ⬜ Aprobar / ⬜ Rechazar / ⬜ Modificar

---

#### PROP-EVT-03: Sangre en el Libreto 🟢

**Efecto:** Elige A) remover 1 estado y -1 cordura, o B) mantener estados y +1 cordura.

**Requiere:** Sistema de elección en eventos (nuevo)

```python
def _event_sangre_libreto(s: GameState, pid: PlayerId, choice: str, cfg: Config) -> None:
    p = s.players[pid]
    
    if choice == "A" and p.statuses:
        # Remover 1 estado (el primero)
        p.statuses.pop(0)
        p.sanity -= 1
    else:  # choice == "B"
        p.sanity = min(p.sanity + 1, p.sanity_max or p.sanity + 1)
```

**Decisión requerida:** ⬜ Aprobar / ⬜ Rechazar / ⬜ Modificar

---

#### PROP-EVT-04: Pasos en el Pasillo 🟢

**Efecto:** Muévete al pasillo (sin acción). Si Total≤2: -2 cordura; si Total≥3: +1 cordura.

```python
def _event_pasos_pasillo(s: GameState, pid: PlayerId, total: int, cfg: Config) -> None:
    from engine.board import floor_of, corridor_id
    p = s.players[pid]
    
    # Mover al pasillo (sin coste de acción)
    p.room = corridor_id(floor_of(p.room))
    
    if total <= 2:
        p.sanity -= 2
    else:
        p.sanity = min(p.sanity + 1, p.sanity_max or p.sanity + 1)
```

**Decisión requerida:** ⬜ Aprobar / ⬜ Rechazar / ⬜ Modificar

---

### 6.2 Eventos Propuestos (Tier 2 - Requieren subsistema menor)

| # | ID | Nombre | Dependencia nueva | Decisión |
|---|-----|--------|-------------------|----------|
| 4 | EVT-05 | Carta Marcada | `peek_deck(n)` | ⬜ Pendiente |
| 5 | EVT-08 | Sombras de Utilería | P1.4 Objetos | ⬜ Pendiente |
| 6 | EVT-06 | Eco del Nombre | `swap_sanity()` | ⬜ Pendiente |
| 7 | EVT-09 | Ensayo Interrumpido | `actions_modifier` | ⬜ Pendiente |

---

### 6.3 Eventos Propuestos (Tier 3 - Requieren subsistema mayor)

| # | ID | Nombre | Dependencia mayor | Decisión |
|---|-----|--------|-------------------|----------|
| 8 | EVT-01 | Contrato de Salida | Sistema consumir llave | ⬜ Pendiente |
| 9 | EVT-02 | Foco de Escena | R-ILLUM-001 completo | ⬜ Pendiente |
| 10 | EVT-07 | Lodo de Carcosa | R-TRAPPED-001 completo | ⬜ Pendiente |

---

### 6.4 Objetos Propuestos (ordenados por facilidad)

| Tier | ID | Nombre | Efecto | Dependencia |
|------|-----|--------|--------|-------------|
| 🟢 | OBJ-10 | Navaja de Utilería | Contundente simple | Ninguna |
| 🟢 | OBJ-08 | Sales Aromáticas | +1 cordura, remover Aturdido | `remove_status()` |
| 🟡 | OBJ-01 | Linterna de Aceite | Ver carta adyacente (3 usos) | `peek_deck()` |
| 🟡 | OBJ-02 | Venda Improvisada | Remover/reducir estado | `remove_status()` |
| 🟡 | OBJ-05 | Cuerda | Movimiento extendido | Ninguna |
| 🟡 | OBJ-07 | Mapa Arrugado | +1 Total (1 uso) | `total_modifier` |
| 🔴 | OBJ-03 | Silbato | Reacción fase Monstruos | Ventana reacción |
| 🔴 | OBJ-04 | Tiza | Interacción Taberna | R-TAVERN-001 |
| 🔴 | OBJ-06 | Candado Oxidado | Proteger llave vs -5 | Hook evento -5 |
| 🔴 | OBJ-09 | Espejo de Bolsillo | Reacción pre-evento | Sistema reacciones |

---

### 6.5 Habitaciones Propuestas (ordenadas por facilidad)

| Tier | ID | Nombre | Efecto | Dependencia |
|------|-----|--------|--------|-------------|
| 🟢 | ROOM-01 | Capilla del Olvido | Remover estado por cordura | `remove_status()` |
| 🟢 | ROOM-09 | Cuarto de Aislamiento | +1 cordura al terminar turno | Hook `on_end_turn` |
| 🟡 | ROOM-02 | Biblioteca de los Ecos | Ver/ordenar 2 cartas | `peek_deck()` |
| 🟡 | ROOM-04 | Enfermería | +2 cordura o remover estado | `remove_status()` |
| 🟡 | ROOM-05 | Galería de Retratos | Swap posición mismo piso | `swap_positions()` |
| 🟡 | ROOM-10 | Sala de Maquinaria | Próxima acción gratis | `next_action_free` |
| 🔴 | ROOM-03 | Sala de Ensayo | Estado Iluminado | R-ILLUM-001 |
| 🔴 | ROOM-06 | Depósito de Escenografía | Objetos con +1 uso | Sistema usos |
| 🔴 | ROOM-07 | Sala de Vestuario | Almacenamiento temporal | Sistema storage |
| 🔴 | ROOM-08 | Observatorio | Elegir ubicación escalera | Override escaleras |

---

### 6.6 Roles Propuestos (ordenados por facilidad)

| Tier | ID | Nombre | Efecto | Dependencia |
|------|-----|--------|--------|-------------|
| 🟢 | ROL-08 | Mártir | Absorber daño de otro | Hook `apply_damage()` |
| 🟡 | ROL-02 | Médico de campaña | Meditar +2 (1/ronda) | `meditate_bonus` |
| 🟡 | ROL-04 | Vigilante | Reducir pérdida otro (fin ronda) | Hook fin ronda |
| 🟡 | ROL-06 | Contramaestre | Primer mov gratis desde pasillo | `first_move_free` |
| 🟡 | ROL-09 | Ilusionista | Swap posición (costo cordura) | `swap_positions()` |
| 🔴 | ROL-01 | Cartógrafo | Ver carta antes de resolver | Hook `on_enter` |
| 🔴 | ROL-03 | Cerrajero | +1 llave + proteger vs -5 | Hook evento -5 |
| 🔴 | ROL-05 | Exorcista | Reacción vs monstruo | Ventana reacción |
| 🔴 | ROL-07 | Archivista | Evento arriba del mazo | `deck.put_on_top()` |
| 🔴 | ROL-10 | Explorador | Reducir penalización Taberna | R-TAVERN-001 |

---

### 6.7 Tesoros Propuestos (ordenados por facilidad)

| Tier | ID | Nombre | Efecto | Dependencia |
|------|-----|--------|--------|-------------|
| 🟢 | TRE-05 | Caja de Música | Transfer cordura entre jugadores | Ninguna |
| 🟢 | TRE-07 | Cadena Teatral | +1 slot de objeto | `inventory_slots` |
| 🟡 | TRE-04 | Diario de la Obra | +1 Total (1/ronda) | `total_modifier` |
| 🟡 | TRE-06 | Llave Hueca | Cuenta como llave, se destruye primero | Hook evento -5 |
| 🟡 | TRE-09 | Mapa de Carcosa | Ver carta cualquier hab | `peek_deck()` |
| 🔴 | TRE-01 | Máscara del Intermedio | Ignorar efecto global Rey | `immune_king` |
| 🔴 | TRE-02 | Reloj de Bolsillo | +1 acción, -1 cordura fin | `actions_modifier` |
| 🔴 | TRE-03 | Amuleto de Salvoconducto | Inmune a Atraer (d6=5) | `immune_attract` |
| 🔴 | TRE-08 | Pluma del Dramaturgo | Cambiar Total 0-2 → 3 | Hook pre-resolución |
| 🔴 | TRE-10 | Sello de Lacre | Bloquear rotación 1 caja | Hook `rotate_boxes()` |

---

## APÉNDICES

### Apéndice A: Orden de Implementación Recomendado

```
FASE 0: Sistema Base (CRÍTICO)
├── P1.1 Sistema de Resolución de Eventos
├── P1.2 Sistema de Total (d6 + cordura)
└── P1.3 Funciones de Utilidad

FASE 1: Eventos Existentes
├── EVT-01 Reflejo de Amarillo
├── EVT-02 Espejo de Amarillo
├── EVT-03 Hay un Cadáver
├── EVT-04 Un Diván de Amarillo
├── EVT-05 Cambia Caras
├── EVT-06 Una Comida Servida
└── EVT-07 La Furia de Amarillo

FASE 2: Objetos y Estados
├── OBJ-01 Vial
├── OBJ-02 Brújula
├── OBJ-03 Objeto Contundente
├── Estados: Sangrado, Maldito, Paranoia, Sanidad, Vanidad
└── Completar ILLUMINATED

FASE 3: Habitaciones Pendientes
├── B3 Cámara Letal
├── Salón de Belleza
└── Taberna

FASE 4: Propuestas (según aprobación)
└── Según decisiones en Parte 6
```

---

### Apéndice B: Checklist de Tests por Feature

```markdown
## Evento: [NOMBRE]
- [ ] Test efecto básico
- [ ] Test con cordura positiva
- [ ] Test con cordura negativa
- [ ] Test con cordura 0
- [ ] Test límites (clamp a -5, clamp a max)
- [ ] Test carta vuelve al fondo del mazo

## Estado: [NOMBRE]
- [ ] Test se aplica correctamente
- [ ] Test duración decrece cada ronda
- [ ] Test se remueve al llegar a 0
- [ ] Test efecto por ronda (si aplica)
- [ ] Test interacción con otros estados

## Objeto: [NOMBRE]
- [ ] Test efecto al usar
- [ ] Test consumo de usos
- [ ] Test no se puede usar sin tenerlo
- [ ] Test en Armería (si aplica)
```

---

### Apéndice C: Palabras Clave del Sistema

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

### Apéndice D: Referencias Cruzadas

| Este documento | Libro Técnico v0.2.3 | IMPLEMENTATION_PLAN |
|----------------|---------------------|---------------------|
| P1.1 Sistema Eventos | §6.1 Resolución | - |
| EVT-01 a EVT-07 | §A.2 Eventos existentes | - |
| Cámara Letal | §11.2 | Fase 1.5 |
| Salón de Belleza | §11.3 | - |
| Taberna | §11.5 | - |
| ILLUMINATED | §9.3 | B1 |
| TRAPPED | §9.2 | Tests existentes |

---

**FIN DEL DOCUMENTO**

*Generado: 19 Enero 2026*
*Para uso con agentes IA (Claude Code, Antigravity, otros)*

# AUDIT_PHYSICAL_RULES_REPORT.md - B1-B6 IMPLEMENTATION

**Fecha:** 15 de Enero, 2026  
**Objetivo:** Implementar reglas canónicas B1-B6 en el motor CARCOSA  
**Baseline:** 89 tests passed

---

## CHECKLIST B1-B6

| Ítem | Descripción | Estado | Archivos | Tests |
|------|------------|--------|----------|-------|
| B1 | ILUMINADO (+1 acción, 2 rondas) | ⏳ EN PROGRESO | `state.py`, `transition.py`, `legality.py` | `test_illuminated_*` |
| B2 | MOTEMEY (vender/comprar) | ⏳ EN PROGRESO | `state.py`, `transition.py`, `legality.py`, `actions.py` | `test_motemey_*` |
| B3 | POOL LLAVES (6→7 condicional) | ⏳ EN PROGRESO | `config.py`, `setup` | `test_keys_pool_*` |
| B4 | PUERTAS AMARILLO (teletransporte) | ⏳ EN PROGRESO | `transition.py`, `legality.py`, `actions.py` | `test_yellow_doors_*` |
| B5 | PEEK DOS HABITACIONES | ⏳ EN PROGRESO | `transition.py`, `legality.py`, `actions.py` | `test_peek_rooms_*` |
| B6 | ARMERÍA (almacenamiento) | ⏳ EN PROGRESO | `state.py`, `transition.py`, `legality.py` | `test_armory_*` |

---

## ARQUITECTURA IDENTIFICADA

### ActionType
Ubicación: `engine/actions.py`
- Enum con acciones: MOVE, SEARCH, MEDITATE, END_TURN, KING_ENDROUND, SACRIFICE, ESCAPE_TRAPPED
- **Acciones a agregar:** USE_MOTEMEY_BUY, USE_MOTEMEY_SELL, USE_YELLOW_DOORS, USE_PEEK_ROOMS, USE_ARMORY_DROP, USE_ARMORY_TAKE

### StatusInstance / Estados
Ubicación: `engine/state.py`
- `status_id: str`, `remaining_rounds: int`, `stacks: int`
- Expiración: decrementan `remaining_rounds` cada ronda
- **Estados a usar:** "ILLUMINATED" (nuevo), "TRAPPED" (existente)

### Cálculo de Acciones
Ubicación: `engine/transition.py:_start_new_round()`
- Base: 2 acciones
- Modifiers: `limited_action_floor_next`, `sanity <= S_LOSS`
- **Hook B1:** Agregar `+ (ILLUMINATED? 1 : 0)` en cálculo

### Habitaciones
Ubicación: `engine/state.py:RoomState`
- `room_id: RoomId`, `deck: DeckState`, `revealed: int`
- **SUPUESTO:** No existe campo `special_room_type`; será agregado si necesario para B2-B6

### GameState - Nuevos campos B1-B6
- `motemey_deck: DeckState` (B2)
- `motemey_event_active: bool` (B2)
- `armory_storage: Dict[RoomId, List[str]]` (B6, capacidad 2 por armería)
- `peek_used_this_turn: bool` (B5)

---

## SUPUESTOS DOCUMENTADOS

### B2 - MOTEMEY
- **SUPUESTO:** Compra siempre ofrece 2 cartas. Si jugador no tiene espacio para elegida, transacción falla (no se paga cordura).
- **SUPUESTO:** Carta no elegida vuelve al mazo del Motemey (no se descarta).
- **SUPUESTO:** Mazo Motemey se prepara en setup (3 Brújulas, 3 Viales, 2 Contundentes, 4 Tesoros, 1 Llave, 1 Cuento).

### B3 - POOL LLAVES
- **SUPUESTO:** Cámara Letal se elige en preparación. Si está presente, hay 7 llaves totales (5 en mazos, 1 en Motemey, 1 extra). Dónde va la extra: en el evento de Cámara Letal o en mazos generales (REQUIERE CLARIFICACIÓN DE CANON).

### B4 - PUERTAS
- **SUPUESTO:** Puertas es una habitación especial con ID fijo (ej. "PUERTAS_AMARILLO").

### B5 - PEEK
- **SUPUESTO:** "Ver" = peek sin extraer. Flag `peek_used_this_turn` se resetea al inicio del turno del jugador.

### B6 - ARMERÍA
- **SUPUESTO:** Sin coste de acción para drop/take. Si falta capacidad, acción falla.
- **SUPUESTO:** Monstruo entra a Armería → destruye Armería y purga items.

---

## CAMBIOS REALIZADOS

(Se actualizará durante la implementación)

---

## COMANDOS EJECUTADOS

```bash
# BASELINE
cd "c:\Users\mirtg\OneDrive\Escritorio\Cristobalini\code related\CARCOSA"
python -m pytest -q
# → 89 passed
```

---

## PRÓXIMOS PASOS

1. Bloque 1: Implementar B1 (ILUMINATED)
2. Bloque 2: Implementar B2+B3 (MOTEMEY + pool llaves)
3. Bloque 3: Implementar B4 (PUERTAS)
4. Bloque 4: Implementar B5 (PEEK)
5. Bloque 5: Implementar B6 (ARMERÍA)
6. Auditoría final y tests verdes

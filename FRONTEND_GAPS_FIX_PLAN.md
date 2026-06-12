# CARCOSA Frontend — Plan Integral de Arreglos Priorizados

**Basado en auditoría completa: Frontend (web/) vs Simulador (engine/) vs Canon (docs/)**
**Fecha:** 2026-06-12
**Branch actual:** `feat/html-canvas-playtest`

---

## ACLARACIÓN IMPORTANTE: OUTCOMES

El simulador tiene **3 caminos a game_over** pero **solo 2 outcomes finales** para el frontend:
- `WIN` → Victoria canónica
- `LOSE` → Derrota (con `state.outcome` détaillant la cause: `LOSE_ALL_MINUS5 (source)` o `LOSE_KEYS_DESTROYED`)

**Frontend debe mostrar la causa específica en la pantalla de Game Over.**

---

## PRIORIDAD 0 — CRÍTICOS (Bloquean jugabilidad / rompen canon)

### P0-1: UI de Sacrificio Dinámica
**Archivos:** `web/js/main.js` (renderActions, executePlayerAction), `web/js/api.js` (nuevo endpoint o extendido)

**Problema:** Frontend hardcodea 2 opciones (SANITY_MAX / OBJECT_SLOT) sin consultar opciones reales del jugador.

**Solución:**
1. **Nuevo endpoint** `GET /legal/{game_id}/{actor}` ya devuelve acciones `SACRIFICE` con `data.mode` y `data.discard_object_id` — **usar eso**.
2. En `renderActions()`: para `SACRIFICE`, leer `action.data` del servidor:
   - Si `mode === "SANITY_MAX"` → mostrar "Sacrificar 1 Cordura Máxima"
   - Si `mode === "OBJECT_SLOT"` y `discard_object_id` → mostrar "Descartar: {nombre_objeto}"
   - Si `mode === "OBJECT_SLOT"` sin `discard_object_id` → mostrar "Reducir slot de objeto (elegir al confirmar)"
3. **Modal de confirmación** al clickear SACRIFICE si hay múltiples opciones (object_slots con varios objetos descartables).

**Criterio de aceptación:** Opciones mostradas = exactamente las que devuelve `/legal`. Sin opciones → no mostrar botón SACRIFICE (server maneja consecuencias automáticas).

---

### P0-2: Pantalla Game Over con Causa Específica
**Archivos:** `web/js/main.js` (showGameOver), `web/index.html` (gameOverDetails)

**Problema:** Muestra genérico "perdió la cordura o las llaves físicas han sido destruidas".

**Solución:** Parsear `state.outcome`:
```javascript
// state.outcome examples: "WIN", "LOSE_ALL_MINUS5 (KING_PRESENCE -> P1)", "LOSE_KEYS_DESTROYED"
if (state.outcome === "WIN") { ... }
else if (state.outcome.startsWith("LOSE_ALL_MINUS5")) {
    const source = state.outcome.match(/\((.+)\)/)?.[1] || "desconocido";
    details = `Todas las almas cayeron a -5 cordura.<br>Golpe final: ${source}`;
} else if (state.outcome === "LOSE_KEYS_DESTROYED") {
    details = `Llaves destruidas superaron el umbral.<br>Llaves en juego: ${state.keys_total - state.keys_destroyed} ≤ 3`;
}
```

**Criterio de aceptación:** Game Over muestra causa exacta + datos relevantes (source, llaves restantes).

---

### P0-3: Roles Completos (7 canónicos) + Selector en Lobby
**Archivos:** `web/index.html` (lobby player config), `web/js/main.js` (humanPlayers, createGame), `web/css/style.css` (role badges)

**Roles canónicos (`engine/config.py:41-50`):**
| Rol | Habilidad | Frontend |
|-----|-----------|----------|
| SCOUT | 1 movimiento gratis/turno | ✅ Parcial (free_move_used_this_turn en state) |
| HIGH_ROLLER | Double roll 1/turno | ✅ Parcial (double_roll_used_this_turn) |
| TANK | Shield + bloquea meditación otros | ❌ Falta shield UI + bloqueo meditación |
| BRAWLER | Contundente gratis | ❌ Falta cost_override=0 en USE_BLUNT |
| HEALER | -1 propia → +2 otros + estado (SANIDAD/ILUMINADO) | ❌ **Completo faltante** |
| PSYCHIC | Peek hallway (cartas adyacentes) | ❌ **Completo faltante** |
| 7º rol (¿WITCH?) | TBD | ❌ **Completo faltante** |

**Solución:**
1. **Lobby:** Reemplazar 4 slots fijos por **pool de 7 roles** con selector `RANDOM_UNIQUE` (default) / `FIXED` / `RANDOM_WITH_REPLACEMENT` (configurable).
2. Asignar rol al crear partida → enviar en `players[]` al server (ya soporta `roles_assigned`).
3. **renderActions:** Inyectar acciones específicas por rol:
   - HEALER: `USE_HEALER_HEAL` (si sanity ≥ 1 y hay otros)
   - PSYCHIC: `PEEK_ROOM_DECK` para habitaciones adyacentes (no solo actual)
   - TANK: Visualizar `shield` en stats + bloquear meditación otros (backend ya hace)
   - BRAWLER: `USE_BLUNT` con `cost_override=0` (badge "GRATIS")
4. **renderPlayersList:** Mostrar habilidad especial por rol (icono + tooltip).

**Criterio de aceptación:** 7 roles seleccionables, habilidades funcionan via `/legal`, UI refleja estado (shield, double_roll, free_move).

---

### P0-4: Reina Helada + ICE_SERVANT — Movimiento Bloqueado + Acción Reducida
**Archivos:** `web/js/main.js` (renderActions, updateState), `web/js/renderer.js` (drawPlayers)

**Engine (`legality.py:40-48`, `player.py:22-38`):**
- `movement_blocked_players`: array de PIDs que **no pueden moverse** este turno (efecto inmediato revelación Reina)
- `_floor_has_ice_servant()` → `_cap_actions_for_ice_servant()` → `remaining_actions = min(remaining, 1)`

**Frontend actual:** Recibe `state.movement_blocked_players` pero **no lo usa**.

**Solución:**
1. En `renderActions()`: si `state.movement_blocked_players.includes(activeActor)` → **filtrar todas las acciones MOVE** (incluye USE_PORTABLE_STAIRS, USE_YELLOW_DOORS, USE_OBJECT:COMPASS).
2. En `renderActions()`: si `_floor_has_ice_servant(state, floor_of(activeActor.room))` → **cambiar label "Acciones: N" a "Acciones: 1 (Reina Helada)"** y limitar botones mostrados a 1 (except END_TURN).
3. En `renderer.js` `drawPlayers()`: aura especial para `movement_blocked` (ej. icono 🧊 sobre token) y para `ICE_SERVANT` (icono ❄️ en piso).

**Criterio de aceptación:** Jugador con movimiento bloqueado no ve botones MOVE; jugador en piso con ICE_SERVANT ve máximo 1 acción + indicador visual claro.

---

### P0-5: Tue-Tue Acumulativo — Contador + Escalada Daño
**Archivos:** `web/js/main.js` (processServerLog, ENTITY_DB), `web/js/renderer.js` (drawMonsters? no spawnea), `web/css/style.css`

**Canon:** 3 revelaciones → daño -1, -2, -5(fija) + STUN piso; persistente: 1 acción/piso Reina.

**Engine:** `state.tue_tue_revelations` (contador global), event `TUE_TUE_REVEALED` con `revelation_count`.

**Frontend:** Solo tiene `OMEN:TUE_TUE` en ENTITY_DB como presagio genérico.

**Solución:**
1. **ENTITY_DB:** Reemplazar `OMEN:TUE_TUE` por entradas por revelación:
   ```javascript
   "TUE_TUE_REV_1": { name: "Tue-Tue (1ª Revelación)", desc: "-1 cordura (-2 con Vanidad)", ... },
   "TUE_TUE_REV_2": { name: "Tue-Tue (2ª Revelación)", desc: "-2 cordura (-3 con Vanidad)", ... },
   "TUE_TUE_REV_3": { name: "Tue-Tue (3ª+ Revelación)", desc: "Fija cordura en -5. Ignora Vanidad. STUN piso.", ... },
   ```
2. `processServerLog`: detectar `log.event === "TUE_TUE_REVEALED"` → usar `log.revelation_count` para mostrar carta correcta + actualizar contador visible en UI (ej. pill `TUE-TUE: 2/3` en header).
3. **Efecto persistente:** Si `state.tue_tue_revelations >= 3` y `state.king_floor` tiene Reina → mostrar indicador "Acción reducida: 1" en jugadores de ese piso.

**Criterio de aceptación:** Contador visible, daño escalonado correcto en logs, STUN piso en 3ª revelación, acción reducida persistente.

---

## PRIORIDAD 1 — ALTOS (Funcionalidad incompleta en habitaciones especiales)

### P1-1: Cámara Letal — Validación 2 Jugadores + Costos d6 + Flag Completado
**Archivos:** `web/js/main.js` (renderActions, processServerLog), `web/index.html` (nuevo overlay confirmación)

**Reglas canon:**
- Requiere: 2 jugadores en room, `CAMARA_LETAL_PRESENT=true`, `!CAMARA_LETAL_RITUAL_COMPLETED`, room no destruida
- 1 acción por jugador participante
- d6 → costos: 1-2=[7,0], 3-4=[4,3], 5-6=[4,3]
- Otorga 7ª llave al pool (incrementa llaves disponibles)
- Flag `CAMARA_LETAL_RITUAL_COMPLETED=true` (una vez/partida)

**Solución:**
1. `renderActions`: `USE_CAMARA_LETAL_RITUAL` solo si `state.flags.CAMARA_LETAL_PRESENT && !state.flags.CAMARA_LETAL_RITUAL_COMPLETED && players_in_room.length === 2`.
2. Al clickear → **modal de confirmación** mostrando: "Ritual Cámara Letal: d6 determina costo. 1-2: [7,0] | 3-6: [4,3]. ¿Participar?".
3. `processServerLog`: evento `CAMARA_LETAL_RITUAL` → mostrar d6, costos aplicados, llave otorgada.
4. Deshabilitar botón permanentemente tras `CAMARA_LETAL_RITUAL_COMPLETED`.

---

### P1-2: Taberna — Tooltip Reglas + Validación Solo Habitaciones
**Archivos:** `web/js/main.js` (renderActions tooltips), `web/index.html` (tooltip CSS)

**Reglas:** FREE (no acción), solo habitaciones (no pasillos), 2 distinct, 1x/turno, -1 cordura actor, rota mazos (peek mutuo).

**Solución:**
1. Tooltip en botón `USE_TABERNA_ROOMS`: "FREE · Solo habitaciones (no pasillos) · 2 distintas · 1 uso/turno · -1 Cordura · Rota mazos (peek mutuo)".
2. `renderActions`: mostrar `actionCost = "FREE (-1 Cordura)"` en vez de "Gratis".
3. Validación visual: si `state.taberna_used_this_turn[pid]` → botón deshabilitado con "✓ Usado este turno".

---

### P1-3: Armería — Límite 2 Items + Soulbound Check + Storage Visual
**Archivos:** `web/js/main.js` (renderActions), `web/js/renderer.js` (drawRoom armory storage)

**Reglas:** Storage max 2 items (keys + objects), no soulbound, FREE.

**Solución:**
1. `renderer.js` `drawRoom`: mostrar contador `Eq: X/2` + lista items.
2. `renderActions`: `USE_ARMORY_DROP` solo si `storage_count < 2` y tiene items no soulbound.
3. `USE_ARMORY_TAKE` solo si `storage_count > 0`.
4. Tooltip: "Storage: 2 items máx (llaves + objetos) · No soulbound · FREE".

---

### P1-4: Puertas Amarillas — Selector Target Visual + Penalidad -1 Cordura Target
**Archivos:** `web/js/main.js` (renderActions → modal), `web/index.html` (modal target picker)

**Reglas:** PAID (1 acción), teletransporta target a tu room, target -1 cordura, reveal.

**Solución:**
1. Al clickear `USE_YELLOW_DOORS` → **modal** con lista de otros jugadores (nombre, rol, room actual, cordura).
2. Confirmación: "Transportar a {target} a tu room. {target} sufre -1 cordura. ¿Confirmar?".
3. `renderActions`: `actionCost = "1 Ac. (Target -1 Cordura)"`.

---

### P1-5: Salón de Belleza — Contador Global + VANIDAD Efecto Real
**Archivos:** `web/js/main.js` (processServerLog, render header), `web/js/renderer.js` (VANIDAD aura)

**Reglas:** Contador global `salon_belleza_uses`. Cada 2 usos → VANIDAD (+1 daño cordura permanente). PAID (1 acción).

**Solución:**
1. Header: pill `SALÓN: {salon_belleza_uses} usos` (leer `state.salon_belleza_uses`).
2. `processServerLog`: evento `SALON_BELLEZA_USED` → actualizar contador + si `uses % 2 === 0` log "¡VANIDAD adquirida! (+1 daño cordura permanente)".
3. `renderer.js` `drawPlayers`: aura VANIDAD distinta (ej. rosa parpadeante) + badge en stats.
4. `sanity_bar`: si jugador tiene VANIDAD, tooltip "Vanidad: +1 daño cordura".

---

### P1-6: Monasterio (Capilla) — Riesgo PARANOIA Explícito + Cura Variable
**Archivos:** `web/js/main.js` (renderActions, processServerLog)

**Reglas:** PAID (1 acción), cura d6+2, d6=1 → PARANOIA (5 turnos).

**Solución:**
1. `renderActions`: `actionText = "⛪ Capilla: Meditar (d6+2 Cordura, 1/6 PARANOIA)"`, `actionCost = "1 Ac."`.
2. `processServerLog`: evento `CAPILLA_USED` → mostrar d6, cura, si PARANOIA.

---

### P1-7: Motemey — UI Compra 2 Cartas (BUY_START → BUY_CHOOSE)
**Archivos:** `web/js/main.js` (renderActions, processServerLog), `web/index.html` (modal 2 cartas)

**Reglas:** 2 pasos: `BUY_START` (-2 cordura, muestra 2 cartas) → `BUY_CHOOSE` (elige 0/1). Mazo 13 cartas fijas. SELL: +1 cordura (normal) / +3 (tesoro).

**Solución:**
1. `renderActions`: si `state.pending_motemey_choice[pid]` → mostrar **solo** `BUY_CHOOSE` (2 botones: "Elegir Carta 1", "Elegir Carta 2") + `END_TURN` + `DISCARD_SANIDAD`.
2. Modal `BUY_START`: muestra 2 cartas con icono, nombre, desc → click para elegir.
3. `SELL`: tooltip diferenciar normal (+1) vs tesoro (+3).

---

## PRIORIDAD 2 — MEDIOS (Modelado de estado avanzado)

### P2-1: Soulbound / Object_Slots_Penalty / Object_Charges
**Archivos:** `web/js/main.js` (renderPlayersList), `web/js/renderer.js` (drawPlayers inventory)

**Campos en `PlayerState`:**
- `soulbound_items: []` — no descartables, no robables (d6=6), no vendibles
- `object_slots_penalty: int` — reduce capacidad objetos (base - penalty)
- `object_charges: { "PORTABLE_STAIRS": 3, "TREASURE_STAIRS": 3 }` — usos restantes

**Solución:**
1. `renderPlayersList`: separar inventario en "Objetos" vs "Soulbound" (icono 🔒).
2. Mostrar `object_charges` como `PORTABLE_STAIRS (3)` → decrementar visual al usar.
3. `object_slots_penalty`: stat `Slots: {actual}/{base - penalty}` (ej. 3/4).
4. `legality.py` ya filtra soulbound en Motemey/Armory/d6=6 — frontend solo refleja.

---

### P2-2: Anillo Activado — Tracking + Efecto -2/Ronda
**Archivos:** `web/js/main.js` (updateState, renderPlayersList), `web/js/renderer.js` (drawPlayers)

**Engine:** `state.ring_activated_by: PlayerId`. Efecto: -2 cordura/turno al portador (start of round).

**Solución:**
1. Si `state.ring_activated_by` → badge 💍 "Anillo Activo" en holder + en header.
2. `renderPlayersList`: en holder, stat `Anillo: -2 cordura/turno`.
3. Log inicio de ronda: "Anillo drena -2 cordura a {holder}".

---

### P2-3: Libro Chambers + Cuentos — Holder + Adjuntos + Vanish Turns
**Archivos:** `web/js/main.js` (renderPlayersList, renderActions), `web/index.html` (grimorio filter cuentos)

**Engine:** `chambers_book_holder`, `chambers_tales_attached` (0-4), `king_vanished_turns = tales_attached`.

**Solución:**
1. `renderPlayersList`: si `pid === chambers_book_holder` → icono 📘 en token + "Libro Chambers ({tales_attached}/4 cuentos)".
2. `USE_ATTACH_TALE`: solo si holder + tiene `TALE_*` en objects.
3. Header: si `king_vanished_turns > 0` → pill `REY DESVANECIDO: {turns} turnos`.
4. Grimorio: filtro "Cuentos" muestra solo `TALE_*` con badge "Unido" si `TALE_ATTACHED_{id}` flag.

---

### P2-4: Falso Rey (Corona) — Piso Falso Rey + Presencia Daño
**Archivos:** `web/js/main.js` (updateState, render header), `web/js/renderer.js` (drawKingPresence)

**Engine:** `false_king_floor`, `false_king_round_appeared`, `CROWN_HOLDER` flag. Presencia daño en piso FK (d6 + sanity vs threshold).

**Solución:**
1. Header: si `false_king_floor` → pill `FALSO REY EN PISO {false_king_floor}` (color magenta).
2. `renderer.js`: corona secundaria 👑 en pasillo piso FK (distinta de Rey real).
3. `king_floor` movement: Rey real **no va a piso FK** (ruleta re-tira) — visual coherente.
4. Log: "Falso Rey aparece en Piso X (Corona activada por {holder})".

---

### P2-5: King Phase Breakdown — Log Desglosado Completo
**Archivos:** `web/js/main.js` (processServerLog para KING_ENDROUND)

**Engine pasos (`king.py:193-291`):**
1. Casa (-1 todos)
2. Vanish check
3. Ruleta d4 → nuevo piso (evita FK)
4. Presencia daño (tabla R1-3:1, R4-6:2, R7-9:3, R10+:4)
5. Efecto d6 (6 tipos)
6. Monster phase
7. Status EOR
8. False King check
9. Stair reroll + boxes rotation
10. Victory check

**Solución:** `processServerLog` para `KING_ENDROUND` → emitir sub-logs secuenciales:
```javascript
addLog("REY", `🏠 Casa: -1 cordura a todos`);
addLog("REY", `🎲 Ruleta d4=${d4}: Rey se manifiesta en Piso ${new_floor}`);
if (pres > 0) addLog("REY", `👑 Presencia (Ronda ${round}): -${pres} cordura en Piso ${king_floor}`);
switch(d6) {
  case 1: addLog("REY", `⚡ d6=1: Rotación intra-piso (R1→R4→R3→R2)`); break;
  case 2: addLog("REY", `☠️ d6=2: -1 cordura a todos (exc. Falso Rey)`); break;
  case 3: addLog("REY", `⏱️ d6=3: Acción reducida en Piso ${king_floor} next round`); break;
  case 4: addLog("REY", `🚪 d6=4: Expulsión del Piso ${king_floor} (exc. Falso Rey)`); break;
  case 5: addLog("REY", `🧲 d6=5: Atracción al Piso ${king_floor} (exc. Falso Rey)`); break;
  case 6: addLog("REY", `🤲 d6=6: Robo objeto no soulbound a todos`); break;
}
addLog("REY", `👾 Fase de Monstruos resuelta`);
addLog("REY", `🎴 Escaleras reroll + rotación cajas`);
```

---

## PRIORIDAD 3 — BAJOS (Pulido / Experiencia)

### P3-1: Mazo Motemey / Global — Contadores Cartas Restantes
**Archivos:** `web/js/main.js` (updateState motemey_deck), `web/index.html` (motemey panel)

**Solución:** En `updateState`: si `state.motemey_deck` → pill `MOTEMEY: {remaining}/13 cartas`. Similar para mazo global (suma `deck.remaining()` por room).

### P3-2: Validador Invariantes Habitaciones Especiales (Setup Visual)
**Archivos:** `web/index.html` (lobby pre-game), `web/js/main.js` (createGame)

**Solución:** Al crear partida, mostrar resumen: "Habitaciones especiales: TABERNA(F2_R3), MOTEMEY(F1_R1), CAMARA_LETAL(F3_R4) ✓ 3 total · 1/piso · 0 en pasillos".

### P3-3: Audio Cues Específicos por Evento (Ya mayormente cubierto)
**Estado:** `CarcosaAudio` tiene métodos para todos los eventos principales. Verificar mapeo completo en `processServerLog`.

### P3-4: Llaves — Capacidad por Rol Visual
**Archivos:** `web/js/main.js` (renderPlayersList stats)

**Engine:** `get_max_keys_capacity(p)` por rol (SCOUT=2, TANK=1, etc. — ver `engine/inventory.py`).

**Solución:** Stat `🔑 {keys}/{capacity}` en lugar de solo `🔑 {keys}`.

### P3-5: HEALER / PSYCHIC — Tooltips Habilidades en Grimorio
**Archivos:** `web/js/main.js` (ENTITY_DB agregar roles), `web/index.html` (grimorio filter "Roles")

**Solución:** Agregar entradas `ROLE:HEALER`, `ROLE:PSYCHIC`, etc. en `ENTITY_DB` con descripciones mecánicas completas.

---

## DEPENDENCIAS ENTRE TAREAS

```
P0-1 (Sacrificio UI) ← independientes
P0-2 (Game Over) ← independientes
P0-3 (Roles) → habilita P2-5 (HEALER/PSYCHIC UI), P2-3 (Libro holder)
P0-4 (Reina/ICE) ← independientes
P0-5 (Tue-Tue) ← independientes

P1-1..P1-7 (Habitaciones) → requieren P0-3 (roles para algunas acciones)
P2-1 (Soulbound/Charges) → base para P1-3 (Armory), P1-4 (Puertas), P1-7 (Motemey)
P2-2 (Anillo) ← independiente
P2-3 (Libro) → requiere P0-3 (roles para CUENTOS)
P2-4 (Falso Rey) ← independiente
P2-5 (King breakdown) ← independiente

P3-* → todos opcionales, post-MVP
```

---

## ARCHIVOS A MODIFICAR (Resumen)

| Archivo | Tareas Afectadas |
|---------|------------------|
| `web/js/main.js` | **Todas** (renderActions, processServerLog, updateState, renderPlayersList, showGameOver, lobby) |
| `web/index.html` | P0-3 (lobby roles), P1-1 (modal cámara), P1-4 (modal puertas), P1-7 (modal motemey), P3-2 (setup summary) |
| `web/js/renderer.js` | P0-4 (auras movimiento bloqueado/ICE), P0-5 (contador Tue-Tue), P1-3 (armory storage visual), P2-1 (inventario soulbound/charges), P2-4 (falso rey visual) |
| `web/js/api.js` | P0-1 (si nuevo endpoint necesario), P1-7 (pending_motemey_choice handling) |
| `web/css/style.css` | P0-3 (role badges), P0-4 (auras nuevas), P0-5 (pill Tue-Tue), P1-5 (contador salón), P2-2 (anillo badge), P2-4 (falso rey pill) |
| `web/js/renderer.js` particles | P0-5 (partículas Tue-Tue?) |

---

## CRITERIOS DE ACEPTACIÓN GLOBALES (Definition of Done)

1. **Cero desviaciones canon** en reglas visibles: sacrificio, victoria/derrota, roles, habitaciones especiales, monstruos, estados, objetos.
2. **UI refleja estado servidor** sin hardcodeos: todas las opciones de acción vienen de `/legal`, todos los contadores vienen de `state`.
3. **Accesibilidad:** ARIA en modales nuevos, `prefers-reduced-motion` respetado, `escapeHTML` en todo output dinámico.
4. **Tests visuales:** Jest/Puppeteer para flujos críticos (sacrificio, cámara letal, game over, rey phase).
5. **Performance:** `renderLoop` 60fps estable, sin memory leaks en WS reconexión.

---

## ESTIMACIÓN DE ESFUERZO (Relative)

| Prioridad | Tareas | Estimación (días dev) |
|-----------|--------|----------------------|
| P0 | 5 | 3-4 |
| P1 | 7 | 4-5 |
| P2 | 5 | 3-4 |
| P3 | 5 | 2-3 |
| **Total** | **22** | **12-16 días** |

---

## PRÓXIMO PASO RECOMENDADO

**Iniciar por P0-1 + P0-2 + P0-3** (core gameplay loop: sacrificio → game over → roles) en branch `fix/frontend-gaps-p0`.
Luego `P0-4 + P0-5` (monstruos especiales).
Luego `P1-*` batch por habitación especial.
Luego `P2-*` batch modelado estado.
`P3-*` en limpieza final.

¿Quieres que genere el **branch + primer commit** con P0-1 (Sacrificio UI dinámica) como punto de partida?
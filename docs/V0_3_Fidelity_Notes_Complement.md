# Carcosa v0.3 — Notas de fidelidad al juego físico (Complemento del Implementation Plan)

**Alcance:** Este documento consolida únicamente los hallazgos A–F detectados en la revisión de **v0.3**, junto con las aclaraciones posteriores y las **instrucciones concretas** para solucionarlos.

**Autoridad:** El **Implementation Plan del repositorio** es la fuente de verdad en cuanto a líneas centrales y orden macro del trabajo. Este archivo es **complementario**: fija decisiones cerradas, añade detalles de implementación y define tests de regresión para evitar drift.

**Nota operativa sobre “recordar”:** la memoria persistente del asistente está deshabilitada en este proyecto. Por eso las reglas definitivas (especialmente STUN) se fijan aquí y deben copiarse al CANON/Implementation Plan.

---

## A) Habitaciones especiales — Setup “1 por piso” (físico)

### Regla física (confirmada)
- Se eligen **3 habitaciones especiales** (3 tipos distintos) desde el pool total.
- Se colocan **boca abajo**, **una por piso**.
- En cada piso, su habitación se define con **D4 → R1..R4** (nunca pasillo).
- Se **revela** solo cuando un jugador entra **por primera vez** a esa habitación.
- Activar el efecto de habitación especial **no consume acción**.
- Si un **monstruo entra** en una habitación especial, esta se **destruye**.

### Problema v0.3
- El setup actual tiende a colocar más de 3 especiales (o una misma especial en múltiples pisos), lo que rompe el físico.

### Mejor solución propuesta (robusta y “engine-first”)
1) **Centralizar setup** en el engine (no en `sim/runner.py`):
- Crear `engine/setup.py::setup_special_rooms(state, rng, pool)` y que sim/tests lo llamen.

2) **Pool único** en un solo lugar:
- Crear `engine/special_rooms.py::SPECIAL_ROOMS_POOL = [...]`.

3) **Algoritmo (exactamente 3 colocaciones):**
- `chosen = rng.sample(pool, k=3)` (sin repetición)
- `rng.shuffle(chosen)` y asignar `chosen[i]` al piso `i+1` (piso 1..3)
- Por cada piso `f`:
  - `room_index = roll_d4()` (o `rng.randint(1,4)`)
  - `rid = F{f}_R{room_index}`
  - setear en `RoomState`:
    - `special_card_id = chosen_for_floor`
    - `special_revealed = False`
    - `special_destroyed = False`
    - `special_activation_count = 0`

4) **Invariantes (fail-fast):**
- Debe existir **exactamente 1** `special_card_id != None` por piso.
- Deben existir **exactamente 3** en total.
- No puede ubicarse en pasillos.

### Tests mínimos (regresión)
- `test_special_setup_one_per_floor`: 3 especiales totales; 1/piso; ubicadas en R1..R4.
- `test_special_reveal_on_first_entry`: primera entrada revela; reentrada no re-revela.
- `test_special_destroyed_on_monster_entry`: entrada/movimiento/spawn de monstruo destruye y deshabilita.

---

## B) STUN y trampas — Reglas definitivas (jugadores/monstruos)

### Reglas definitivas (confirmadas)
1) **Jugador atrapado por Araña**
- Queda con **3 turnos** de atrapado (stun/trap).
- En **cada uno de sus turnos** mientras está atrapado puede intentar liberarse:
  - `d6 + cordura_actual`
  - si el resultado es **>= 3**, se libera antes.

2) En este caso (Araña) y “como el viejo del saco”:
- Al liberarse, el **monstruo en cuestión** queda stuneado por **1 turno**.

3) **Objeto contundente** usado por jugador NO atrapado contra un monstruo:
- El monstruo queda stuneado por **2 turnos**.

4) **El Rey de Amarillo no puede ser stuneado.**

### Implicación técnica
Esto reemplaza cualquier simplificación previa del tipo “STUN=1 para todo”. Se necesitan:
- Estado “TRAPPED” (Araña) con duración 3 y chequeo por turno.
- Identidad del monstruo fuente del trap (para stuneo 1 turno al liberarse).
- Stun por contundente (2 turnos) para monstruos, con excepción Rey.

### Implementación recomendada (mínima y fiel)
- Estados sugeridos:
  - `TRAPPED_SPIDER(remaining_turns=3, source_monster_id=...)`
  - `TRAPPED_SACK(...)` si aplica
  - `STUN_MONSTER(remaining_turns=1|2)` para monstruos (no Rey)
- Inicio del turno del jugador:
  - Si `TRAPPED_*` activo:
    - resolver “escape roll” (acción coste 0 o subfase automática) con `d6 + cordura_actual >= 3`.
    - si libera: remover `TRAPPED_*` y aplicar `STUN_MONSTER(1)` al `source_monster_id`.
- Objeto contundente:
  - aplicar `STUN_MONSTER(2)` salvo si `monster.is_yellow_king`.

### Tests mínimos (regresión)
- `test_spider_trap_duration_3_turns`
- `test_spider_escape_roll_releases`
- `test_escape_stuns_source_monster_1_turn`
- `test_blunt_stuns_monster_2_turns`
- `test_yellow_king_not_stunnable`

**Pregunta abierta necesaria (B):**
- Si el jugador falla el intento de escape, ¿pierde igualmente sus 2 acciones ese turno, o puede actuar tras fallar?

---

## C) Habitaciones especiales no consumen acción

### Regla física (confirmada)
- Activar el efecto de una habitación especial **no consume** una de las 2 acciones del jugador.

### Corrección
- Centralizar un set/lista de **acciones free** (coste 0).
- Incluir:
  - `USE_YELLOW_DOORS` (Puertas de Amarillo)
  - acciones de Motemey / Peek / Armería / Cámara Letal
  - cualquier `ACTIVATE_SPECIAL_ROOM`

### Tests mínimos
- Un test por especial: tras activación, `actions_left` no cambia.

---

## D) Motemey — Solución integral recomendada

### Objetivo físico
- Comprar: paga **2 cordura**, Motemey ofrece **2 cartas**, jugador elige **1**.

### Recomendación integral (determinista + replay-friendly)
**Diseño de 2 pasos con oferta persistida en estado:**
1) `MOTEMEY_BUY_START` (cobra -2 cordura)
- Precondiciones:
  - `cordura >= 2`
  - `motemey_deck.remaining() > 0`
  - no hay `pending_choice`
- Efecto:
  - extraer 2 cartas si hay (si solo 1, extraer 1) usando `draw_top()`
  - guardar `pending_choice = {kind:"MOTEMEY_BUY", player_id, offers:[CardId...]}`

2) `MOTEMEY_BUY_CHOOSE(index)` (coste 0)
- Precondiciones:
  - existe `pending_choice` del jugador
  - `index` válido
- Efecto:
  - entregar carta elegida al jugador según tipo (KEY suma keys; tesoros/objetos a inventario)
  - carta no elegida vuelve **al fondo** con `put_bottom(rejected)`
  - limpiar `pending_choice`

### Por qué esta solución
- Garantiza “elección real” a nivel de acciones legales.
- Replay determinista: la oferta queda registrada.
- Evita duplicación del mazo: se reinsertan **CardId reales** con `put_bottom()`.

### Tests mínimos
- `test_motemey_buy_offers_two_and_choose`
- `test_motemey_buy_with_one_card_offers_one`
- `test_motemey_rejected_goes_to_bottom_no_growth`
- `test_motemey_buy_blocked_if_pending_choice`

**Pregunta abierta necesaria (D):**
- La carta no elegida: ¿vuelve al fondo del mazo (recomendado) o se descarta?

---

## E) Corona — Unificar: una sola corona (TESORO + SOULBOUND)

### Regla física (confirmada)
- Solo existe **una** corona.
- La corona es un **tesoro** y es **SOULbound**.

### Corrección propuesta
- Un único ID canónico: `CROWN`.
- `CROWN.kind = TREASURE` y `CROWN.is_soulbound = True`.
- Eliminar `TREASURE_CROWN` (o mapearlo a `CROWN` en migración para no romper runs antiguos).

### Tests mínimos
- `test_crown_is_treasure_and_soulbound`
- `test_no_duplicate_crown_ids`

---

## F) Falso Rey — Fórmula más precisa (con ejemplo DPS)

### Ejemplo físico (DPS)
- Cordura máxima base DPS = 3:
  - 1er check exige 4
  - 2do exige 5
  - 3ro exige 6

### Fórmula precisa recomendada
- Estado: `false_king_check_target`
- Inicialización al obtener/activar corona:
  - `target = sanity_max_base + 1`
- Cada ronda con check:
  - `roll = d6 + sanity_current`
  - éxito si `roll >= target`
  - luego `target += 1`

> Nota: aunque en el ticket anterior se dijo “Falso Rey no es problema”, aquí se fija la fórmula correcta para alinear con físico.

### Tests mínimos
- `test_false_king_target_progression_dps_example` (RNG controlado)

---

## Revisión global de tests (obligatorio para evitar regresiones del motor real)

### Problema
Existen tests “verdes” que no ejercitan el motor (`step()`), por lo que no detectan regresiones reales.

### Acciones requeridas
1) Establecer dos niveles:
- Unit tests (funciones puras)
- Integration/Engine tests (siempre pasan por `get_legal_actions()` + `step()`)

2) Para cada bloque A–F, asegurar:
- 1 test de legalidad (acciones disponibles)
- 1 test de transición real (step)
- 1 test de serialización/replay si el estado lo requiere (D/E/F)

3) Añadir un smoke multi-seed (1,2,3):
- valida “no crash” + invariantes del estado.

---

## ¿Se necesitan más aclaraciones?
Sí, para implementar con rigor sin asumir:
1) (B) Si el jugador falla el escape del TRAPPED, ¿puede actuar ese turno o no?
2) (D) Carta no elegida en Motemey: ¿fondo del mazo o descarte?
3) (A) Lista canónica del pool de habitaciones especiales del físico y cuáles tienen efecto de “segunda activación” (p. ej. Salón de Belleza/Vanidad).

---

## Checklist Done v0.3 (A–F)
- [ ] Setup especiales: 3 totales; 1/piso; d4→R1..R4; boca abajo; reveal al entrar.
- [ ] Especiales free actions (incluye Puertas).
- [ ] TRAPPED Araña (3 turnos + escape roll >=3) + stun fuente 1 turno.
- [ ] Contundente: stun monstruo 2 turnos; Rey no stuneable.
- [ ] Motemey: oferta persistente + elección real + sin duplicación + replay determinista.
- [ ] Corona unificada: tesoro + soulbound; un solo ID.
- [ ] Fórmula Falso Rey documentada y testeada.
- [ ] Tests: integración con `step()` + smoke multi-seed + serialización/replay donde aplique.

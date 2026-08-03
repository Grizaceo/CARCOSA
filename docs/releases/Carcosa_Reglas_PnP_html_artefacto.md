# CARCOSA — Reglas Print & Play (fieles al código actual)

**Versión del motor relevado:** `engine/` · branch `feat/html-canvas-playtest`
**Fecha de relevamiento:** 2026-08-02 · **Fuente:** lectura directa de `engine/*.py` + `sim/runner.py` (no del libro PDF)
**Determinismo:** toda partida es determinista dado el seed (verificado byte a byte en auditoría 2026-07-12).

---

## 0. Presentación

CARCOSA es un juego cooperativo de tablero para 4 jugadores contra la Casa (mazos) y el Rey de Amarillo.
Ganás reuniendo llaves y llegando al Umbral; perdés si la cordura colectiva colapsa o las llaves fuera de juego pasan el límite.

**Nota de fidelidad:** este documento es *descripitivo del código*, no una re-promesa de reglas de mesa. Si algo contradice la edición print & play física, manda el código.

---

## 1. Material

- Tablero de 3 pisos (F1, F2, F3). Cada piso: pasillo (P) + 4 habitaciones (R1-R4) → 15 nodos.
- **Mazo de habitaciones** (canónico, `engine/setup.py:setup_canonical_deck`), repartido en las 12 habitaciones (R1-R4 × F1-F3). **107 cartas** (ver §5 para discrepancia vs 108 del docstring).
- **Mazo de Motemey** (13 cartas).
- 4 fichas de jugador, monstruos, Rey de Amarillo, d4 y d6, seeds de RNG determinista.
- **Llaves** (entidad separada de objetos): 6 en juego.

---

## 2. Roles y arranque

En `sim/runner.py:make_smoke_state`, por defecto roles fijos:
| Jugador | Rol | Nota |
|---|---|---|
| P1 | SCOUT | Mueve +1; al usar escalera, tira y puede aturdirse |
| P2 | HIGH_ROLLER | Suma 2d6 una vez por turno al resolver eventos |
| P3 | TANK | Capacidad/cordura más alta, bloquea meditación en el piso del Rey |
| P4 | BRAWLER | Mejora en combate con contundente |

En el lobby se usa `ROLE_DRAW_MODE = RANDOM_UNIQUE` (reparto canónico sin repetir roles).
Cada uno arranca repartido en pasillos F1/F2 con su cordura máxima e items de inicio según su catálogo.

**Región:** la Casa golpea **1 cordura** a cada jugador al final de cada ronda (`HOUSE_LOSS_PER_ROUND=1`).

---

## 3. Estructura del turno

- Cada jugador tiene **2 acciones** por turno.
- Orden de turno: P1 → P2 → P3 → P4.
- Tras los 4 jugadores → **Fase KING** (única acción interna de fin de ronda).
- El actor activo solo ve y puede ejecutar sus **acciones legales**; el resto ve "Esperando a...".

Acciones por jugador (generadas por `engine/legality.py`):
- **MOVE** a nodo conectado (misma planta). Escalera; vecinos de piso: escalera→escalera del piso contiguo.
- **SEARCH** si el mazo de la habitación tiene cartas (robar / revelar).
- **MEDITATE** (recuperar cordura), bloqueado en pasillo del piso del Rey o si un TANK está presente.
- **Usar objeto** (Brújula, Vial, Contundente, escaleras de tesoro).
- **Habitación especial** (si estás en una).
- **Habilidad de rol** (p. ej. heal del Healer).

Hay **interrupts** con prioridad absoluta: sacrificio (al caer a ≤-5), peek en pasillo, elección de Motemey.

---

## 4. Cómo se resuelven los EVENTOS de carta (el corazón del sistema)

**Fórmula de resolución (documentada en código):**

```
total = d6 + cordura_actual   (luego clamp a un mínimo de 0)
```

La carta no "sigue a la tensión". Cada evento tiene una tabla de efectos según ese `total`.

- Tira **1d6** (el HIGH_ROLLER puede hacerlo doble, una vez por turno).
- Súmale la **cordura actual del jugador** (no la máxima — sino la actual, la que tenga en ese momento).
- Si el total es negativo, se clampa a 0.
- Se escoge el efecto según el umbral de `total`.

Los eventos vienen con el prefijo `EVENT:` en el mazo; al resolver, la carta vuelve **al fondo** del mazo de la habitación.

### Tabla de eventos (por su `event_id` en el mazo)

#### EVENT:HAY_CADAVER
| total | Efecto |
|---|---|
| 0–2 | Pierdes tu siguiente turno |
| 3–4 | −1 cordura |
| 5+ | Ganas un objeto Contundente (si no hay slot, descarta) |

#### EVENT:COMIDA_SERVIDA
| total | Efecto |
|---|---|
| 0 | −3 cordura |
| 1–2 | Estado Envenado (duración 2) |
| 3–6 | +2 cordura |
| 7+ | Trae a otro jugador a tu habitación; tú y él +2 cordura |

#### EVENT:DIVAN_AMARILLO
| total | Efecto |
|---|---|
| 0–3 | Quita todos tus estados |
| 4–7 | Quita todos tus estados + +1 cordura |
| 8+ | Ganas estado SANIDAD (duración 2) |

#### EVENT:CAMBIA_CARAS — Esponja con un compañero
| total | Efecto |
|---|---|
| 0–3 | Intercambian posiciones con el jugador a tu derecha (siguiente en orden de turno) |
| 4+ | Intercambiás con el jugador a tu izquierda |

#### EVENT:FURIA_AMARILLO
| total | Efecto |
|---|---|
| 0 | El daño del Rey se **duplica permanentemente** |
| 1–4 | El Rey se mueve a tu piso; todos los jugadores en él pierden `HOUSE_LOSS` (1, o 2 si doble) |
| 5+ | Aturdes al Rey 1 turno |

#### EVENT:ASCENSOR
| total | Efecto |
|---|---|
| 0 | Fin de tu turno |
| 1–3 | Subes 1 piso (F1→F2→F3→F1) |
| 4–6 | Subes 2 pisos (F1→F3→F2→F1) |

#### EVENT:TRAMPILLA
| total | Efecto |
|---|---|
| 0 | Fin de tu turno |
| 1–3 | Bajas 2 pisos (= subir 1) |
| 4–6 | Bajas 1 piso (= subir 2) |

#### EVENT:GOLPE_AMARILLO / REFLEJO_AMARILLO
| total | Efecto |
|---|---|
| cualquiera | −2 cordura |

#### EVENT:ESPEJO_AMARILLO
| total | Efecto |
|---|---|
| — | El tablero invierte tu cordura (cordura × −1) |

#### EVENT:EVENTO_MOTEMEY
- Se activa la tienda de Motemey (interrumpir) inmediatamente: comprar o vender.

#### Cartas "amarillas" (FURIA, GOLPE, ESPEJO, DIVÁN y REFLEJO)
Si tenés **Protección Amarilla** activa (ronda 14 de Salón de Belleza) el evento se devuelve al fondo sin efecto.

---

## 5. Objetos (catálogo

| Objeto | Código | Efecto |
|---|---|---|
| Brújula | COMPASS | Mueve al pasillo del piso actual (gratis) |
| Vial | VIAL | +2 cordura (sin pasar el máximo) — gratis |
| Contundente | BLUNT | Aturde 2 turnos al monstruo en tu habitación; contra Ice Servant lo retira: si GOBLIN, dropea loot (objetos y llaves); contra Bogeyman, libera víctima; contra Rey de Amarillo es inmune |
| Escalera de tesoro | TREASURE_STAIRS | 3 usos: coloca una escalera temporal en tu habitación, válida 1 turno |
| Llavero | TREASURE_RING | Efecto pasivo: +1 slot de llave y +1 cordura máxima |
| Capilla | (estancia) | tira 1d6: curas de tu +2; si el dado=1 también ganas PARANOIA |

**Reglas soulbound:** objeto soulbound (Corona, BOOK_CHAMBERS) no se puede intercambiar/dropear, no lo quita el descarte del Rey y no ocupa slot.

**Llavero** es pasivo: no se usa; aumenta max cordura y slots de llaves.

---

## 5. Habitaciones especiales (7 del pool; 3 por partida, 1 por piso)

`engine/setup.py` elige 3 del pool (7 tipos) repartiendo 1 por piso, ubicadas con D4 en R1-R4, nunca en pasillo, **boca abajo** hasta la primera entrada.

| Habitación | Costo de acción | Efecto |
|---|---|---|
| TABERNA | Gratis | Revela la plancha superior de 2 habitaciones (peek) ; −1 cordura |
| MOTEMEY | Gratis | Tienda: **Comprar** (−2 cordura, miras 2 cartas del mazo Motemey, guardas 1); **Vender** un objeto (no soulbound) → si es tesoro: más 3 ; objeto normal: tepat +1 |
| ARMERÍA | Gratis | Almacenar / robar objetos y llaves (máx 2 objetos por armería; para llaves hagas ficha valor) |
| PUERTAS_AMARILLO | Pagada | Teletransporta al piso de otro jugador (verde), −1 cordura al objetivo |
| CÁMARA_LETAL | Pagada | Requiere 2 jugadores en la habitación; ritual D6 modula el costo de cordura de cada uno; si se completa mitad una llave (keys_in_hand < keys_total). Costos según dado: (1-2)→[7,0]; (3-4)→[4,3]; (5-6)→[4,3] |
| SALÓN_BELLEZA | Pagada | Te da Protección envuelta +1 ronda; cada 2º uso también VANIDAD |
| MONASTERIO_LOCURA | Pagada | (Presente en el pool; mecánica especial del libro técnico) |

---

## 6. Estado de cordura, estados negativos y derrota

Los estados que se pueden infligir: `TRAPPED`, `TRAPPED_SPIDER`, `MALDITO`, `ENVENENADO`, `PARANOIA`, `STUN`, `VANIDAD`.

**Derrota:** si el total de cordura de TODOS los jugadores está ≤ −4 (`S_LOSS=-5` → todos a −5 o menos). El sacrificio resetea a 0. La cordura puede regenerarse al meditar/en el peep/nas.

**Derrota por llaves:** si quedan en juego (no destruidas) ≤ `KEYS_LOSE_THRESHOLD` (3). Las llaves que se destruyen (regla de descarte del Rey) se restan del "en juego".

---

## 7. La Llave + Umbral (victoria)

- Pool canónico: **6 llaves** → 5 en el mazo de habitaciones + 1 en el mazo de Motemey (`KEYS_TOTAL=6`).
- Llaves por obtener para vencer: **4** (`KEYS_TO_WIN=4`).
- **El Umbral de Amarillo** = pasillo del piso 2 (`UMBRAL_NODE="F2_P"`).
- Para ganar: lleva 4+ llaves hasta el Umbral (cumples `keys_in_hand >= KEYS_TO_WIN`).

### Fase KING (fin de ronda, `engine/systems/king.py`)
- El Rey lanza d4/d6 internos; su daño de presencia está escalado por ronda (empezna en la **ronda 2**).
- Mueve monstruos, rocía los mazos ("cinta de sushi") quizás.
- Chequea victoria/derrota al cierre de cada ronda.
- Un dado del Rey (d6) cuyo parece **6** puede causar descartes de objetos no soulbound, y un d4  puede mover al piso ganador.

---

## 8. Tensión (medidor interno — NO resuelve cartas)

`engine/tension.py` calcula un escalar (equipo:
- objetivo 0.80, banda 0.75–0.85) con 24 características:
  - % de llaves que tengo en mano (`P_keys`)
  - cordura media / máximo (`P_sanity`)
  - cuántos monstruos e peso (`P_mon`)
  - en qué piso está el Rey (riesgo, `P_king_risk`)
  - reinicio, etc.

Úsos:
- Penaliza/potencia la *heurística del Rey* (si la tensión es alta, el Rey pega más).
- Guía a los botones a decidir (meditar vs buscar vs huir del piso del Rey).
- Normalización / reward shaping de RL.

No toca la resolución de cartas. **Las cartas resuelven por `max(0, d6 + cordura_actual)`. Tensión es de lectura, no de regla.**

---

## 9. Desplazamiento de los mazos ("cinta sushi")

En cada fin de ronda, el mazo de una habitación "rota": las cartas de arriba bajan a un hueco. El pend se simula poniendo las cartas del `top` hacia el fondo lentamente, y el mazo de cada habitación pertenece a un "box" fijo (se mezcla internamente). El `DeckState.top` es un puntero espiritual: las cartas consumidas quedan "visibles" en el array pero el frontend debe usar `cards[top:]`.

---

## 10. Discrepancias / anotaciones honestas de relevamiento

1. **Mazo canónico = 107 cartas, no 108.** La suma de `setup_canonical_deck` da 107 (el docstring dice 108), lo que deja la 12ª habitación con 8 cartas y no 9. Discrepancia de fidelidad sin romper el motor (el reparto tolera el resto), pero a corregir si se quiere el regla-canónico exacto.

2. `LOSE_ON_DECK_EXHAUSTION = False` → no hay derrota automática por agotar el mazo.

3. `MAX_ROUNDS=60` → timeout (en simulación; en partida humana no hay límite de ronda salvo los registros).

---

## 11. Ciclo de vida del mazo (qué se consume y qué recicla)

Relevado de `engine/state.py:DeckState` (`top` puntero + `put_bottom`) y de los resolutores
(`cards.py`, `events.py`, `monsters.py`, `omens.py`). El mazo NO es elástico por igual para toda carta.

| Tipo de carta | Al resolver (SEARCH / entrar a habitación) | ¿Regresa al mazo? |
|---|---|---|
| **EVENT / EVENTS** | Se resuelve por `max(0, d6 + cordura)` | **SÍ — vuelve al fondo** (recicla infinito) |
| **OMEN** | D6 + cordura (≤1 vs ≥2) | No — va a la pila de descarte |
| **KEY** (otorgada) | `p.keys += 1` | **NO — se consume** |
| **KEY** (límite lleno / todas repartidas) | Se devuelve | SÍ — `put_bottom` |
| **OBJECT / tesoro / talas / libro** | Se agrega al inventario | No — se consume |
| **CROWN** | Activa Falso Rey (1ª vez) | No — se consume |
| **STATE** | Aplica estado (dur 2, TRAPPED 3) | No — se consume |
| **MONSTER** | Spawn con caso especial | No — se consume |

**Consecuencia (la regla jugable):**
- Los **eventos son el único combustible que recicla** → un mazo nunca vuelve a cero por tener eventos.
- **Llaves, objetos, monstruos, estados y presagios son de UN solo uso**: al resolverse salen del mazo físico permanente.
- Con el tiempo una habitación decae a un mazo compuesto solo por sus eventos, radicándose en círculo.
- Las 5 llaves de mazos + la de Motemey son recursos únicos: cada una robada es definitiva. No hay regeneración de llaves.
- `LOSE_ON_DECK_EXHAUSTION = False` (config): agotar el mazo NO dispara derrota automática. El juego no depende de la pila para terminar — termina por victoria en el Umbral, o por derrota de cordura/llaves.

**Pacing honesto:** la partida es "buscar las llaves entre el ruido infinito de eventos" — los eventos te mantienen presionado (y vivos), los recursos únicos (llaves) son el premio que se va agotando.

---

## 12. Resumen jugable rápido (cheat-sheet)

1. Al inicio: 4 jugadores con roles, todos en pasillos F1/F2; 3 habitaciones especiales ocultas (1 por piso); 6 llaves repartidas en mazos (5 Hab + 1 Motemey).
2. Tu turno: tira las **acciones legales** (mov, buscar, meditar, ojos, especial, habilidad). El Rey luego ataca.
3. Cuando busques una carta de evento: `total = 1d6 + corre_y_actual`; aplica el efecto de la tabla de la carta.
4. La carta vuelve al fondo del mazo.
5. Busca las y logra 4 en el **Umbral de Amarillo (F2_P)** para vencer.
6. Vigila: −5 general → derrota; ≤3 llaves en juego → derrota; cada ronda −1 cordura por la Casa.

---

*Último relevamiento: 2026-08-02 · Repo: ~/.hermes/workspace/ACTIVE/CARCOSA · Motor: engine/ + sim/game_server.py*
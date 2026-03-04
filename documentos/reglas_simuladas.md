# CARCOSA — Reglas simuladas (referencia canon)

Este documento describe exactamente lo que el motor de simulación implementa. Su propósito es permitir comparar la simulación contra las reglas físicas del juego y detectar discrepancias.

---

## TABLERO

- **3 pisos**, cada uno con **4 habitaciones** (R1–R4) y **1 pasillo** (P).
- **15 nodos** en total: F1_R1..F1_R4, F1_P, F2_R1..F2_R4, F2_P, F3_R1..F3_R4, F3_P.
- **Umbral de Amarillo** = pasillo del piso 2 (F2_P).

### Adyacencias (movimiento 1 paso)

Desde una **habitación**:
- Al pasillo de su propio piso.
- A la habitación par: R1↔R2, R3↔R4.

Desde un **pasillo**:
- A las 4 habitaciones de su piso.

No hay conexión directa entre pisos a pie; se usan las escaleras.

### Escaleras

- 1 escalera por piso (3 en total), posicionadas en una habitación aleatoria al inicio.
- Permiten moverse entre pisos adyacentes.
- Al final de cada ronda se **reposicionan** (tiro de d4 por piso).

---

## TURNOS Y RONDAS

### Turno de jugador

- Cada jugador tiene **2 acciones por turno** (salvo modificadores de rol o estado).
- Acciones disponibles: **MOVER, BUSCAR, MEDITAR, DESCARTAR SANIDAD, USAR OBJETO, USAR HABITACIÓN ESPECIAL, FIN DE TURNO**.
- El orden de turno rota jugador a jugador; cuando todos terminan, empieza la **Fase del Rey**.

### Fase del Rey (fin de ronda)

Se ejecuta en este orden exacto:

1. **Casa:** todos los jugadores pierden **1 cordura**.
2. **Ruleta d4:** el Rey se mueve. Se lanza 1d4 y el Rey avanza ese número de pisos (ciclo 1→2→3→1). Si el resultado es el piso del Falso Rey, se relanza hasta que sea distinto.
3. **Presencia del Rey:** los jugadores en el piso donde acaba de llegar el Rey pierden cordura según la ronda *(no aplica en ronda 1)*:
   - Rondas 1–3: **1** de pérdida.
   - Rondas 4–6: **2** de pérdida.
   - Rondas 7–9: **3** de pérdida.
   - Ronda 10+: **4** de pérdida.
4. **Efecto d6 del Rey** (resultado 1–6):
   - **1** — Rotación intra-piso de mazos (R1→R4→R3→R2→R1 por piso).
   - **2** — Todos los jugadores pierden 1 cordura adicional *(excepto los que están en el piso del Falso Rey)*.
   - **3** — El piso del Rey queda con **acción reducida** la siguiente ronda (1 sola acción para quienes estén ahí).
   - **4** — Todos los jugadores son expulsados del piso del Rey *(excepto los del piso del Falso Rey)*.
   - **5** — Todos los jugadores son atraídos al piso del Rey *(excepto los del piso del Falso Rey)*.
   - **6** — Cada jugador descarta su último objeto no-soulbound *(excepto los del piso del Falso Rey)*.
5. **Fase de monstruos:** los monstruos se mueven y actúan.
6. **Efectos de estados al final de ronda** (MALDITO, SANIDAD, ENVENENADO, etc.).
7. **Tick de estados:** cada estado activo pierde 1 ronda de duración; los que llegan a 0 se eliminan.
8. **Chequeo del Falso Rey** (si está activo).
9. **Reposicionamiento de escaleras** (d4 por piso).
10. **Rotación de mazos** (global, ciclo sushi; o intra-piso si d6=1 en paso 4).

---

## CORDURA

- Rango: **−5** hasta el máximo del rol.
- **−5** activa la mecánica de **sacrificio** (ver más abajo).
- Recuperación: meditación, objetos (Vial), estados (SANIDAD).
- El estado **VANIDAD** añade +1 de pérdida extra en cada instancia de daño de cordura.

### Meditación

- En **habitación**: recupera **1 cordura**.
- En **pasillo**: recupera **2 cordura**.
- El Tank puede bloquear la meditación de jugadores en su misma habitación.

### Sacrificio (llegar a −5)

Cuando un jugador llega a −5:
- Puede elegir entre **reducir 1 slot de objeto** o **reducir 1 de cordura máxima** permanentemente (hasta un mínimo de −1 de máximo).
- Mientras el sacrificio está pendiente, el jugador no puede actuar.
- Consecuencias inmediatas: objetos o llaves pueden perderse si exceden los nuevos slots.

---

## LLAVES

- **Pool base:** 6 llaves en juego (5 distribuidas en mazos de habitaciones + 1 en Motemey).
- Si la Cámara Letal completa su ritual, se añade **1 llave extra** al pool (total: 7).
- Cada jugador puede cargar llaves según su rol (1–2 por rol).
- Las llaves son independientes de los slots de objetos.

---

## VICTORIA Y DERROTA

### Victoria

Todos los jugadores están en el **Umbral de Amarillo** (F2_P) **y** entre todos llevan **4 o más llaves**.

### Derrota

Se pierde si ocurre cualquiera de las siguientes:
- **Todos** los jugadores están en −5 de cordura simultáneamente.
- **3 o más llaves** del pool han sido destruidas.

---

## ROLES

| Rol | Cordura máx. | Slots llaves | Slots objetos | Habilidad |
|---|:---:|:---:|:---:|---|
| **Sanador** (HEALER) | 4 | 1 | 2 | Gasta 1 cordura propia → da +2 cordura a otros + elige ILUMINADO o SANIDAD para sí |
| **Tanque** (TANK) | 7 | 1 | 3 | Puede recibir daño en lugar de aliados en su nodo; +1 escudo al inicio de ronda |
| **Apostador** (HIGH_ROLLER) | 5 | 2 | 2 | 1 vez por turno puede lanzar 2d6 y sumar ambos resultados (en lugar de 1d6) |
| **Explorador** (SCOUT) | 3 | 1 | 1 | +1 movimiento gratis adicional; al usar escaleras: si d6+cordura < 3 → STUN |
| **Luchador** (BRAWLER) | 3 | 1 | 2 | Usa el objeto Contundente sin gastar acción; puede reaccionar contra monstruos que lo atacan |
| **Psíquico** (PSYCHIC) | 4 | 1 | 2 | Al entrar a una habitación: ve las 2 cartas superiores y puede reordenarlas |

Todos los roles tienen cordura mínima de **−5**.

---

## OBJETOS

### Objetos normales

| Objeto | Usos | Efecto |
|---|:---:|---|
| **Brújula** | 1 | Mueve al jugador al pasillo de su piso actual (gratis, puede usarse como reacción) |
| **Vial** | 1 | Recupera 2 cordura (puede usarse como reacción) |
| **Contundente** | 1 | Aturde (STUN) a un monstruo en la misma habitación por 2 turnos. El Rey de Amarillo es inmune. Si es un Sirviente de Hielo, lo destruye directamente. Si es un Duende, además hace caer su botín. |
| **Cuerda** | 1 | (efecto por definir) |
| **Escalera Portátil** | 1 | Permite subir o bajar 1 piso |

### Cuentos de Amarillo

Son 4 objetos: **El Reparador de Reputaciones** (`TALE_REPAIRER`), **La Máscara** (`TALE_MASK`), **En la Corte del Dragón** (`TALE_DRAGON`), **El Signo de Amarillo** (`TALE_SIGN`).

- Sin el Libro de Cámaras, los Cuentos son objetos sin efecto.
- Unir un Cuento al Libro **no cuesta acción** (acción gratuita).
- Al unir el N-ésimo Cuento, el Rey queda **desterrado por N rondas**:
  - 1er Cuento → 1 ronda de destierro
  - 2do Cuento → 2 rondas de destierro
  - 3er Cuento → 3 rondas de destierro
  - 4to Cuento (suele venir de Motemey) → 4 rondas de destierro
- **Destierro**: el Rey no activa sus efectos de fin de ronda (d4 de movimiento, presencia, d6), pero La Casa (−1 cordura) sí aplica con normalidad.

### Libro de Cámaras (Soulbound)

**El Libro de Cámaras** (`BOOK_CHAMBERS`) — Al ser revelado por un jugador, se vuelve **soulbound** con ese jugador (no puede descartarse ni perderse). No tiene efecto propio al revelarse; sirve como requisito para unir los Cuentos de Amarillo.

### Libro (Soulbound)

**El Rey de Amarillo** — Soulbound desde el inicio. No puede descartarse ni perderse por sacrificio.

### Tesoros (de Motemey)

| Tesoro | Efecto |
|---|---|
| **Llavero** | Amplia capacidad de llaves |
| **Escaleras Tesoro** | 3 usos de escalera portátil |
| **Pergamino** | (efecto por definir) |
| **Colgante** | (efecto por definir) |
| **Corona** | Soulbound. Activa el **Falso Rey** (ver más abajo) |
| **Anillo** | Al activarse: todos los jugadores recuperan cordura máxima, pero el portador pierde 2 de cordura por turno posterior |

---

## ESTADOS

### Estados con carta propia (duran 2 rondas)

| Estado | Efecto |
|---|---|
| **MALDITO** | Al final de cada ronda, otros jugadores en el mismo piso pierden 1 cordura |
| **SANIDAD** | Recupera 1 cordura al final de cada turno (propio y ajenos). Puede descartarse gratis para eliminar **todos** los estados (positivos y negativos) |
| **ENVENENADO** | Pierde 1 de cordura máxima al final de cada ronda. ⚠️ La reducción es **permanente** incluso cuando el estado expira |
| **PARANOIA** | No puede estar en el mismo nodo que otro jugador. El movimiento hacia nodos ocupados está bloqueado |

### Estados por efectos

| Estado | Origen | Duración | Efecto |
|---|---|:---:|---|
| **VANIDAD** | Salón de Belleza (cada 2ª activación) | 2 rondas | +1 cordura perdida adicional en cada daño recibido. Bloquea usar el Salón de Belleza |
| **ILUMINADO** | Capilla u otros efectos | 2 rondas | +1 acción disponible (3 en total) |
| **ATURDIDO** (STUN) | Contundente, escape de trampa | 2 turnos (Contundente) / 1 turno (escape) | El monstruo no puede actuar. El Rey de Amarillo es inmune; la Reina Helada no |
| **ATRAPADO** (TRAPPED) | Araña, Viejo del Saco | 3 turnos | No puede actuar. Cada turno intenta escape: lanza 1d6 (HIGH_ROLLER puede sumar 2d6) + cordura ≥ 3. Si falla, pierde el turno. Al escapar, el monstruo fuente queda STUN 1 turno |
| **MOVIMIENTO BLOQUEADO** | Reina Helada (al entrar) | 1 turno | No puede moverse. Puede usar 2 acciones de otro tipo |
| **ACCIÓN REDUCIDA** | Reina Helada (turnos siguientes) | Mientras la Reina esté en el piso | Solo 1 acción disponible |

---

## MONSTRUOS

| Monstruo | Comportamiento |
|---|---|
| **Araña** | Al revelar: aplica ATRAPADO (3 turnos) al jugador que la revela |
| **Baby Spider** | Al revelar: aplica STUN 1 turno al jugador que la revela |
| **Duende (Goblin)** | Al aparecer: roba objetos o llaves del jugador en su habitación. Si tiene botín, huye |
| **Viejo del Saco** | Atrapa jugadores (TRAPPED) y los arrastra consigo al moverse |
| **Reina Helada** | Al entrar en juego: aplica MOVIMIENTO BLOQUEADO a jugadores presentes. Mientras esté en un piso: todos en ese piso tienen ACCIÓN REDUCIDA. Puede ser stuneada |
| **Sirviente de Hielo** | Limita a 1 acción a jugadores en su piso. El Contundente lo destruye directamente |
| **Tue-Tue** | Nunca hace spawn físico. Evento progresivo: 1ª vez −1 cordura al revelador; 2ª vez −2 cordura; 3ª vez en adelante: fija la cordura del revelador en −5 |
| **Rey de Amarillo** | Jefe principal. Inmune al STUN. Ver Fase del Rey |

---

## HABITACIONES ESPECIALES

Al inicio del juego se colocan **3 habitaciones especiales** (una por piso), elegidas aleatoriamente entre los tipos disponibles. Están boca abajo hasta que un jugador entra por primera vez.

Un monstruo puede destruir una habitación especial al ocupar su posición.

### Taberna (FREE — sin coste de acción)

- Permite ver las 2 cartas superiores de los mazos de 2 habitaciones elegidas.
- Solo puede usarse **una vez por turno** (por toda la mesa).

### Motemey (FREE — sin coste de acción)

- Compra: el jugador paga **2 cordura**, roba 2 cartas del mazo Motemey y elige quedarse con 1.
- Venta: puede devolver un objeto de su inventario al mazo Motemey.
- El mazo Motemey incluye tesoros y llaves.

### Armería (FREE — sin coste de acción)

- Almacenamiento compartido con capacidad para **2 objetos**.
- Permite dejar o tomar objetos (incluyendo llaves).
- Los objetos soulbound no pueden dejarse.

### Puertas de Amarillo (PAID — cuesta 1 acción)

- El jugador que la activa se teleporta a la habitación de otro jugador elegido.
- El jugador **destino** (el que ya estaba allí) pierde **1 cordura**.
- El activador no paga cordura adicional.

### Cámara Letal (PAID — cuesta 1 acción)

- Ritual: requiere la participación de los jugadores en la habitación.
- Si el ritual tiene éxito: se añade **1 llave extra** al pool (de 6 a 7).
- El ritual solo puede completarse **una vez** por partida.

### Salón de Belleza (PAID — cuesta 1 acción)

- Global: lleva un contador de activaciones totales (de cualquier jugador).
- Cada **2ª activación** (2ª, 4ª, 6ª…) aplica el estado **VANIDAD** al jugador que la activa.
- Los jugadores con VANIDAD activa **no pueden** activar el Salón de Belleza.

### Monasterio a la Locura

- En el pool de habitaciones especiales pero su mecánica aún está en definición.

---

## FALSO REY

Se activa cuando un jugador obtiene la **Corona** (tesoro soulbound de Motemey).

- El portador de la Corona define la posición del Falso Rey: su piso.
- El Rey de Amarillo **no puede** caer en el piso del Falso Rey (el d4 se relanza).
- Los jugadores en el piso del Falso Rey **no son afectados** por los efectos de d6 del Rey (expulsión, atracción, pérdida de cordura por d6=2, descarte por d6=6).
- Al final de cada ronda, el Falso Rey hace su propio **chequeo de presencia**: se lanza 1d6 + cordura del portador; si el resultado ≤ umbral (que aumenta con las rondas), todos los jugadores en el piso del Falso Rey pierden cordura según la tabla de presencia del Rey.

---

## ROTACIÓN DE MAZOS

Cada habitación tiene asociado un "mazo" (box) con cartas que se van revelando al buscar.

- Al final de cada ronda: los mazos rotan en **ciclo global** entre habitaciones siguiendo un orden fijo que cruza pisos.
- Si el d6 del Rey resulta en 1: en cambio se hace una **rotación intra-piso** (R1→R4→R3→R2→R1 dentro de cada piso, sin cruzar pisos).

---

## ACLARACIONES PENDIENTES DE CANON

Las siguientes mecánicas están referenciadas en el código pero sin definición completa aún:

- Mecánica exacta del **Monasterio a la Locura**.
- Efecto completo del **Pergamino** y el **Colgante** (tesoros).
- ~~Mecánica completa de los **Cuentos de Amarillo** y el **Libro de Cámaras**.~~ *(implementado — ver sección Objetos)*
- Comportamiento completo del **Anillo** tras su activación.
- ~~Habilidad completa del **Sanador**.~~ *(implementado — estado actual es el canon)*

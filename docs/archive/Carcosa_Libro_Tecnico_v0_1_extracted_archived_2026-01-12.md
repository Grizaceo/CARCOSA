# Carcosa — Libro Técnico de Reglas (orientado a código)

> Versión extraída automáticamente desde el PDF `Carcosa_Libro_de_Reglas_Tecnico_v0_1.pdf`.

> Recomendación: mantener este archivo en el repositorio (por ejemplo `docs/`) para consulta por el agente.

> Nota: el PDF original tiene tablas/columnas; la extracción puede perder formato visual, pero conserva el texto.


---

## Página 1

Carcosa — Libro Técnico de Reglas (orientado a
código)
Versión v0.1 | Generado desde documentos del proyecto (enero 2026)
Este documento consolida las reglas vigentes de Carcosa en un formato operativo para
implementación en motor, simulador y pruebas automatizadas. Cuando una regla permanece
ambigua o contradictoria entre fuentes, se marca explícitamente como PENDIENTE o como
PARÁMETRO de configuración.
Fuentes principales
Carcosa - Análisis y especificación juego
(consolidado) + Manual/Documento base
(Proyecto Diplomatura) + material de
proyecto (tablero/rotación).
Objetivo de implementación
Motor determinista con soporte de
aleatoriedad vía RNG seed; luego simulación
para balance y búsqueda (MCTS/expectimax).
Alcance
Turnos, acciones, movimiento, mazos,
habitaciones especiales, Rey de Amarillo,
monstruos, estados, victoria/derrota.

---

## Página 2

1. Modelo conceptual y términos
Carcosa es un juego cooperativo por rondas. Cada jugador controla una “Pobre Alma” con
recursos de Cordura y capacidad de inventario. El tablero es un grafo
(habitaciones/pasillos/escaleras) y el estado del mundo se actualiza por turnos y por una
resolución obligatoria al final de cada ronda.
1.1 Entidades núcleo (para el motor)
-
Jugador (Pobre Alma): id, rol, cordura_actual, cordura_max, ubicacion, inventario_objetos
(capacidad), inventario_llaves (capacidad), flags (false_king, secuestrado, etc.).
-
Tablero: nodos (habitaciones y pasillos por piso) y aristas (movimiento normal y escaleras
condicionadas).
-
Mazos de habitación (12): cada uno vive dentro de una “Caja de Movimiento” asociada a un
slot de habitación; el mazo rota entre slots según la cinta global.
-
Cartas: Evento, Objeto, Llave, Monstruo, Estado, Presagio, Libro, Cuento, Tesoro, Habitación
Especial.
-
Rey de Amarillo: posición (piso + pasillo), estado de destierro (vanish), tabla de daño base
por ronda, efecto global por d6.
-
Monstruos: fichas persistentes en tablero; lógica de movimiento y activación por fin de
ronda.
-
Estados alterados: efectos con duración finita (en rondas) y triggers (principalmente fin de
ronda).
-
DPS (rol): único habilitado para Reacción sobre monstruos (ventana específica).
1.2 Convención de tiempos y fases
Fase de Ronda: Turnos de jugadores (en orden) → Resolución de Fin de Ronda (orden fijo). Regla
de referencia: “Ronda” se cumple cuando todos los jugadores jugaron 1 turno (relevante para
duraciones de estados).
1.3 Aleatoriedad reproducible
Todo lanzamiento de dados y barajado debe consumir el RNG del motor (seed). Esto permite
simulación y depuración. Se recomienda exponer un “log de RNG” opcional.

---

## Página 3

2. Tablero, nodos y movimiento
El tablero contiene 3 pisos. En cada piso hay 4 habitaciones y 1 pasillo. Convención: F{floor}
_R{1..4} y F{floor}_PAS. La numeración de habitaciones es fija: 1=arriba-izquierda, 2=arriba-
derecha, 3=abajo-derecha, 4=abajo-izquierda.
2.1 Adyacencias y coste de movimiento
-
Toda habitación conecta con el pasillo de su piso en 1 movimiento.
-
Conexiones directas adicionales: R1 ↔ R2 y R3 ↔ R4 (1 movimiento).
-
Cruces izquierda↔derecha fuera de esas conexiones requieren pasar por el pasillo
(habitualmente 2 movimientos).
2.2 Escaleras (estado por piso)
Existe exactamente 1 escalera por piso. Se representa como la habitación Rk (k {1..4}) de ese
piso que contiene la escalera en la ronda vigente. Al final de cada ronda se reubica con 1 tirada
de d4 por piso.
Estado mínimo sugerido:
stairs_room[1]  {1..4}
stairs_room[2]  {1..4}
stairs_room[3]  {1..4}
Uso: para cambiar de piso, el jugador debe estar en la habitación que contiene la escalera en su
piso actual. En piso 1 no se puede “bajar” y en piso 3 no se puede “subir”; el intento es inválido.
2.3 Mapeo d4 → habitación
Convención fija para setup y reposicionamientos: d4=1→R1, 2→R2, 3→R3, 4→R4.

---

## Página 4

3. Preparación de partida (setup)
La preparación debe ser determinista salvo por barajados y tiradas explícitas. Toda información
oculta (cartas boca abajo) se conserva en el estado del motor.
3.1 Colocar Rey, Santuario y Corona
-
Existe SANCTUARY_YELLOW como ubicación fija marcada en el tablero.
-
El Rey de Amarillo inicia en el piso del Santuario.
-
En Ronda 1 no se aplica la pérdida de cordura causada por el Rey verdadero (solo esa).
-
La Corona de Amarillo inicia en el Santuario.
3.2 Habitaciones especiales
Se barajan cartas de Habitación y se roban 3 (una por piso). Por cada piso, se tira d4 para elegir
la habitación. Se colocan boca abajo y se revelan al entrar por primera vez. Permanecen en
juego salvo regla de la habitación. Nota de proyecto: las habitaciones especiales se “gastan” por
usos (no por rondas) cuando su regla así lo indique; un monstruo al entrar puede destruir solo el
efecto especial, dejando la habitación como normal.
3.3 Mazos de habitación (12) y composición
Se preparan 12 mazos de habitación. Cada mazo contiene 9 cartas: 4 Eventos, 2 Objetos y 3
Variables. Las cartas variables provienen de un pool (Estados, Monstruos, Presagios, Llaves,
Libro, Cuentos, Tesoros) según el manual.
Cada mazo se baraja individualmente y se coloca en una Caja de Movimiento asociada a una
habitación (slot).
3.4 Escaleras (setup inicial)
Se realizan 3 tiradas de d4 (una por piso) para ubicar la escalera inicial de cada piso.

---

## Página 5

4. Turno de jugador
En su turno, cada jugador dispone de 2 acciones. Puede repetir acciones y puede decidir no usar
ambas.
4.1 Acciones disponibles
-
Moverse
-
Buscar
-
Meditar
-
Usar Objeto Contundente
-
Acción de Habitación
-
Acciones Gratuitas
-
Intercambio (gratis, si están en el mismo nodo)
4.2 Movimiento y revelación
Al moverse a otra habitación, se revela la primera carta del mazo de la habitación (caja/slot
actual) y se resuelve inmediatamente. Buscar revela 1 carta adicional del mismo mazo y la
resuelve. Al entrar a un pasillo por efecto, el jugador puede usar la mecánica de “mirar” una
carta contigua sin activarla y devolverla al tope boca abajo (si la regla aplica).
4.3 Intercambio
Si dos o más jugadores están en la misma habitación o pasillo, pueden intercambiar libremente
objetos y llaves sin costo de acciones. Excepción: la Corona de Amarillo no puede intercambiarse
y no puede desprenderse del portador.

---

## Página 6

5. Cartas: ciclo de vida y reglas generales
Regla general de destino de cartas:
-
Eventos: tras resolverse vuelven al fondo de su mazo.
-
Objetos, Llaves, Tesoros: si pasan a inventario o se consumen, se remueven del mazo y van a
descarte o eliminación (según tipo).
-
Monstruos: al revelarse, se invoca ficha en tablero; la carta de monstruo se descarta (salvo
regla distinta).
-
Si no se puede determinar con seguridad el mazo de origen de una carta, se descarta.
Inventario: llaves ocupan slots de llavero; objetos/tesoros ocupan slots de objeto. Si no hay
espacio, el jugador elige qué descartar/quedarse.

---

## Página 7

6. Fin de Ronda (resolución obligatoria)
Tras terminar todos los turnos, se ejecuta la resolución de Fin de Ronda en orden fijo. Si el Rey
está desterrado (vanish), se omite todo el bloque del Rey.
Paso
Bloque
Descripción operativa
1
Casa
Todas las Pobres Almas
pierden 1 de cordura (salvo
inmunidades).
2
Rey (daño por presencia)
Pobres Almas en el piso del
Rey pierden cordura según
tabla por ronda. En Ronda 1
esta pérdida no aplica.
3
Rey (ruleta d4)
La Pobre Alma que inició la
ronda tira d4 y el Rey se
manifiesta en el piso
resultante según ruleta;
aparece en el pasillo.
4
Rey (efecto d6)
La misma Pobre Alma tira d6
y aplica 1 efecto global (1–6).
5
Monstruos
Se activan todos los
monstruos; ventana de
Reacción del DPS antes del
efecto del monstruo.
6
Estados y checks
Se resuelven todos los
efectos “al final de la ronda”
(incluye venenos, estados y
check del Falso Rey).
7
Escaleras
Se tiran 3 d4 (uno por piso)
para recolocar escaleras.
8
Rotación de mazos
Se rota la posición de las
Cajas de Movimiento según
la cinta global acordada.

---

## Página 8

6.1 Tabla de efectos d6 del Rey (bloque 4)
Al aplicar el efecto del Rey (d6 puro):
d6
Nombre
Efecto
1
Barajar
Baraja todos los mazos de
habitación (cada mazo
individual).
2
−1 cordura global
Todos los jugadores pierden
1 cordura adicional.
3
1 acción
Los jugadores en el piso del
Rey solo disponen de 1
acción en su siguiente turno.
4
Mover por escalera (antes:
‘expulsar’)
Todos los jugadores del piso
del Rey se mueven a la
habitación con escalera más
cercana en pisos contiguos
(definición exacta en §6.2).
5
Atraer
Todos los jugadores son
colocados en el pasillo donde
se encuentra ubicado el Rey
(con excepción de
inmunidades por Falso Rey).
6
Descartar objeto
Cada jugador descarta 1
objeto (si tiene).
6.2 Definiciones exactas: Atraer y ‘Expulsar’
Atraer: mover a todos los jugadores al PASILLO del piso del Rey. Excepción: el Falso Rey y los
jugadores en su piso no son atraídos.
Mover por escalera (antes ‘expulsar’): mueve a los jugadores del piso del Rey al piso contiguo
mediante la escalera más cercana. Interpretación vigente: si están en piso 1 van a la escalera del
piso 2; si están en piso 3 van a la escalera del piso 2; si están en piso 2 van a la escalera del piso
1. El Rey, en cambio, es ‘expulsado/banisheado’ al Santuario cuando un efecto lo destierra.

---

## Página 9

7. Santuario, Corona, Libro y Falso Rey
7.1 Corona y Falso Rey: obtención y restricciones
-
En el Santuario, un jugador puede gastar 1 llave (de su inventario) para obtener la Corona.
-
Quien obtiene la Corona pasa a ser el Falso Rey.
-
La Corona no ocupa slot de objeto y no puede soltarse (no se intercambia, vende, descarta
ni destruye).
7.2 Efectos persistentes del Falso Rey
-
Bloqueo de manifestación: el Rey verdadero no puede manifestarse en el piso del Falso Rey;
si la ruleta da ese piso, se repite hasta que sea distinto.
-
Inmunidad al Atraer: el Falso Rey y las Pobres Almas en su piso no son afectadas por Atraer.
-
Check de fin de ronda: al Final de cada ronda, el Falso Rey puede gatillar un efecto del Rey
verdadero en su piso; tirada estándar total = d6 + cordura_actual (clamp mínimo 0). Umbral
inicial = cordura_max + 2; el umbral requerido aumenta +1 cada ronda posterior.
Resultado del check: si total > umbral, no ocurre nada; si total <= umbral, se aplica solo la
pérdida de cordura del Rey verdadero en el piso del Falso Rey.
7.3 Libro y Cuentos de Amarillo (destierro del Rey)
El Libro es un objeto especial que no ocupa slot y no puede intercambiarse/robarse/destruirse.
Hay 4 Cuentos de Amarillo: 3 en mazos comunes y 1 en el mercader (coste: 4 cordura). Si un
jugador distinto al portador del libro obtiene un cuento, debe entregarlo al portador para que
surta efecto. Los cuentos no ocupan slot.
Al anexar Cuentos al Libro, el Rey es desterrado (vanish) al Santuario por N rondas (N=1,2,3,4
según cuento anexado). Mientras esté desterrado, se omite todo el bloque del Rey en Fin de
Ronda (pérdidas y d6).
Timing operativo (según explicación del proyecto): si el destierro se activa durante una ronda,
afecta el Fin de Ronda inmediato y, adicionalmente, cubre las rondas completas siguientes
según N. Se recomienda modelar el destierro como un contador de “fines de ronda a omitir”.

---

## Página 10

8. Monstruos
Los monstruos se encuentran dentro de los mazos y spawnean al ser revelados por un jugador.
Una vez en tablero, persisten como ficha. Pueden coexistir con jugadores en la misma
habitación.
8.1 Ventana de Reacción (DPS)
Solo el rol DPS puede reaccionar al intentar activarse el efecto de un monstruo. La reacción
ocurre antes del efecto del monstruo, no cuesta acción y requiere un objeto utilizable. Es 1
reacción por monstruo; el DPS debe estar en la misma habitación del monstruo.
Aturdimiento por objeto: aturdimiento normal dura 1 ronda; mientras está aturdido, bloquea el
efecto de esa interacción y su movimiento en el paso de monstruos.
8.2 Movimiento y efectos por tipo (resumen)
Monstruo
Regla resumida
Araña de Amarillo
Se mueve 1 espacio hacia la Pobre Alma más
cercana. Si la alcanza, la aturde por 3 rondas.
Reina Helada
No se mueve.
Tue-Tue
Movimiento no definido en el documento
base; existe regla especial global de ‘tercer
Tue-Tue’ (ver §9.3).
Duende de Amarillo
Se mueve 1 espacio lejos de la Pobre Alma
más cercana. Si alcanza a una Pobre Alma,
roba todos sus objetos y llaves y se aleja; su
ficha se reposiciona a la habitación más
lejana al jugador afectado.
Viejo del Saco
Se mueve 1 espacio lejos de la Pobre Alma
más cercana. Si alcanza a una Pobre Alma, la
secuestra y se aleja; rescate: estar en su
habitación y gastar 1 acción.

---

## Página 11

9. Estados alterados
Los estados alterados se aplican a jugadores y típicamente se resuelven en el Fin de Ronda (paso
6). Duración estándar confirmada para la mayoría: 2 rondas. Sanidad se renueva si se reaplica
antes de expirar.
Envenenado: afecta la cordura máxima (no se anula por protecciones que solo evitan pérdida de
cordura actual) y puede apilarse, reduciendo 2 de cordura máxima por doble envenenamiento.
9.1 Regla de −5 cordura (derrota funcional)
Al llegar a −5:
-
Destruye todas sus llaves.
-
Destruye todos sus objetos.
-
Las demás Pobres Almas pierden 1 cordura.
-
El jugador queda con 1 acción por turno mientras permanezca en −5; al subir a −4 vuelve a 2
acciones.
Existen propuestas alternativas de “sacrificio” en documentos de diseño; en esta versión técnica
se mantienen como opcionales hasta cierre.
9.2 Anti-loop
Se detecta loop por patrón de habitaciones. Disparo: 3 ciclos completos (no cuenta pasillo ni
cambios de piso por escalera). Sanción: termina turno y fija cordura a −5 aplicando
consecuencias.
9.3 Regla global de Tue-Tue (tercer evento)
El tercer Tue-Tue revelado a lo largo de la partida deja en −5 al jugador que lo revela. Esta regla
es global entre todos los jugadores.

---

## Página 12

10. Condiciones de término
10.1 Victoria (cooperativa)
Al Final de Ronda, simultáneamente:
-
El grupo posee ≥ 4 llaves en total.
-
Todas las Pobres Almas están en el Umbral de Amarillo (pasillo del primer piso).
10.2 Derrota
-
Todas las Pobres Almas están en −5 de cordura.
-
Quedan únicamente 3 llaves “en juego” (requiere definición operativa; ver §11).
11. Puntos abiertos para completar el motor
-
Tabla de daño base del Rey por ronda (mencionada como existente).
-
Definición exacta de ‘llaves en juego’ para la condición de derrota por llaves.
-
Composición determinista del mazo del Mercader/Buhonero (qué vende, cómo aparece,
etc.).
-
Catálogo completo de textos de cartas (Eventos, Objetos, Estados, Presagios, Tesoros) para
completar el Excel de entidades.

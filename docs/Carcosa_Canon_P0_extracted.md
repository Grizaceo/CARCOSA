# Canon operativo para implementación P0 (extraído del Libro Técnico v0.1)

> Este extracto está pensado para ser usado como “fuente de verdad” por un agente en VS Code al implementar el backlog P0.

> Si alguna cifra o regla aparece incompleta en el documento (por ejemplo, tabla de daño por presencia del Rey), parametrizar en `Config` y registrar en `NOTES.md`.


## 2. Movimiento y tablero

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

---PAGE 4---


## 6. Fin de Ronda y definiciones relevantes (P0)

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

> [!NOTE] **VARIANTE ENGINE (2026-01-23):**
> En este engine se implementa como **rotación intra-floor** (R1→R4→R3→R2→R1 por piso) en lugar de shuffle.
> **Razón:** En el juego físico, barajar todos los mazos manualmente es tedioso y propenso a errores.
> Este proyecto busca ser una representación estricta del juego físico para simulaciones, por lo que se optó
> por una mecánica que logra el mismo efecto de "reorganizar cartas" sin la fricción del shuffle físico.
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

---PAGE 9---


## 9.1 Regla de −5 cordura

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

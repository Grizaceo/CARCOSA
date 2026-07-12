# HALI — motor de representación 2.5D para CARCOSA

> *"Along the shore the cloud waves break… the twin suns sink behind the lake."*
> HALI es el lago a través del cual se ve Carcosa: un motor de render isométrico
> ad hoc, escrito desde cero en Canvas 2D sin dependencias, con dirección de arte
> Robert W. Chambers (*El Rey de Amarillo*, 1895). 100 % reproducible en local:
> ni CDNs, ni assets externos, ni servicios de terceros.

## Qué hace

- **Jugar**: crea partidas contra los bots del server local (o con amigos por
  asientos remotos), mueve con click en el tablero y actúa con la botonera de
  acciones legales. Las reglas viven SOLO en el engine Python (`/legal` +
  `step()`); este cliente jamás decide legalidad.
- **Guardar**: cualquier partida (terminada o parcial) se guarda en el server
  (`runs/human_*/human.jsonl`, o PostgreSQL si hay `DATABASE_URL`).
- **Reproducir**: cualquier jsonl del simulador —headless o humano— se ve como
  replay con timeline, velocidades y paso a paso. El destilado corre también en
  JS, así que el ciclo jugar → guardar → reproducir se cierra en el navegador.

## Arranque rápido (todo local)

```bash
make hali-serve          # game_server en http://127.0.0.1:8765
# abrir http://127.0.0.1:8765/static/hali/
```

En el panel **Partida**: elige quién ocupa cada asiento (yo / bot / amigo),
opcionalmente una seed, y *Crear y jugar*. Para que un amigo entre desde otro
navegador: compártele el `game_id`, él pulsa *Conectar* y *Reclamar* su asiento.

**Guardar y re-ver**: botón *Guardar partida* (abajo a la izquierda) en
cualquier momento; al terminar la partida se guarda sola. La sección
*partidas guardadas* lista lo almacenado (`GET /games`) y un click abre el
replay. También puedes arrastrar cualquier `.jsonl`/`.json` sobre la ventana.

## Build autocontenido (un solo archivo)

```bash
make hali-dist           # → dist/hali_standalone.html (~215 KB)
```

Ese HTML único funciona abierto directamente desde el disco (`file://`):
trae la demo embebida y, si el server local está corriendo, también permite
crear y jugar partidas apuntando a `http://127.0.0.1:8765`. Para empaquetar
una partida concreta como archivo compartible solo-replay:

```bash
python3 tools/distill_replay.py runs/<mi_partida>.jsonl -o /tmp/mi_replay.json
python3 tools/build_hali_standalone.py --no-live --replay /tmp/mi_replay.json -o dist/mi_partida.html
```

Regenerar la demo desde cero (simulador headless → replay):

```bash
make hali-demo-replay
```

## Modos y fuentes de datos

| Fuente | Cómo llega | Uso |
|---|---|---|
| Partida en vivo | `/start` `/claim` `/state` `/legal` `/act` `/save` + WS | jugar u observar |
| Partida guardada | `GET /games` + `GET /games/{id}/download` (jsonl) | re-ver desde el panel |
| jsonl del runner | `tools/distill_replay.py` o arrastrar el archivo | visualizar partidas de bots |
| Replay embebido | `tools/build_hali_standalone.py --replay …` | demo autocontenida |

## Controles

- **arrastrar** mover cámara · **rueda** zoom · **click en sala iluminada** mover
- **0–3** enfocar piso (0 = todos) · **espacio** play/pausa · **←/→** paso a paso

## Arquitectura

```
js/hali-core.js   proyección isométrica 2:1, cámara, tweens, picking, bucle
js/hali-art.js    paleta y pintura procedural (fondo, pisos, piezas, FX, Señal)
js/hali-data.js   destilador jsonl→frames, adaptador /state, LiveClient
js/hali-main.js   orquestación, HUD, lobby, timeline, barra de acciones
```

El frame normalizado es el único contrato entre datos y render; agregar una
fuente nueva (p. ej. un stream de entrenamiento RL) es escribir un adaptador.

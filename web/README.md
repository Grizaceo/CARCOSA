# CARCOSA — Playtest Web (frontend canónico)

Este directorio es **el frontend oficial** del playtest HTML. Lo sirve `sim/game_server.py`
(el servidor canónico, en la raíz del repo). `docs/playtest-html/` es una copia antigua, no usar.

## Jugar en local (tú + amigo en la misma red o con túnel)

```bash
# desde la raíz del repo
uvicorn sim.game_server:app --host 0.0.0.0 --port 8765
```

1. **Host**: abre `http://localhost:8765/`. Configura los 4 asientos:
   - **YO** = ese asiento lo controlas tú en este navegador (puedes marcar varios → hotseat).
   - **AMIGO** = asiento humano reservado para quien se una con el link.
   - **BOT** = lo juega la IA del servidor.
   Elige modo de roles (RANDOM_UNIQUE es el canónico) y crea la partida.
2. **Amigo**: abre el link compartido (`http://<ip-del-host>:8765/?game=<id>`), pulsa
   **Unirse** y elige su asiento. El servidor bloquea que dos navegadores controlen el
   mismo asiento (claim por `client_id`).
3. El turno del actor activo solo muestra acciones en el navegador que controla ese
   asiento; el resto ve "Esperando a...". El Rey y los bots los resuelve el servidor.

En producción (Render/Fly/Railway) es igual: el host comparte la URL pública con `?game=<id>`.

## Reglas / fuente de verdad

La UI **no** implementa reglas: todas las acciones vienen de `GET /legal` y el engine
(`engine/`) valida cada acción en `POST /act`. Si un botón aparece, es legal; si el
engine lo rechaza, la UI muestra el motivo. La interrupción de **sacrificio** (caer a -5)
cambia el actor activo al jugador afectado y ofrece exactamente las opciones del engine.

## Registro de partidas (para saber qué funciona y qué no)

- Al terminar una partida el servidor **guarda automáticamente** el registro completo
  (JSONL, una transición por línea) en PostgreSQL si hay `DATABASE_URL`, o en
  `runs/human_<fecha>_seed<seed>_<game_id>/human.jsonl` + índice `runs/human_games_index.jsonl`.
- `GET /games` — lista de partidas jugadas (outcome, rondas, jugadores humanos, seed).
- `GET /games/<id>/download` — descarga el JSONL de una partida.
- Las sesiones activas se respaldan en `runs/active_sessions/` y sobreviven reinicios
  del servidor (expiran tras 6 h de inactividad).

## Recuperación y rescates

- **F5 / cierre del navegador**: al volver a abrir la página se reconecta automáticamente
  a la partida activa con tus mismos asientos (claims del servidor por `client_id`).
- **Salir**: libera tus asientos en el servidor para que otro navegador pueda tomarlos.
- **Amigo ausente / sesión perdida**: cuando es el turno de un asiento humano que nadie
  controla, la UI ofrece "🎮 Tomar control"; también el seat picker permite forzar un
  asiento ocupado (modelo de confianza entre amigos).
- **Caída del servidor / WS**: reconexión con backoff y, si se agota, polling de `/state`
  cada 5 s hasta recuperar el tiempo real. Las sesiones restauradas reanudan el bucle de
  bots automáticamente al arrancar el servidor.

## Limitación conocida (información oculta)

El estado que reciben los clientes incluye el contenido de los mazos (se usa para
inferir cartas reveladas en la bitácora). Un jugador con DevTools podría ver cartas no
reveladas. Para un playtest cooperativo entre amigos es aceptable; si algún día importa,
habría que mover la inferencia de reveals al servidor y censurar `deck.cards`.

## Endpoints útiles

| Endpoint | Descripción |
|---|---|
| `GET /health` | estado del servidor, sesiones activas, DB |
| `GET /setup_preview/{seed}` | preview real del setup (habitaciones especiales + roles) |
| `POST /claim` | reclamar asiento(s) para un navegador |

# Plan: HTML Canvas Playtest Client para CARCOSA

Branch: `feat/html-canvas-playtest`

## 1. Grounding — ¿Qué necesitamos?

### Servidor existente (`sim/game_server.py`)
- FastAPI corriendo en `0.0.0.0:8765`
- Endpoints ya funcionales:
  - `POST /start` — inicia partida (humanos y bots)
  - `GET /state/{id}` — estado actual
  - `GET /legal/{id}/{actor}` — acciones legales
  - `POST /act` — ejecutar acción
  - `WS /ws/{id}/{pid}` — push de cambios de estado
  - CORS abierto (`*`)
- Ya soporta **multi-jugador humano + bots**: defines `players`, los demás son bots automáticos
- Persistencia: POST /save/{id} → JSONL compatible con pipeline BC

### State summary devuelto por la API
```json
{
  "game_over": false,
  "outcome": null,
  "round": 1,
  "phase": "EXPLORE",
  "active_actor": "P1",
  "players": {
    "P1": {
      "sanity": 5, "sanity_max": 8,
      "keys": 0,
      "room": "F1_R2",
      "objects": [],
      "role_id": "medium",
      "statuses": [],
      "remaining_actions": 3
    }
    // ... P2, P3, P4
  },
  "monsters": [
    {"id": "M1", "room": "F1_R5", "floor": 1}
  ],
  "king_floor": 1
}
```

### ¿Qué falta del lado servidor?
- **Casi nada.** El servidor ya expone todo lo necesario.
- Solo necesitamos un `GET /actions/{game_id}/{actor}` que devuelva las acciones legales **formateadas para UI** (tipo + data descriptiva). El endpoint `/legal/{id}/{actor}` ya existe y devuelve actions con type y data.

### ¿Qué necesitamos del lado cliente?
- **HTML + Canvas + JavaScript vanilla** (sin framework, sin bundler)
- Conexión HTTP para /start, /state, /legal, /act
- Conexión WebSocket para push de estado (opcional, podemos poll)
- Renderizado 2D del tablero (canvas)
- Interfaz de acciones (botones)
- Soporte hot-seat para 2 jugadores en la misma máquina

## 2. Arquitectura del cliente HTML

```
docs/playtest-html/
├── index.html              # Entry point, layout
├── css/
│   └── style.css           # Estilos retro/oscuros, responsivo
├── js/
│   ├── main.js             # Orquestador, ciclo de juego
│   ├── api.js              # Llamadas HTTP al servidor + WS
│   ├── renderer.js         # Canvas 2D: tablero, fichas, monstruos
│   ├── actions.js          # Panel de acciones legales
│   ├── state.js            # Estado local, transiciones
│   └── components.js       # Mini-componentes: chat, log, info panel
└── README.md               # Cómo usarlo
```

### Flujo de juego (hot-seat)
1. Abrir `index.html` → lobby: elegir seed, cantidad de jugadores humanos
2. POST /start → recibir game_id + estado inicial
3. Renderizar tablero en canvas + info de jugadores
4. GET /legal/{game_id}/{actor} → mostrar acciones disponibles como botones
5. POST /act con la acción elegida → recibir nuevo estado
6. Si el siguiente actor es humano (misma máquina), mostrar su turno
7. Si es bot, el servidor avanza solo (ya implementado)
8. Repetir hasta game_over
9. POST /save → guardar partida como JSONL

## 3. ¿Qué tan factible?

**Altamente factible.** Datos concretos:

- **Servidor:** no requiere cambios. CORS ya abierto, endpoints completos, auto-advance de bots implementado.
- **API surface:** 5 endpoints HTTP + 1 WebSocket. Mínimo.
- **Payload del state:** ~1-2KB por request. Liviano.
- **Renderizado:** el tablero de CARCOSA es cuadrícula de habitaciones (F1_R1..R9, F2_R1..R9, etc.). Canvas 2D con rectángulos y texto es suficiente.
- **Complejidad:** media-baja. Más lógica de UI (mostrar acciones, manejar turnos) que lógica de juego (ya en el servidor).
- **Hot-seat:** el servidor ya soporta `human_ids`. Solo hay que rotar el input local.

### Riesgos y mitigaciones
| Riesgo | Mitigación |
|--------|-----------|
| Estado muy grande para renderizar | El `_state_summary` ya es compacto. Si falta algo, agregar campos al servidor (es cambio trivial) |
| Acciones legales complejas | El endpoint `/legal` ya las devuelve. El cliente solo las lista como botones |
| WebSocket como single point of failure | Polling cada 2s como fallback. El servidor es stateless para GET /state |
| Múltiples pestañas/ventanas | Cada pestaña crea su propio game_id. No hay conflicto |
| Conexión entre amigos (LAN/internet) | Servidor expuesto con `--host 0.0.0.0`. El cliente se conecta a `server_url` configurable |

## 4. Plan de implementación (fases)

### Fase 1: Esqueleto funcional (2-3 horas)
- [ ] `index.html` con lobby (seed, jugadores humanos, server_url)
- [ ] `api.js`: /start, /state, /legal, /act, /save
- [ ] `state.js`: mantener game_id, current_state, active_actor
- [ ] `renderer.js`: canvas con cuadrícula 3x3 por piso, habitaciones coloreadas
- [ ] `actions.js`: lista de acciones como botones clickeables
- [ ] Loop básico: lobby → /start → render → esperar input → /act → loop

### Fase 2: Experiencia completa (2-3 horas)
- [ ] Panel de información de jugadores (sanity, keys, objetos, statuses)
- [ ] Monstruos en el tablero (íconos/colores)
- [ ] Marcador de turno activo ("Turno de P1")
- [ ] Event log (últimas acciones)
- [ ] POST /save al finalizar la partida
- [ ] Botón "Nueva partida"

### Fase 3: Pulido y pruebas (1-2 horas)
- [ ] CSS oscuro temático CARCOSA
- [ ] Responsive (mobile-friendly para compartir pantalla)
- [ ] WebSocket como opción preferente, polling como fallback
- [ ] Soporte multi-ventana (abrir pestaña por jugador)
- [ ] Prueba de hot-seat con 2 jugadores locales

## 5. Requisitos para el amigo

- **Navegador web moderno** (Chrome/Firefox/Edge — cualquier cosa que no sea IE)
- **Conexión al mismo servidor**:
  - Local: ambos en la misma red WiFi → `http://192.168.x.x:8765`
  - Remoto: servidor en VPS o usando `ngrok http 8765`
- **Sin instalación**, sin Node.js, sin dependencias. Solo abrir `index.html`.

## 6. Alternativas si esto escala

Si el playtest HTML funciona y se usa seguido, se puede considerar:
- Migrar a un framework liviano (Svelte, Preact) para estados más complejos
- Agregar lobby web con sala de espera
- Autenticación básica para servidores remotos (API key)

---

*Documento de trabajo. Se actualiza a medida que se implementa.*
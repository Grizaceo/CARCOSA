# CARCOSA — Plan: Frontend Godot para Partidas Humanas (BC Dataset)

**Estado:** diseño inicial  
**Fecha:** 2026-03-23  
**Motivación:** Reemplazar/complementar datos de bots con partidas reales de jugadores humanos para Behavioral Cloning. 2+ jugadores humanos que conocen el juego generan señal de mayor calidad que cualquier heurística.

---

## Por qué esto es valioso

| Fuente de datos | Calidad de señal | Cobertura de bordes | Esfuerzo |
|---|---|---|---|
| Bots heurísticos (GOAL, etc.) | Media — reglas explícitas, no óptimas | Baja — ignoran edge-cases | Cero (automático) |
| RL auto-mejorado | Media-alta — mejora solo si converge | Media | Alto (computacional) |
| **Jugadores humanos** | **Alta — decisiones contextuales reales** | **Alta — humanos manejan bordes intuitivamente** | **Bajo (jugar = grabar)** |

Incluso 200–500 partidas humanas ganadas complementan masivamente el BC existente.

---

## Arquitectura general

```
┌──────────────────────────────────────────────────────────┐
│                      GODOT CLIENT                        │
│  (GDScript — render tablero, UI de acciones, HUD)        │
│                                                          │
│   Player 1 (local)          Player 2 (local o LAN)      │
│   ┌─────────────┐           ┌─────────────┐             │
│   │  Board View │           │  Board View │             │
│   │  Action HUD │           │  Action HUD │             │
│   └──────┬──────┘           └──────┬──────┘             │
└──────────┼───────────────────────┼─────────────────────┘
           │  HTTP/WebSocket       │
           ▼                       ▼
┌──────────────────────────────────────────────────────────┐
│              PYTHON GAME SERVER                          │
│         sim/game_server.py  (FastAPI + uvicorn)          │
│                                                          │
│  /start     → crea GameState, retorna game_id + estado   │
│  /state     → serializa GameState completo (JSON)        │
│  /legal     → get_legal_actions() para jugador activo    │
│  /act       → aplica Action, retorna nuevo estado        │
│  /save      → guarda sesión como JSONL (BC-ready)        │
│                                                          │
│  Usa directamente: engine/, sim/metrics.py               │
└──────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│         BC PIPELINE EXISTENTE (sin cambios)              │
│  tools/ai_ready_export.py → data/human_bc.csv            │
│  train/train_bc.py  →  models_bc/human_bc.pt             │
└──────────────────────────────────────────────────────────┘
```

**Ventaja clave:** el engine Python ya es determinista, serializable (`GameState.to_dict()`) y produce JSONL idéntico al que el pipeline BC ya consume. El servidor es una capa muy delgada.

---

## Fase 1 — Python: Servidor de Juego (REST)

### Archivo: `sim/game_server.py`

Dependencia mínima: `fastapi`, `uvicorn` (agregar a `requirements.txt`).

```python
# sim/game_server.py  — esqueleto de referencia
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid, json
from pathlib import Path
from datetime import datetime

from engine.config import Config
from engine.rng import RNG
from engine.actions import Action, ActionType
from engine.transition import step
from engine.legality import get_legal_actions
from sim.runner import make_smoke_state   # o make_game_state genérico
from sim.metrics import transition_record

app = FastAPI()
sessions: dict = {}   # game_id → {state, rng, records, cfg, seed}

class StartRequest(BaseModel):
    seed: int = 1
    players: list[str] = ["P1", "P2", "P3", "P4"]  # IDs de jugadores humanos
    mode: str = "human"   # "human" | "mixed" (algunos bots)

class ActionRequest(BaseModel):
    game_id: str
    player_id: str
    action_type: str
    data: dict = {}

@app.post("/start")
def start_game(req: StartRequest):
    game_id = str(uuid.uuid4())[:8]
    cfg = Config()
    rng = RNG(req.seed)
    state = make_smoke_state(seed=req.seed, cfg=cfg)
    sessions[game_id] = {"state": state, "rng": rng, "records": [], "cfg": cfg, "seed": req.seed}
    return {"game_id": game_id, "state": state.to_dict()}

@app.get("/state/{game_id}")
def get_state(game_id: str):
    s = sessions.get(game_id)
    if not s: raise HTTPException(404, "session not found")
    return s["state"].to_dict()

@app.get("/legal/{game_id}/{player_id}")
def legal_actions(game_id: str, player_id: str):
    s = sessions.get(game_id)
    if not s: raise HTTPException(404, "session not found")
    actions = get_legal_actions(s["state"], player_id)
    return [{"type": a.type, "data": a.data} for a in actions]

@app.post("/act")
def apply_action(req: ActionRequest):
    s = sessions.get(req.game_id)
    if not s: raise HTTPException(404, "session not found")
    action = Action(type=ActionType(req.action_type), data=req.data)
    pre_state = s["state"]
    # step() requiere RNG — se persiste entre llamadas para mantener secuencia determinista
    new_state = step(pre_state, action, s["rng"], s["cfg"])
    rec = transition_record(pre_state, action, new_state, actor=req.player_id)
    s["records"].append(rec)
    s["state"] = new_state
    return {"state": new_state.to_dict(), "done": new_state.outcome is not None}

@app.post("/save/{game_id}")
def save_session(game_id: str):
    s = sessions.get(game_id)
    if not s: raise HTTPException(404, "session not found")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(f"runs/human_{ts}_seed{s['seed']}.jsonl")
    out.parent.mkdir(exist_ok=True)
    with open(out, "w") as f:
        for r in s["records"]:
            f.write(json.dumps(r) + "\n")
    return {"saved": str(out), "steps": len(s["records"])}

### Correr el servidor
```bash
# En WSL
uvicorn sim.game_server:app --host 0.0.0.0 --port 8765 --reload
```

---

## Fase 2 — Godot: Cliente

### Estructura de proyecto Godot (Godot 4.x)
```
carcosa_client/
├── project.godot
├── scenes/
│   ├── Main.tscn          — escena raíz: conexión y lobby
│   ├── BoardView.tscn     — tablero 3 pisos, habitaciones, jugadores
│   ├── ActionPanel.tscn   — lista de acciones legales clickeables
│   ├── PlayerHUD.tscn     — cordura, llaves, objetos del jugador activo
│   └── EventLog.tscn      — log de eventos de la partida
├── scripts/
│   ├── GameClient.gd      — singleton: HTTP calls al servidor Python
│   ├── BoardView.gd       — renderiza estado → tablero visual
│   ├── ActionPanel.gd     — muestra acciones legales, emite acción elegida
│   └── PlayerHUD.gd       — actualiza stats de jugador
└── assets/
    ├── rooms/             — sprites de habitaciones
    ├── players/           — tokens de jugadores
    └── icons/             — íconos de acciones, objetos, estados
```

### GameClient.gd — núcleo de comunicación
```gdscript
# scripts/GameClient.gd
extends Node

const BASE_URL = "http://127.0.0.1:8765"
var game_id: String = ""
var current_state: Dictionary = {}
var my_player_id: String = "P1"

signal state_updated(state: Dictionary)
signal legal_actions_ready(actions: Array)

func start_game(seed: int, player_ids: Array) -> void:
    var body = JSON.stringify({"seed": seed, "players": player_ids})
    _post("/start", body, func(resp):
        game_id = resp["game_id"]
        current_state = resp["state"]
        state_updated.emit(current_state)
        fetch_legal_actions()
    )

func fetch_state() -> void:
    _get("/state/" + game_id, func(resp):
        current_state = resp
        state_updated.emit(current_state)
    )

func fetch_legal_actions() -> void:
    var active = _get_active_player()
    if active != my_player_id:
        return  # no es nuestro turno
    _get("/legal/" + game_id + "/" + my_player_id, func(resp):
        legal_actions_ready.emit(resp)
    )

func send_action(action_type: String, data: Dictionary = {}) -> void:
    var body = JSON.stringify({
        "game_id": game_id,
        "player_id": my_player_id,
        "action_type": action_type,
        "data": data
    })
    _post("/act", body, func(resp):
        current_state = resp["state"]
        state_updated.emit(current_state)
        if resp["done"]:
            save_session()
        else:
            fetch_legal_actions()
    )

func save_session() -> void:
    _post("/save/" + game_id, "{}", func(resp):
        print("Sesión guardada: ", resp["saved"])
    )

func _get_active_player() -> String:
    var order = current_state.get("turn_order", [])
    var pos = current_state.get("turn_pos", 0)
    if order.size() > pos:
        return order[pos]
    return ""

# helpers HTTP (usando HTTPRequest de Godot)
func _post(path: String, body: String, callback: Callable) -> void:
    var req = HTTPRequest.new()
    add_child(req)
    req.request_completed.connect(func(result, code, headers, response):
        req.queue_free()
        if code == 200:
            callback.call(JSON.parse_string(response.get_string_from_utf8()))
    )
    req.request(BASE_URL + path, ["Content-Type: application/json"], HTTPClient.METHOD_POST, body)

func _get(path: String, callback: Callable) -> void:
    var req = HTTPRequest.new()
    add_child(req)
    req.request_completed.connect(func(result, code, headers, response):
        req.queue_free()
        if code == 200:
            callback.call(JSON.parse_string(response.get_string_from_utf8()))
    )
    req.request(BASE_URL + path)
```

---

## Fase 3 — Multiplayer local (2 jugadores, 1 máquina)

Para el caso de "tú y otro colega":
- Misma instancia Godot muestra el turno del jugador activo
- `ActionPanel` solo aparece cuando `active_player == my_player_id`
- Para 2 jugadores en la misma PC: modo "hot-seat" — el juego pregunta "¿Jugador X, listo?" antes de mostrar las acciones

### Multiplayer LAN (opcional, fase posterior)
- Godot como thin client puro: cada PC conecta al mismo servidor Python en LAN
- `BASE_URL` configurable desde pantalla de lobby
- El servidor ya maneja sesiones por `game_id`
- Solo agregar WebSocket en lugar de HTTP polling para notificaciones de turno

---

## Fase 4 — Modo Mixto (humano + bot)

Para partidas de entrenamiento más largas sin necesitar 4 jugadores humanos:

```python
# En StartRequest agregar:
bot_players: dict = {}  # {"P3": "GOAL", "P4": "RANDOM"}
```

El servidor aplica la bot policy automáticamente cuando el turno es de P3/P4.
Los humanos solo toman decisiones para sus personajes.
Todo queda registrado en el mismo JSONL — el exportador ya distingue por `policy` field.

---

## Datos generados — compatibilidad con pipeline BC

Los JSONL guardados en `runs/human_*.jsonl` son **idénticos** al formato existente.

Para generar dataset BC desde partidas humanas:
```bash
# Exactamente igual que con datos de bots
python tools/ai_ready_export.py \
    --input runs/human_*.jsonl \
    --mode bc \
    --output data/human_bc.csv

# Entrenar mezclando humano + bot (recomendado)
python tools/ai_ready_export.py \
    --input runs/human_*.jsonl runs/seed_*.jsonl \
    --mode bc \
    --output data/mixed_bc.csv

python train/train_bc.py \
    --data data/mixed_bc.csv \
    --epochs 200 \
    --filter-outcome WIN \
    --save-dir models_bc/human_guided_v1
```

---

## Plan de implementación por fases

### Fase A — Servidor mínimo funcional (2–3 horas Python)
- [ ] Verificar firma de `step()` y `make_smoke_state()` en el engine actual
- [ ] Implementar `sim/game_server.py` con los 5 endpoints core
- [ ] Test manual con `curl` / `httpx` antes de arrancar Godot
- [ ] Agregar `fastapi`, `uvicorn` a `requirements.txt`

### Fase B — Godot: tablero parseable (2–4 horas Godot)
- [ ] Crear proyecto Godot 4.x en `godot_client/`
- [ ] Implementar `GameClient.gd` (HTTP calls)
- [ ] Renderizar tablero como grilla de 3 pisos × salas (placeholder con Labels primero)
- [ ] Mostrar lista de acciones legales como botones clickeables
- [ ] Verificar ciclo completo: start → ver estado → click acción → ver nuevo estado

### Fase C — UX jugable (1–2 días Godot)
- [ ] HUD de jugador: cordura, llaves, objetos, rol
- [ ] Log de eventos (texto de lo que pasó en el último step)
- [ ] Indicador visual de turno activo (quién juega ahora)
- [ ] Modo hot-seat: transición entre jugadores en misma máquina
- [ ] Pantalla de resultado (WIN / LOSE + botón "guardar y nueva partida")

### Fase D — Grabación y pipeline completo
- [ ] Auto-save al terminar partida
- [ ] Script wrapper `tools/run_human_session.sh` que levanta el servidor y abre Godot
- [ ] Verificar que `ai_ready_export.py` procesa correctamente los JSONL humanos
- [ ] Primer entrenamiento BC con datos mixtos y comparar con baseline bot

---

---

## ¿Es trasladable a Android + online?

**Respuesta corta: sí, y casi sin reescribir nada.**

La arquitectura cliente-servidor es exactamente la correcta para esto. Cada capa escala independientemente:

### Cliente Godot → Android

Godot 4 tiene export nativo a Android. El código GDScript es **idéntico**, solo cambia el target de exportación en el editor de Godot. Requerimientos adicionales:
- Instalar Android SDK + JDK en la máquina de build (una vez)
- Firmar el APK con un keystore (una vez)
- Cambiar `BASE_URL` en `GameClient.gd` para apuntar al servidor online en vez de `localhost`

**Nada del código de juego cambia.**

### Servidor Python → Online multiplayer

El servidor FastAPI ya es stateless por diseño (`game_id` como clave de sesión). Para pasar de local a online:

| Qué agregar | Esfuerzo | Notas |
|---|---|---|
| Reemplazar HTTP polling → WebSocket | Medio | Godot 4 tiene `WebSocketPeer` nativo; FastAPI tiene soporte con `websockets` lib |
| Hosting del servidor | Bajo | VPS $5/mes (Hetzner, DigitalOcean) o Docker en cualquier máquina con IP pública |
| Persistencia de sesiones | Bajo | SQLite (simple) o Redis (si escala) para que el servidor no pierda sesiones al reiniciar |
| Auth mínima de jugadores | Bajo | UUID de sesión por dispositivo, o nombre de jugador simple — no necesita OAuth |

### Ruta de evolución de la arquitectura

```
Sprint 1-4 ✅(1-2)        Sprint 5-6               Sprint 7+
────────────────────      ────────────────────      ────────────────────
PC local (hot-seat)  →   LAN / VPS online     →   App Android store
HTTP polling             WebSocket bidireccional    Google Play (opcional)
Un servidor por sesión   Servidor persistente       Push notifications
Sin auth                 UUID de jugador            User accounts (opcional)
```

**Conclusión:** El plan actual es Sprint 1–4. Sprints 5–7 son extensiones naturales sin romper nada anterior.

---

## Sprints de implementación (con agentes)

Cada sprint está diseñado para ser delegable a un agente de Copilot con contexto mínimo.

---

### Sprint 0 — Verificación de APIs del engine
**Objetivo:** Documentar las firmas exactas de las funciones que el servidor va a usar.  
**Duración estimada:** 30 min  
**Delegable a agente:** Sí (read-only, sin cambios de código)

**Tarea del agente:**
```
Lee los siguientes archivos y reporta:
- engine/transition.py → firma exacta de step() y qué retorna
- engine/legality.py → firma de get_legal_actions() y tipo de retorno
- engine/state.py → si GameState tiene método to_dict() y su estructura
- sim/runner.py → cómo se inicializa un GameState (make_smoke_state o equivalente)
- sim/metrics.py → firma de transition_record()
Documenta cualquier dependencia no obvia (RNG, Config, etc.)
```

**Resultado esperado:** Un bloque de referencias como este (ya verificado):
```python
# VERIFICADO 2026-03-23
step(state: GameState, action: Action, rng: RNG, cfg: Optional[Config] = None) -> GameState
get_legal_actions(state: GameState, player_id: PlayerId) -> List[Action]  # verificar firma real
transition_record(state, action, next_state, actor: str) -> dict  # verificar firma real
```

---

### Sprint 1 — Servidor Python mínimo (5 endpoints)
**Objetivo:** `sim/game_server.py` funcional, testeable con curl.  
**Estado:** ✅ COMPLETADO 2026-03-23  
**Duración estimada:** 2–3 horas  
**Delegable a agente:** Sí (implementación pura Python)

**Dependencias:** Sprint 0 completado (firmas verificadas)

**Tarea del agente:**
```
Implementa sim/game_server.py para el proyecto CARCOSA.

Requisitos:
- FastAPI + uvicorn
- Endpoints: POST /start, GET /state/{id}, GET /legal/{id}/{pid}, POST /act, POST /save/{id}
- Cada sesión almacena: state (GameState), rng (RNG), records (list), seed (int)
- El RNG debe persistir entre llamadas a /act (es el mismo objeto de la partida)
- /act serializa la transición con transition_record() y agrega a records[]
- /save escribe runs/human_{timestamp}_seed{N}.jsonl compatible con ai_ready_export.py
- /legal retorna acciones como lista de {type: str, data: dict}

Contexto del engine:
- step(state, action, rng, cfg=None) -> GameState  [engine/transition.py]
- get_legal_actions(state, player_id) -> List[Action]  [engine/legality.py]
- Action(type=ActionType(str), data=dict)  [engine/actions.py]
- make_smoke_state(seed, cfg) -> GameState  [sim/runner.py]

Agregar fastapi y uvicorn a requirements.txt.
```

**Criterio de éxito:**
```bash
uvicorn sim.game_server:app --port 8765
# En otra terminal:
curl -X POST http://localhost:8765/start -H "Content-Type: application/json" -d '{"seed":1}'
# Responde: {"game_id": "...", "state": {...}}
```

---

### Sprint 2 — Cliente Godot: texto + botones (board mínimo)
**Objetivo:** Ciclo completo jugable en Godot, sin gráficos — texto y botones.  
**Estado:** ✅ COMPLETADO 2026-03-23  
**Duración estimada:** 4–6 horas  
**Delegable a agente:** Parcialmente (scaffolding del proyecto; el wiring de UI requiere test manual)

**Dependencias:** Sprint 1 completado y servidor corriendo

**Tarea del agente (scaffolding):**
```
Crea el proyecto Godot 4 en godot_client/ con esta estructura mínima:
- project.godot configurado para Godot 4.3+
- scripts/GameClient.gd: singleton con _post()/_get() HTTP helpers, señales state_updated/legal_actions_ready
- scripts/Main.gd: pantalla de inicio con campo seed + botón "Nueva partida"
- scripts/BoardView.gd: muestra estado como tabla de texto (pisos, salas, jugadores, llaves, cordura)
- scripts/ActionPanel.gd: lista de botones generados dinámicamente desde /legal, emite acción al click
- scenes/Main.tscn, scenes/BoardView.tscn, scenes/ActionPanel.tscn

GameClient.gd debe:
- BASE_URL = "http://127.0.0.1:8765"
- start_game(seed, player_ids) → POST /start
- fetch_legal_actions(player_id) → GET /legal/{game_id}/{player_id}
- send_action(action_type, data) → POST /act → actualizar estado
- save_session() → POST /save/{game_id}

La UI puede ser completamente texto/colores — sin sprites todavía.
```

**Criterio de éxito:** Poder jugar una partida completa (START → múltiples acciones → SAVE) desde la ventana de Godot.

---

### Sprint 3 — Hot-seat + grabación BC
**Objetivo:** Soporte para 2–4 jugadores en la misma máquina, auto-save al terminar.  
**Duración estimada:** 2–3 horas  
**Delegable a agente:** Sí

**Tarea del agente:**
```
Extiende el cliente Godot (godot_client/) para soporte hot-seat:

1. En GameClient.gd: agregar lista local de player_ids humanos y cuál es el "activo"
2. En ActionPanel.gd: cuando el jugador activo NO es ninguno de los locales, mostrar
   overlay "Turno de [nombre]" y no mostrar acciones (modo observador)
3. Cuando SÍ es nuestro turno: mostrar AcceptDialog "Es el turno de [P2]. ¿Listo?" antes de revelar acciones
4. En Main.gd: pantalla de lobby donde se configura cuántos jugadores humanos hay (1-4)
   y qué bot usar para los slots vacíos (por ahora: ninguno — todos humanos o error)
5. Auto-save: cuando el servidor retorna done=true, llamar automáticamente a /save/{game_id}
   y mostrar pantalla de resultado (WIN/LOSE) con opción "Nueva partida"

No modificar sim/game_server.py en este sprint.
```

**Criterio de éxito:** Dos personas en la misma PC pueden jugar una partida completa que se guarda automáticamente como JSONL.

---

### Sprint 4 — Verificación BC pipeline
**Objetivo:** Confirmar que las partidas humanas generadas alimentan correctamente el entrenamiento BC.  
**Duración estimada:** 1 hora  
**Delegable a agente:** Sí (es verificación + script)

**Tarea del agente:**
```
1. Jugar (o simular con curl) 2–3 partidas con el servidor, guardar como runs/human_*.jsonl
2. Ejecutar: python tools/ai_ready_export.py --input runs/human_*.jsonl --mode bc --output data/human_bc.csv
3. Verificar que el CSV tiene las columnas esperadas (obs_P_sanity, obs_P_keys, etc.) y no tiene NaNs raros
4. Ejecutar: python train/train_bc.py --data data/human_bc.csv --epochs 5 --batch-size 32 --device cpu --save-dir models_bc/human_test
5. Reportar si el entrenamiento completa sin errores

Si hay incompatibilidades en el formato JSONL, identificar la diferencia entre
runs/human_*.jsonl y runs/[partida_de_bot].jsonl y parchear sim/game_server.py.
```

**Criterio de éxito:** `train_bc.py` procesa datos humanos sin modificaciones adicionales.

---

### Sprint 5 — WebSocket + modo online LAN
**Objetivo:** Dos PCs en la misma red pueden jugar juntas.  
**Duración estimada:** 4–6 horas  
**Delegable a agente:** Sí

**Tarea del agente:**
```
Migra sim/game_server.py y GameClient.gd de HTTP polling a WebSocket para notificaciones de turno.

Servidor (Python):
- Agregar endpoint WS: GET /ws/{game_id}/{player_id}
- Cuando cualquier jugador hace POST /act, el servidor hace broadcast a todos los ws conectados:
  {"type": "state_update", "state": {...}, "active_player": "P2"}
- HTTP endpoints /start, /legal, /act, /save se mantienen igual (WS es solo para push)
- Dependencia: 'websockets' ya incluida en fastapi[all] o agregar manualmente

Cliente Godot:
- En GameClient.gd: agregar WebSocketPeer para suscribirse a /ws/{game_id}/{my_player_id}
- Al recibir "state_update": actualizar estado visual y llamar fetch_legal_actions() si es nuestro turno
- Reemplazar el polling manual por esta notificación push
- BASE_URL configurable desde pantalla de lobby (para apuntar a host LAN: 192.168.x.x:8765)

No tocar la lógica de BC recording ni el formato JSONL.
```

**Criterio de éxito:** Dos instancias de Godot en distintas PCs (misma LAN) ven el estado actualizarse en tiempo real cuando el otro jugador actúa.

---

### Sprint 6 — Servidor hosted (VPS / Docker)
**Objetivo:** Servidor accesible desde internet para jugar con cualquier persona.  
**Duración estimada:** 2–4 horas  
**Delegable a agente:** Sí (Dockerfile + instrucciones deploy)

**Tarea del agente:**
```
Crea Dockerfile.server en la raíz del proyecto para el servidor de juego:
- Base: python:3.11-slim
- Instala requirements mínimos (fastapi, uvicorn, y dependencias del engine)
- Copia solo: engine/, sim/game_server.py, sim/runner.py, sim/metrics.py, sim/memory.py, sim/policies.py
- CMD: uvicorn sim.game_server:app --host 0.0.0.0 --port 8765
- Volumen montable para /app/runs (para persistir los JSONL)

Crear también docker-compose.server.yml:
- Servicio 'carcosa-server' con el Dockerfile.server
- Port mapping 8765:8765
- Volume ./runs:/app/runs

Agregar sección en docs/GODOT_HUMAN_PLAY_PLAN.md con instrucciones deploy:
- docker-compose -f docker-compose.server.yml up -d
- Cómo configurar BASE_URL en Godot al valor del servidor remoto
- Nota sobre abrir puerto 8765 en firewall del VPS
```

**Criterio de éxito:** `docker-compose -f docker-compose.server.yml up` levanta el servidor; cliente Godot local puede conectarse con IP pública.

---

### Sprint 7 — Export Android
**Objetivo:** APK instalable en Android con el cliente de juego.  
**Duración estimada:** 2–3 horas (instalación SDK) + 30 min (export)  
**Delegable a agente:** Parcialmente (el agente da instrucciones; la ejecución es manual en Godot)

**Tarea del agente:**
```
Documenta el proceso completo de export a Android para el proyecto godot_client/:

1. Requisitos de sistema: JDK 17+, Android SDK (API 28+), Godot Android export templates
2. Pasos en Godot Editor: Project → Export → Android, configurar keystore y package name
3. Cambios de código necesarios en GameClient.gd:
   - BASE_URL no puede ser 127.0.0.1 en Android → leer de una variable de configuración
   - Crear res://config.json o usar ProjectSettings para BASE_URL configurable
4. Configuración de red en Android: asegurar que el manifest tiene INTERNET permission
5. Cómo generar APK de debug vs release
6. Test en dispositivo: adb install carcosa.apk

Verificar si hay incompatibilidades con el uso de HTTPRequest de Godot en Android.
```

**Criterio de éxito:** APK instalable y funcional que se conecta al servidor del Sprint 6.

---

## Qué NO hace este plan (fuera de alcance por ahora)
- Motor de reglas en Godot (toda la lógica sigue en Python — Godot es solo UI)
- Assets gráficos definitivos (primero con texto/colores placeholder)
- Store deployment (Google Play / App Store)
- Cuentas de usuario / autenticación OAuth
- Modo torneo / rankings / leaderboard

---

## Referencia rápida de archivos relevantes

| Archivo | Rol |
|---|---|
| `sim/game_server.py` | A crear — servidor FastAPI |
| `engine/transition.py` | `step(state, action) → (state, events)` |
| `engine/legality.py` | `get_legal_actions(state, player_id) → List[Action]` |
| `engine/state.py` | `GameState.to_dict()` — serialización JSON |
| `sim/metrics.py` | `transition_record()` — genera registros BC |
| `sim/runner.py` | `make_smoke_state()` — referencia para init |
| `tools/ai_ready_export.py` | Procesa JSONL → CSV para BC (sin cambios) |
| `train/train_bc.py` | Entrenamiento BC (sin cambios) |
| `godot_client/` | A crear — proyecto Godot 4.x |

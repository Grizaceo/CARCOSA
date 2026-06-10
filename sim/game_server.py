"""
sim/game_server.py — CARCOSA Human Play Server (Sprint 1)

FastAPI server que expone el engine de CARCOSA como API HTTP,
permitiendo que un cliente externo (Godot u otro) juegue partidas
y las guarde como JSONL compatible con el pipeline BC.

Arrancar desde la raíz del proyecto con:
    uvicorn sim.game_server:app --host 127.0.0.1 --port 8765 --reload

Endpoints:
    POST /start              → nueva partida
    GET  /state/{id}         → estado actual
    GET  /legal/{id}/{actor} → acciones legales para un actor
    POST /act                → aplicar una acción
    POST /save/{id}          → guardar JSONL compatible con BC pipeline
    GET  /                   → health check
    WS   /ws/{id}/{pid}      → WebSocket para actualizaciones de estado en tiempo real
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from engine.actions import Action, ActionType
from engine.config import Config
from engine.legality import get_legal_actions
from engine.rng import RNG
from engine.state import GameState
from engine.transition import step
from sim.metrics import transition_record, write_jsonl
from sim.runner import make_smoke_state

app = FastAPI(title="CARCOSA Game Server", version="1.0.0")

# Custom exception handler for HTTPException to ensure proper error responses
from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# Permitir requests desde Godot (localhost) y herramientas de test
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Almacén de sesiones en memoria: {game_id -> session_dict}
_sessions: Dict[str, Dict[str, Any]] = {}

# WebSocket connections per session: {game_id -> set of WebSocket}
_ws_connections: Dict[str, set] = {}


# ── Request models ─────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    seed: int = 1
    players: list[str] = ["P1", "P2", "P3", "P4"]


class ActRequest(BaseModel):
    game_id: str
    actor: str
    action_type: str
    action_data: Dict[str, Any] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session(game_id: str) -> Dict[str, Any]:
    session = _sessions.get(game_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Game not found: " + game_id)
    return session


def _active_actor(state: GameState) -> str:
    """Devuelve el actor que debe actuar en este momento."""
    if state.phase == "KING":
        return "KING"
    # CANON Fix #A: Sacrifice Interrupt — el actor activo puede ser distinto del turn_pos
    pending_sacrifice = state.flags.get("PENDING_SACRIFICE_CHECK")
    if pending_sacrifice:
        if isinstance(pending_sacrifice, list):
            if pending_sacrifice:
                return str(pending_sacrifice[0])
        else:
            return str(pending_sacrifice)
    return str(state.turn_order[state.turn_pos])


def _state_summary(state: GameState) -> Dict[str, Any]:
    """Resumen serializable del estado para la respuesta API."""
    return {
        "game_over": state.game_over,
        "outcome": state.outcome,
        "round": state.round,
        "phase": state.phase,
        "active_actor": _active_actor(state),
        "players": {
            str(pid): {
                "sanity": p.sanity,
                "sanity_max": p.sanity_max,
                "keys": p.keys,
                "room": str(p.room),
                "objects": list(p.objects),
                "role_id": p.role_id,
                "statuses": [s.status_id for s in p.statuses],
                "remaining_actions": state.remaining_actions.get(pid, 0),
            }
            for pid, p in state.players.items()
        },
        "monsters": [
            {
                "id": str(m.monster_id),
                "room": str(m.room),
                # Floor is encoded in room name: "F1_R2" → floor 1
                "floor": int(str(m.room).split("_")[0][1:]) if str(m.room).startswith("F") else 1,
            }
            for m in state.monsters
        ],
        "rooms": {
            str(rid): {
                "special_card_id": r.special_card_id,
                "special_revealed": r.special_revealed,
                "special_destroyed": r.special_destroyed,
                "deck": {
                    "cards": [str(c) for c in r.deck.cards],
                    "top": r.deck.top,
                } if r.deck else None
            }
            for rid, r in state.rooms.items()
        },
        "king_floor": state.king_floor,
        "action_log": list(state.action_log),
    }


# ── WebSocket broadcast helper ───────────────────────────────────────────────────

async def _broadcast(game_id: str, message: Dict[str, Any]) -> None:
    """Send JSON message to all WebSocket connections for a game session."""
    connections = _ws_connections.get(game_id, set())
    dead_connections = set()
    
    for ws in connections:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead_connections.add(ws)
    
    # Remove dead connections
    if dead_connections:
        _ws_connections[game_id] = connections - dead_connections


# ── Auto-advance ──────────────────────────────────────────────────────────────

def _single_step(session: Dict[str, Any], actor: str, action_type: str, action_data: Dict[str, Any], policy_label: str) -> GameState:
    """Ejecuta un step, registra la transición, retorna el nuevo estado."""
    state: GameState = session["state"]
    rng: RNG = session["rng"]
    cfg: Config = session["cfg"]
    step_idx: int = session["step_idx"]

    at = ActionType(action_type)
    action = Action(actor=actor, type=at, data=action_data)
    next_state = step(state, action, rng, cfg)

    action_dict: Dict[str, Any] = {"actor": actor, "type": action_type, "data": action_data}
    if action_type == "KING_ENDROUND" and rng.last_king_d6 is not None:
        action_dict["d6"] = rng.last_king_d6

    record = transition_record(state, action_dict, next_state, cfg, step_idx)
    record["policy"] = policy_label

    session["records"].append(record)
    session["state"] = next_state
    session["step_idx"] = step_idx + 1
    return next_state


async def _auto_advance_until_human(game_id: str) -> None:
    """
    Avanza el estado automáticamente mientras el actor activo NO sea humano.
    Maneja tanto bots (policy=GOAL) como fases del KING.
    """
    from sim.policies import get_king_policy, get_player_policy

    session = _get_session(game_id)
    human_ids: set = session.get("human_ids", set())
    cfg: Config = session["cfg"]
    rng: RNG = session["rng"]

    kpol = get_king_policy(getattr(cfg, "KING_POLICY", "RANDOM"), cfg)
    ppol = get_player_policy("GOAL", cfg)

    max_iter: int = 100  # safety valve
    it: int = 0

    while it < max_iter:
        state: GameState = session["state"]
        if state.game_over:
            break

        actor: str = _active_actor(state)
        # ¿Es humano? → parar y esperar input
        if actor in human_ids:
            break

        # ¿KING?
        if actor == "KING":
            action = kpol.choose(state, rng)
            legal = get_legal_actions(state, "KING")
            if action not in legal:
                action = legal[0] if legal else Action(actor="KING", type=ActionType.KING_ENDROUND, data={})
            _single_step(session, "KING", action.type.value, action.data, "bot_king")
        else:
            # Bot
            action = ppol.choose(state, rng)
            legal = get_legal_actions(state, actor)
            if action not in legal:
                action = legal[0] if legal else Action(actor=actor, type=ActionType.END_TURN, data={})
            _single_step(session, actor, action.type.value, action.data, "bot")
        
        # Broadcast state after each bot action
        if game_id in _ws_connections:
            await _broadcast(game_id, {
                "type": "state_update",
                "state": _state_summary(session["state"]),
                "active_player": _active_actor(session["state"]),
            })
        it += 1


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/start")
def start_game(req: StartRequest) -> Dict[str, Any]:
    """
    Inicia una nueva partida. Retorna game_id + estado inicial.

    Si hay menos de 4 jugadores humanos, los slots restantes se rellenan con
    bots (policy=GOAL) que el servidor avanza automáticamente.

    Ejemplo:
        curl -X POST http://localhost:8765/start \\
             -H 'Content-Type: application/json' \\
             -d '{"seed": 1, "players": ["P1", "P2"]}'
    """
    game_id = str(uuid.uuid4())[:8]
    cfg = Config()
    # Siempre crear estado completo (4 jugadores). El engine lo requiere.
    # Los slots no humanos se manejan como bots.
    state = make_smoke_state(seed=req.seed, cfg=cfg)
    # RNG independiente para gameplay (igual que runner.py)
    game_rng = RNG(req.seed)

    # Detectar qué jugadores son humanos y cuáles bots
    human_ids: set = set(req.players)
    all_ids = [str(pid) for pid in state.players.keys()]
    bot_ids = [pid for pid in all_ids if pid not in human_ids]

    _sessions[game_id] = {
        "state": state,
        "rng": game_rng,
        "cfg": cfg,
        "seed": req.seed,
        "records": [],
        "step_idx": 0,
        "human_ids": human_ids,
        "bot_ids": set(bot_ids),
    }

    # Avanzar automáticamente si el primer turno es de un bot o de KING
    _auto_advance_until_human(game_id)

    return {"game_id": game_id, "state": _state_summary(_sessions[game_id]["state"])}


@app.get("/state/{game_id}")
def get_state(game_id: str) -> Dict[str, Any]:
    """Retorna el estado actual de una partida."""
    session = _get_session(game_id)
    return {"game_id": game_id, "state": _state_summary(session["state"])}


@app.get("/legal/{game_id}/{actor}")
def get_legal(game_id: str, actor: str) -> Dict[str, Any]:
    """
    Retorna las acciones legales para `actor` en el estado actual.
    actor: 'P1' | 'P2' | 'P3' | 'P4' | 'KING'
    """
    session = _get_session(game_id)
    state = session["state"]
    try:
        actions = get_legal_actions(state, actor)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "game_id": game_id,
        "actor": actor,
        "actions": [{"type": a.type.value, "data": a.data} for a in actions],
    }


@app.post("/act")
async def act(req: ActRequest) -> Dict[str, Any]:
    """
    Aplica una acción al estado actual y registra la transición.
    Después, avanza automáticamente por bots y fases KING hasta
    que toque el siguiente humano (o game over).

    Ejemplo:
        curl -X POST http://localhost:8765/act \\
             -H 'Content-Type: application/json' \\
             -d '{"game_id": "abc12345", "actor": "P1",
                  "action_type": "END_TURN", "action_data": {}}'
    """
    session = _get_session(req.game_id)
    state: GameState = session["state"]

    # Validar que el actor pertenece a esta partida
    human_ids: set = session.get("human_ids", set())
    bot_ids: set = session.get("bot_ids", set())
    valid_actors = human_ids | bot_ids
    if req.actor not in valid_actors:
        raise HTTPException(
            status_code=403,
            detail=f"Actor '{req.actor}' no pertenece a esta partida. Actores válidos: {sorted(valid_actors)}"
        )

    if state.game_over:
        raise HTTPException(status_code=400, detail="Game is already over")

    try:
        ActionType(req.action_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Unknown action type: " + req.action_type,
        )

    # Ejecutar la acción del humano
    next_state = _single_step(session, req.actor, req.action_type, req.action_data, "human")
    
    # Broadcast state update after human action
    if req.game_id in _ws_connections:
        await _broadcast(req.game_id, {
            "type": "state_update",
            "state": _state_summary(session["state"]),
            "active_player": _active_actor(session["state"]),
        })

    # Avanzar automáticamente hasta que toque otro humano
    await _auto_advance_until_human(req.game_id)

    # Broadcast final state after auto-advance
    if req.game_id in _ws_connections:
        await _broadcast(req.game_id, {
            "type": "state_update",
            "state": _state_summary(session["state"]),
            "active_player": _active_actor(session["state"]),
        })

    # El estado final es el que quedó después del auto-advance
    final_state: GameState = session["state"]
    return {
        "game_id": req.game_id,
        "state": _state_summary(final_state),
        "done": bool(final_state.game_over),
        "outcome": final_state.outcome,
        "step": session["step_idx"],
    }


@app.post("/save/{game_id}")
def save_game(game_id: str) -> Dict[str, Any]:
    """
    Guarda la sesión como JSONL en runs/human_{timestamp}_seed{N}/.
    Compatible con ai_ready_export.py y train_bc.py.
    """
    session = _get_session(game_id)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    seed = session["seed"]
    out_dir = "runs/human_" + ts + "_seed" + str(seed)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "human.jsonl")
    write_jsonl(path, session["records"])
    return {
        "game_id": game_id,
        "saved_to": path,
        "steps": len(session["records"]),
        "outcome": session["state"].outcome,
    }


@app.get("/")
def health() -> Dict[str, Any]:
    """Health check básico."""
    return {
        "status": "ok",
        "active_sessions": len(_sessions),
        "ws_connections": {gid: len(conns) for gid, conns in _ws_connections.items()},
    }


# ── Static file serving ──────────────────────────────────────────────────────
# Sirve frontend estático (index.html + assets)
STATIC_DIR = "/app/static"

@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/static/css/style.css", include_in_schema=False)
async def serve_css():
    return FileResponse(os.path.join(STATIC_DIR, "css", "style.css"), media_type="text/css")

@app.get("/static/js/api.js", include_in_schema=False)
async def serve_api_js():
    return FileResponse(os.path.join(STATIC_DIR, "js", "api.js"), media_type="application/javascript")

@app.get("/static/js/renderer.js", include_in_schema=False)
async def serve_renderer_js():
    return FileResponse(os.path.join(STATIC_DIR, "js", "renderer.js"), media_type="application/javascript")

@app.get("/static/js/main.js", include_in_schema=False)
async def serve_main_js():
    return FileResponse(os.path.join(STATIC_DIR, "js", "main.js"), media_type="application/javascript")


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws/{game_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    """
    WebSocket endpoint for real-time game state updates.
    
    Client (Godot) connects to /ws/{game_id}/{player_id} after receiving game_id
    from /start. Server sends state_update messages when game state changes.
    """
    await websocket.accept()
    
    # Register connection
    if game_id not in _ws_connections:
        _ws_connections[game_id] = set()
    _ws_connections[game_id].add(websocket)
    
    session = _sessions.get(game_id)
    if session:
        # Send current state immediately upon connection
        await websocket.send_text(json.dumps({
            "type": "state_update",
            "state": _state_summary(session["state"]),
            "active_player": _active_actor(session["state"]),
        }))
    
    try:
        while True:
            # Keep connection alive (clients don't need to send messages)
            data = await websocket.receive_text()
            # Ignore any messages from client for now
    except Exception:
        pass
    finally:
        # Remove dead connection
        _ws_connections.get(game_id, set()).discard(websocket)

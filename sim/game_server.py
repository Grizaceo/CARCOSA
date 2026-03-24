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
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Permitir requests desde Godot (localhost) y herramientas de test
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Almacén de sesiones en memoria: {game_id -> session_dict}
_sessions: Dict[str, Dict[str, Any]] = {}


# ── Request models ─────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    seed: int = 1


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
        "king_floor": state.king_floor,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/start")
def start_game(req: StartRequest) -> Dict[str, Any]:
    """
    Inicia una nueva partida. Retorna game_id + estado inicial.

    Ejemplo:
        curl -X POST http://localhost:8765/start \\
             -H 'Content-Type: application/json' \\
             -d '{"seed": 1}'
    """
    game_id = str(uuid.uuid4())[:8]
    cfg = Config()
    state = make_smoke_state(seed=req.seed, cfg=cfg)
    # RNG independiente para el gameplay (igual que run_episode en runner.py)
    rng = RNG(req.seed)

    _sessions[game_id] = {
        "state": state,
        "rng": rng,
        "cfg": cfg,
        "seed": req.seed,
        "records": [],
        "step_idx": 0,
    }
    return {"game_id": game_id, "state": _state_summary(state)}


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
def act(req: ActRequest) -> Dict[str, Any]:
    """
    Aplica una acción al estado actual y registra la transición.
    Retorna el nuevo estado, done y outcome.

    Ejemplo:
        curl -X POST http://localhost:8765/act \\
             -H 'Content-Type: application/json' \\
             -d '{"game_id": "abc12345", "actor": "P1",
                  "action_type": "END_TURN", "action_data": {}}'
    """
    session = _get_session(req.game_id)
    state: GameState = session["state"]
    rng: RNG = session["rng"]
    cfg: Config = session["cfg"]
    step_idx: int = session["step_idx"]

    if state.game_over:
        raise HTTPException(status_code=400, detail="Game is already over")

    try:
        action_type = ActionType(req.action_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Unknown action type: " + req.action_type,
        )

    action = Action(actor=req.actor, type=action_type, data=req.action_data)

    try:
        next_state = step(state, action, rng, cfg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # transition_record espera action como Dict (no como Action object)
    action_dict: Dict[str, Any] = {
        "actor": req.actor,
        "type": req.action_type,
        "data": req.action_data,
    }
    record = transition_record(state, action_dict, next_state, cfg, step_idx)
    record["policy"] = "human"

    session["records"].append(record)
    session["state"] = next_state
    session["step_idx"] = step_idx + 1

    return {
        "game_id": req.game_id,
        "state": _state_summary(next_state),
        "done": bool(next_state.game_over),
        "outcome": next_state.outcome,
        "step": step_idx,
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
    return {"status": "ok", "active_sessions": len(_sessions)}

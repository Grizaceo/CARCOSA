"""
sim/game_server.py — CARCOSA Human Play Server

FastAPI server que expone el engine de CARCOSA como API HTTP,
permitiendo que clientes web (web/) o Godot jueguen partidas
y las guarde como JSONL compatible con el pipeline BC.

Arrancar desde la raíz del proyecto con:
    uvicorn sim.game_server:app --host 127.0.0.1 --port 8765 --reload

Endpoints:
    POST /start                → nueva partida (roles + asientos humanos/bots)
    POST /claim                → reclamar asiento(s) para un cliente (multijugador remoto)
    GET  /state/{id}           → estado actual
    GET  /legal/{id}/{actor}   → acciones legales para un actor
    POST /act                  → aplicar una acción (valida legalidad)
    POST /save/{id}            → guardar JSONL compatible con BC pipeline
    GET  /games                → lista partidas guardadas (PG o filesystem)
    GET  /games/{id}/download  → descarga JSONL de una partida guardada
    GET  /setup_preview/{seed} → preview real de setup (habitaciones especiales + roles)
    GET  /health               → health check
    WS   /ws/{id}/{pid}        → WebSocket para actualizaciones de estado en tiempo real
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.actions import Action, ActionType
from engine.config import Config
from engine.inventory import get_inventory_limits
from engine.legality import get_legal_actions
from engine.rng import RNG
from engine.state import GameState
from engine.transition import step
from sim.metrics import transition_record, write_jsonl, write_jsonl_to_string
from sim.runner import make_smoke_state

# PostgreSQL connection pool (opcional: sin asyncpg se usa filesystem)
try:
    import asyncpg
except ImportError:
    asyncpg = None
_db_pool = None

async def init_db_pool():
    global _db_pool
    if asyncpg is None:
        print("[DB] asyncpg no instalado, usando filesystem para registros de partidas")
        return
    database_url = os.getenv("DATABASE_URL")

    # Force internal URL format for Render PostgreSQL internal connections
    if database_url and "oregon-postgres.render.com" in database_url:
        # Convert external URL to internal format
        database_url = database_url.replace(
            "@dpg-d8kvfshkh4rs73fjricg-a.oregon-postgres.render.com:5432/",
            "@dpg-d8kvfshkh4rs73fjricg-a/"
        )
        print(f"[DB] Converted to internal URL format: {database_url[:80]}...")

    print(f"[DB] DATABASE_URL from env: {database_url[:80] if database_url else 'NOT SET'}...")
    if database_url:
        # Render PostgreSQL internal connections need SSL but hostname verification fails
        # Create custom SSL context that doesn't verify hostname
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        # Remove sslmode from URL if present
        if "sslmode=" in database_url:
            import urllib.parse
            parsed = urllib.parse.urlparse(database_url)
            query_params = urllib.parse.parse_qs(parsed.query)
            query_params.pop('sslmode', None)
            new_query = urllib.parse.urlencode(query_params, doseq=True)
            database_url = urllib.parse.urlunparse(parsed._replace(query=new_query))

        print(f"[DB] Connecting to PostgreSQL with custom SSL: {database_url[:80]}...")
        try:
            _db_pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5, ssl=ssl_context)
            # Test connection
            async with _db_pool.acquire() as conn:
                await conn.execute("SELECT 1")
            print("[DB] PostgreSQL connection test successful")
        except Exception as e:
            print(f"[DB] PostgreSQL connection FAILED: {type(e).__name__}: {e}")
            print(f"[DB] Falling back to filesystem mode")
            _db_pool = None
            return

        # Create table if not exists
        try:
            async with _db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS carcosa_games (
                        id TEXT PRIMARY KEY,
                        seed INTEGER NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        completed_at TIMESTAMPTZ,
                        outcome TEXT,
                        rounds INTEGER,
                        jsonl_data TEXT NOT NULL,
                        human_players TEXT[] NOT NULL
                    )
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_carcosa_games_created_at ON carcosa_games(created_at DESC)
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS carcosa_reports (
                        id TEXT PRIMARY KEY,
                        game_id TEXT,
                        client_id TEXT,
                        category TEXT,
                        description TEXT NOT NULL,
                        context TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
            print(f"[DB] PostgreSQL pool initialized with custom SSL: {database_url[:50]}...")
        except Exception as e:
            print(f"[DB] Table creation FAILED: {type(e).__name__}: {e}")
            print("[DB] Falling back to filesystem mode")
            _db_pool = None
    else:
        print("[DB] DATABASE_URL not set, using filesystem fallback")


app = FastAPI(title="CARCOSA Game Server", version="1.1.0")

# Detectar directorio de static (Docker usa /app/static, local usa web/)
STATIC_DIR = "/app/static"
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
    if not os.path.exists(STATIC_DIR):
        STATIC_DIR = "web"

# Servir frontend estático en /static (html=True: /static/hali/ sirve su index.html)
app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")


# Atajo al motor HALI (representación 2.5D)
@app.get("/hali", include_in_schema=False)
async def serve_hali():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/hali/")

# Servir index.html en root con headers anti-cache para forzar reload del frontend
@app.get("/", include_in_schema=False)
async def serve_index():
    response = FileResponse(os.path.join(STATIC_DIR, "index.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Custom exception handler for HTTPException to ensure proper error responses
from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# Lifecycle
@app.on_event("startup")
async def startup_db():
    await init_db_pool()
    load_sessions_from_disk()
    asyncio.create_task(cleanup_inactive_sessions_task())
    # Si una sesión restaurada quedó con un bot/KING como actor activo (snapshot
    # persistido a mitad del bucle de bots), reanudar el auto-advance.
    for gid in list(_sessions.keys()):
        try:
            state = _sessions[gid]["state"]
            if not state.game_over and _active_actor(state) not in _sessions[gid].get("human_ids", set()):
                asyncio.create_task(_auto_advance_until_human(gid))
        except Exception as e:
            print(f"[SESSION_LOAD] Error reanudando auto-advance de {gid}: {e}")

@app.on_event("shutdown")
async def shutdown_db():
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        print("[DB] PostgreSQL pool closed")

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

# Índice filesystem de partidas guardadas (fallback sin PostgreSQL)
FS_GAMES_INDEX = os.path.join("runs", "human_games_index.jsonl")


# ── Persistencia de sesiones activas (sobrevive reinicios) ───────────────────

def serialize_rng(rng: RNG) -> Dict[str, Any]:
    return {
        "seed": rng.seed,
        "last_king_d6": rng.last_king_d6,
        "last_king_d4": rng.last_king_d4,
        "random_state": list(rng._r.getstate()) if rng._r else None
    }

def deserialize_rng(d: Dict[str, Any]) -> RNG:
    rng = RNG(d["seed"])
    rng.last_king_d6 = d.get("last_king_d6")
    rng.last_king_d4 = d.get("last_king_d4")
    if d.get("random_state") and rng._r:
        state = d["random_state"]
        state[1] = tuple(state[1])
        rng._r.setstate(tuple(state))
    return rng

def serialize_session(session: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "state": session["state"].to_dict(),
        "rng": serialize_rng(session["rng"]),
        "seed": session["seed"],
        "records": session["records"],
        "step_idx": session["step_idx"],
        "human_ids": list(session["human_ids"]),
        "bot_ids": list(session["bot_ids"]),
        "seat_claims": dict(session.get("seat_claims", {})),
        "saved_to": session.get("saved_to"),
        "updated_at": datetime.now().isoformat()
    }

def deserialize_session(d: Dict[str, Any]) -> Dict[str, Any]:
    cfg = Config()
    state = GameState.from_dict(d["state"])
    rng = deserialize_rng(d["rng"])
    return {
        "state": state,
        "rng": rng,
        "cfg": cfg,
        "seed": d["seed"],
        "records": d["records"],
        "step_idx": d["step_idx"],
        "human_ids": set(d["human_ids"]),
        "bot_ids": set(d["bot_ids"]),
        "seat_claims": dict(d.get("seat_claims", {})),
        "saved_to": d.get("saved_to"),
    }

def save_session_to_disk(game_id: str) -> None:
    session = _sessions.get(game_id)
    if not session:
        return
    try:
        os.makedirs("runs/active_sessions", exist_ok=True)
        path = os.path.join("runs/active_sessions", f"{game_id}.json")
        with open(path, "w") as f:
            json.dump(serialize_session(session), f)
    except Exception as e:
        print(f"[SESSION_SAVE] Error saving session {game_id}: {e}")

def load_sessions_from_disk() -> None:
    path = "runs/active_sessions"
    if not os.path.exists(path):
        return
    print("[SESSION_LOAD] Loading active sessions from disk...")
    for filename in os.listdir(path):
        if filename.endswith(".json"):
            game_id = filename[:-5]
            file_path = os.path.join(path, filename)
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                _sessions[game_id] = deserialize_session(data)
                print(f"[SESSION_LOAD] Restored active session: {game_id}")
            except Exception as e:
                print(f"[SESSION_LOAD] Error loading session {game_id}: {e}")

def delete_session_from_disk(game_id: str) -> None:
    try:
        path = os.path.join("runs/active_sessions", f"{game_id}.json")
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"[SESSION_DELETE] Error deleting session file {game_id}: {e}")

async def cleanup_inactive_sessions_task():
    while True:
        await asyncio.sleep(900)  # Cada 15 minutos
        path = "runs/active_sessions"
        if not os.path.exists(path):
            continue
        now = datetime.now()
        for filename in os.listdir(path):
            if filename.endswith(".json"):
                game_id = filename[:-5]
                file_path = os.path.join(path, filename)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    # Si no ha sido modificada en más de 6 horas
                    if (now - mtime).total_seconds() > 21600:
                        print(f"[CLEANUP] Expiring inactive game session: {game_id}")
                        _sessions.pop(game_id, None)
                        _ws_connections.pop(game_id, None)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                except Exception as e:
                    print(f"[CLEANUP] Error during cleanup of {game_id}: {e}")


# ── Request models ─────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    seed: int = 1
    players: list[str] = ["P1", "P2", "P3", "P4"]
    # Config completa de asientos: [{pid, roleId?, control: "local"|"remote"|"bot"}]
    # (compat: también acepta isHuman: bool en lugar de control)
    players_config: list[Dict[str, Any]] = []
    draw_mode: str = ""
    client_id: Optional[str] = None
    # [092]/[093] Política de bots = TECHO REAL 23.0% (COMMITTEE v5).
    # bot_default.zip -> models/maskable_ppo_carcosa_final_20260805_154245.zip (23.0% real).
    # NO usar el último modelo en disco (20260806_185139 = jitter FALSIFICADO 0/300).
    # Nota: models/ esta gitignored (artifacts locales). El .zip debe existir en disco.
    bot_policy: str = "PPO"
    ppo_model_path: Optional[str] = "models/maskable_ppo_carcosa_final_20260805_154245.zip"


class ActRequest(BaseModel):
    game_id: str
    actor: str
    action_type: str
    action_data: Dict[str, Any] = {}
    client_id: Optional[str] = None


class ReportRequest(BaseModel):
    """Reporte de error in-app (para jugadores que no usan GitHub)."""
    description: str
    category: str = "otro"          # regla | visual | interfaz | otro
    game_id: Optional[str] = None
    client_id: Optional[str] = None
    context: Dict[str, Any] = {}    # capturado automáticamente por el frontend


class ClaimRequest(BaseModel):
    game_id: str
    client_id: str
    seats: list[str]
    # "add": reclama los asientos listados sin soltar los demás (default).
    # "replace": los asientos del cliente pasan a ser exactamente `seats`.
    # "release": suelta los asientos listados (o todos los del cliente si la lista viene vacía).
    mode: str = "add"
    # Permite quitarle un asiento a otro client_id (rescate de partidas: amigo que nunca
    # llegó, localStorage perdido, etc. — modelo de confianza entre amigos).
    takeover: bool = False


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


def _json_safe(value: Any) -> Any:
    """Convierte recursivamente a tipos JSON-serializables (claves/objetos custom → str)."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _state_summary(state: GameState, session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resumen serializable del estado para la respuesta API."""
    cfg = (session or {}).get("cfg") or Config()

    players: Dict[str, Any] = {}
    for pid, p in state.players.items():
        key_slots, obj_slots = get_inventory_limits(p)
        players[str(pid)] = {
            "sanity": p.sanity,
            "sanity_max": p.sanity_max,
            "keys": p.keys,
            "keys_capacity": key_slots,
            "object_slots": obj_slots,
            "room": str(p.room),
            "objects": list(p.objects),
            "role_id": p.role_id,
            "statuses": [s.status_id for s in p.statuses],
            "remaining_actions": state.remaining_actions.get(pid, 0),
            "shield": getattr(p, "shield", 0),
            "at_minus5": getattr(p, "at_minus5", False),
            "free_move_used_this_turn": getattr(p, "free_move_used_this_turn", False),
            "double_roll_used_this_turn": getattr(p, "double_roll_used_this_turn", False),
            "soulbound_items": list(getattr(p, "soulbound_items", [])),
            "object_charges": dict(getattr(p, "object_charges", {})),
            "object_slots_penalty": getattr(p, "object_slots_penalty", 0),
        }

    summary = {
        "game_over": state.game_over,
        "outcome": state.outcome,
        "round": state.round,
        "phase": state.phase,
        "active_actor": _active_actor(state),
        "players": players,
        "monsters": [
            {
                "id": str(m.monster_id),
                "monster_id": str(m.monster_id),
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
        # P3-1: Motemey deck for frontend deck counters
        "motemey_deck": {
            "cards": [str(c) for c in state.motemey_deck.cards],
            "top": state.motemey_deck.top,
        } if state.motemey_deck else None,
        "king_floor": state.king_floor,
        "action_log": _json_safe(list(state.action_log)),
        # Estado global que el frontend necesita para render fiel al canon
        "flags": _json_safe(dict(state.flags)),
        "pending_motemey_choice": _json_safe(state.pending_motemey_choice) if state.pending_motemey_choice else None,
        "movement_blocked_players": [str(x) for x in state.movement_blocked_players],
        "tue_tue_revelations": state.tue_tue_revelations,
        "salon_belleza_uses": state.salon_belleza_uses,
        "false_king_floor": state.false_king_floor,
        "king_vanished_turns": state.king_vanished_turns,
        "keys_destroyed": state.keys_destroyed,
        "keys_total": getattr(cfg, "KEYS_TOTAL", 6),
        "keys_to_win": getattr(cfg, "KEYS_TO_WIN", 4),
        "ring_activated_by": str(state.ring_activated_by) if state.ring_activated_by else None,
        "chambers_book_holder": str(state.chambers_book_holder) if state.chambers_book_holder else None,
        "chambers_tales_attached": state.chambers_tales_attached,
        "taberna_used_this_turn": {str(k): bool(v) for k, v in state.taberna_used_this_turn.items()},
        "armory_storage": {str(k): [str(i) for i in v] for k, v in state.armory_storage.items()},
        # Escaleras por piso: sin esto el frontend no puede renderizar la conectividad
        # vertical canónica (canon 4.2). {"1": "F1_R1", ...}
        "stairs": {str(f): str(rid) for f, rid in state.stairs.items()},
    }

    if session is not None:
        summary["seats"] = {
            "humans": sorted(str(x) for x in session.get("human_ids", set())),
            "bots": sorted(str(x) for x in session.get("bot_ids", set())),
            "claims": dict(session.get("seat_claims", {})),
        }
        summary["saved_to"] = session.get("saved_to")
        summary["seed"] = session.get("seed")
        # Contador monotónico: el frontend descarta estados que lleguen fuera de orden
        # (la respuesta HTTP de /act y los broadcasts WS viajan por canales distintos).
        summary["step"] = session.get("step_idx", 0)
        # Acción más reciente (para el visualizador de red en vivo, línea [092])
        la = session.get("last_action")
        if la is not None:
            summary["last_action"] = {"actor": la.get("actor"), "type": la.get("type"), "data": la.get("data", {})}

    return summary


# ── WebSocket broadcast helper ───────────────────────────────────────────────────

async def _broadcast_state(game_id: str) -> None:
    """Envía el estado actual a todas las conexiones WS de la partida."""
    session = _sessions.get(game_id)
    connections = _ws_connections.get(game_id, set())
    if not session or not connections:
        return

    payload = json.dumps({
        "type": "state_update",
        "state": _state_summary(session["state"], session),
        "active_player": _active_actor(session["state"]),
    })

    dead = set()
    for ws in list(connections):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    if dead:
        _ws_connections[game_id] = connections - dead


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
        # Anotar d6/d4 en la entrada del action_log para que el frontend pueda
        # desglosar la fase del Rey (el engine no los incluye en su log).
        if next_state.action_log and next_state.action_log[-1].get("type") == "KING_ENDROUND":
            next_state.action_log[-1]["d6"] = rng.last_king_d6
            if rng.last_king_d4 is not None:
                next_state.action_log[-1]["d4"] = rng.last_king_d4

    record = transition_record(state, action_dict, next_state, cfg, step_idx)
    record["policy"] = policy_label
    session["last_action"] = action_dict  # para el visualizador de red en vivo (línea [092])

    session["records"].append(record)
    session["state"] = next_state
    session["step_idx"] = step_idx + 1
    return next_state


async def _auto_advance_until_human(game_id: str, delay: float = 0.0) -> None:
    """
    Avanza el estado automáticamente mientras el actor activo NO sea humano.
    Maneja tanto bots (policy=GOAL) como fases del KING.

    Si delay > 0 (modo espectador 100% bots), espera `delay` segundos entre
    pasos para que el cliente vea la partida a ritmo humano vía WebSocket.
    """
    from sim.policies import get_king_policy, get_player_policy

    session = _get_session(game_id)
    human_ids: set = session.get("human_ids", set())
    has_human: bool = session.get("has_human", bool(human_ids))
    cfg: Config = session["cfg"]
    rng: RNG = session["rng"]

    kpol = get_king_policy(getattr(cfg, "KING_POLICY", "RANDOM"), cfg)
    # [092]/[093] Política de bots = TECHO REAL 23.0% (COMMITTEE v5).
    # Default: PPO con models/maskable_ppo_carcosa_final_20260805_154245.zip
    # (modelo 23.0% real, no el FALSIFICADO de jitter 20260806_185139).
    # Si se pide GOAL explícitamente en el request, se respeta (override abajo).
    bot_policy_name = "PPO"
    model_path = getattr(session.get("start_request"), "ppo_model_path", None) or \
        "models/maskable_ppo_carcosa_final_20260805_154245.zip"
    req_bot_policy = getattr(session.get("start_request"), "bot_policy", "PPO").upper()
    if req_bot_policy == "GOAL":
        bot_policy_name = "GOAL"
        model_path = None
    elif req_bot_policy in ("PPO", "COMMITTEE") and model_path:
        bot_policy_name = req_bot_policy
    try:
        ppol = get_player_policy(bot_policy_name, cfg, model_path=model_path)
    except Exception as e:
        print(f"[AUTO_ADVANCE] No se pudo cargar policy '{bot_policy_name}': {e}. "
              f"Usando GOAL.")
        ppol = get_player_policy("GOAL", cfg)

    # Si no hay humanos, la partida es 100% bots: correr hasta game_over.
    # Si hay humanos, tope de seguridad para no bloquear la respuesta HTTP.
    max_iter: int = 5000 if not has_human else 200
    it: int = 0

    while it < max_iter:
        state: GameState = session["state"]
        if state.game_over:
            break

        actor: str = _active_actor(state)
        # ¿Es humano? → parar y esperar input (solo aplica si hay humanos)
        if has_human and actor in human_ids:
            break

        try:
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
        except ValueError as e:
            # Bot eligió acción ilegal y el fallback también falló: forzar END_TURN
            print(f"[AUTO_ADVANCE] Illegal bot action for {actor}: {e}. Forcing END_TURN.")
            try:
                _single_step(session, actor, "END_TURN", {}, "bot_fallback")
            except ValueError as e2:
                print(f"[AUTO_ADVANCE] END_TURN also illegal for {actor}: {e2}. Stopping loop.")
                break

        # Broadcast state after each bot action
        await _broadcast_state(game_id)
        it += 1

        # Ritmo de espectador: pausa para que el cliente vea los frames a velocidad humana
        if delay > 0:
            await asyncio.sleep(delay)


# ── Persistencia de partidas terminadas ───────────────────────────────────────

def _fs_index_append(entry: Dict[str, Any]) -> None:
    try:
        os.makedirs("runs", exist_ok=True)
        with open(FS_GAMES_INDEX, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[FS] Error writing games index: {e}")


def _fs_index_read() -> List[Dict[str, Any]]:
    if not os.path.exists(FS_GAMES_INDEX):
        return []
    entries: List[Dict[str, Any]] = []
    try:
        with open(FS_GAMES_INDEX) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        print(f"[FS] Error reading games index: {e}")
    # Dedup por id (la entrada más reciente gana), más nuevas primero
    by_id: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        by_id[e.get("id", "")] = e
    return sorted(by_id.values(), key=lambda e: e.get("completed_at", ""), reverse=True)


async def _persist_game(game_id: str, session: Dict[str, Any]) -> str:
    """Guarda la partida (registros JSONL + metadata) en PostgreSQL o filesystem."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    seed = session["seed"]
    jsonl_data = write_jsonl_to_string(session["records"])
    human_ids = sorted(session.get("human_ids", set()))
    state: GameState = session["state"]

    saved_to = None

    # Try PostgreSQL first
    if _db_pool:
        try:
            async with _db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO carcosa_games (id, seed, completed_at, outcome, rounds, jsonl_data, human_players)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO UPDATE SET
                        completed_at = EXCLUDED.completed_at,
                        outcome = EXCLUDED.outcome,
                        rounds = EXCLUDED.rounds,
                        jsonl_data = EXCLUDED.jsonl_data,
                        human_players = EXCLUDED.human_players
                """, game_id, seed, datetime.now(), state.outcome, state.round, jsonl_data, human_ids)
            saved_to = f"postgresql://carcosa_games/{game_id}"
            print(f"[DB] Game {game_id} saved to PostgreSQL")
        except Exception as e:
            print(f"[DB] PostgreSQL save failed: {e}, falling back to filesystem")

    # Fallback: filesystem (for local dev / backup)
    if not saved_to:
        out_dir = os.path.join("runs", f"human_{ts}_seed{seed}_{game_id}")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "human.jsonl")
        write_jsonl(path, session["records"])
        saved_to = path
        _fs_index_append({
            "id": game_id,
            "seed": seed,
            "completed_at": datetime.now().isoformat(),
            "outcome": state.outcome,
            "rounds": state.round,
            "human_players": human_ids,
            "steps": len(session["records"]),
            "path": path,
        })
        print(f"[FS] Game {game_id} saved to {path}")

    session["saved_to"] = saved_to
    return saved_to


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/start")
async def start_game(req: StartRequest) -> Dict[str, Any]:
    """
    Inicia una nueva partida. Retorna game_id + estado inicial.

    Asientos: players_config = [{pid, roleId?, control}] con control:
      - "local":  humano en el navegador del host (hotseat)
      - "remote": humano que se unirá desde otro navegador (amigo)
      - "bot":    IA del servidor (policy=GOAL)
    Compat: si players_config viene vacío, `players` = lista de humanos (todos locales).

    Roles: draw_mode = RANDOM_UNIQUE (canónico) | FIXED | RANDOM_WITH_REPLACEMENT.
    En FIXED, roleId por asiento se respeta si viene en players_config.
    """
    game_id = str(uuid.uuid4())[:8]
    cfg = Config()

    valid_pids = {"P1", "P2", "P3", "P4"}
    draw_mode = (req.draw_mode or "").upper()
    if draw_mode in ("FIXED", "RANDOM_UNIQUE", "RANDOM_WITH_REPLACEMENT"):
        import dataclasses
        cfg = dataclasses.replace(cfg, ROLE_DRAW_MODE=draw_mode)

    human_ids: set = set()
    local_ids: set = set()
    explicit_roles: Dict[str, str] = {}

    if req.players_config:
        for pc in req.players_config:
            pid = str(pc.get("pid", ""))
            if pid not in valid_pids:
                continue
            control = str(pc.get("control", "")).lower()
            if not control:
                control = "local" if pc.get("isHuman") else "bot"
            if control in ("local", "human", "yo"):
                human_ids.add(pid)
                local_ids.add(pid)
            elif control in ("remote", "friend", "amigo"):
                human_ids.add(pid)
            role_id = pc.get("roleId") or pc.get("role_id")
            if role_id:
                explicit_roles[pid] = str(role_id).upper()
    else:
        human_ids = {p for p in req.players if p in valid_pids}
        local_ids = set(human_ids)

    # Siempre crear estado completo (4 jugadores). El engine lo requiere.
    state = make_smoke_state(seed=req.seed, cfg=cfg)

    # Roles explícitos del lobby (solo en FIXED: asignación determinista elegida por el host)
    if draw_mode == "FIXED" and explicit_roles:
        from engine.roles import get_sanity_max, get_starting_items
        from engine.catalogs.roles import ROLE_CATALOG
        for pid_obj, p in state.players.items():
            role = explicit_roles.get(str(pid_obj))
            if role and role in ROLE_CATALOG and role != p.role_id:
                p.role_id = role
                p.sanity_max = get_sanity_max(role)
                p.sanity = p.sanity_max
                p.objects = list(get_starting_items(role))
        state.roles_assigned = {str(pid): p.role_id for pid, p in state.players.items()}

    # RNG independiente para gameplay (igual que runner.py)
    game_rng = RNG(req.seed)

    all_ids = [str(pid) for pid in state.players.keys()]
    bot_ids = [pid for pid in all_ids if pid not in human_ids]

    # Validación: debe haber al menos un jugador (humano o bot).
    # Permitimos 0 humanos (partida 100% bots = modo espectador en vivo).
    if not human_ids and not bot_ids:
        raise HTTPException(status_code=400, detail="Debe haber al menos un jugador (humano o bot).")

    seat_claims: Dict[str, str] = {}
    if req.client_id:
        for pid in local_ids:
            seat_claims[pid] = req.client_id

    _sessions[game_id] = {
        "state": state,
        "rng": game_rng,
        "cfg": cfg,
        "seed": req.seed,
        "records": [],
        "step_idx": 0,
        "human_ids": human_ids,
        "bot_ids": set(bot_ids),
        "has_human": bool(human_ids),
        "seat_claims": seat_claims,
        "saved_to": None,
        # [092] Andamiaje PPO: guardo el request para que _auto_advance_until_human
        # lea bot_policy/ppo_model_path sin acoplar la firma. Por defecto GOAL.
        "start_request": req,
    }

    # Avanzar automáticamente si el primer turno es de un bot o de KING.
    # En modo espectador (sin humanos) lo corremos en background con ritmo
    # humano, para que el cliente reciba el game_id al instante y vea los
    # frames llegar por WebSocket a velocidad visible (no un burst final).
    if not human_ids:
        BOT_STEP_DELAY = 0.35  # segundos entre pasos en modo espectador
        asyncio.create_task(_auto_advance_until_human(game_id, delay=BOT_STEP_DELAY))
    else:
        await _auto_advance_until_human(game_id)

    # Guardar sesión activa en disco
    save_session_to_disk(game_id)

    session = _sessions[game_id]
    return {"game_id": game_id, "state": _state_summary(session["state"], session)}


@app.post("/claim")
async def claim_seats(req: ClaimRequest) -> Dict[str, Any]:
    """
    Reclama asiento(s) humano(s) para un cliente (navegador) identificado por client_id.
    Evita que dos navegadores controlen el mismo asiento. Reclamar con una lista nueva
    libera los asientos que ese cliente tenía y ya no pide.
    """
    session = _get_session(req.game_id)
    human_ids: set = session.get("human_ids", set())
    claims: Dict[str, str] = session.setdefault("seat_claims", {})
    mode = (req.mode or "add").lower()

    if mode == "release":
        targets = req.seats or [s for s, c in claims.items() if c == req.client_id]
        for seat in targets:
            if claims.get(seat) == req.client_id:
                del claims[seat]
    else:
        for seat in req.seats:
            if seat not in human_ids:
                raise HTTPException(status_code=400, detail=f"El asiento {seat} no es humano en esta partida.")
            owner = claims.get(seat)
            if owner and owner != req.client_id and not req.takeover:
                raise HTTPException(status_code=409, detail=f"El asiento {seat} ya está ocupado por otro jugador.")
        if mode == "replace":
            for seat in [s for s, c in claims.items() if c == req.client_id and s not in req.seats]:
                del claims[seat]
        for seat in req.seats:
            claims[seat] = req.client_id

    save_session_to_disk(req.game_id)
    await _broadcast_state(req.game_id)

    return {
        "game_id": req.game_id,
        "claimed": [s for s, c in claims.items() if c == req.client_id],
        "seats": {
            "humans": sorted(human_ids),
            "bots": sorted(session.get("bot_ids", set())),
            "claims": dict(claims),
        },
    }


@app.get("/state/{game_id}")
def get_state(game_id: str) -> Dict[str, Any]:
    """Retorna el estado actual de una partida."""
    session = _get_session(game_id)
    return {"game_id": game_id, "state": _state_summary(session["state"], session)}


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

    # Enforcement de asientos: un asiento reclamado solo puede ser jugado por su dueño.
    claims: Dict[str, str] = session.get("seat_claims", {})
    owner = claims.get(req.actor)
    if owner and owner != req.client_id:
        raise HTTPException(
            status_code=403,
            detail=f"El asiento {req.actor} está controlado por otro jugador."
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

    # Ejecutar la acción del humano (step() valida legalidad)
    try:
        next_state = _single_step(session, req.actor, req.action_type, req.action_data, "human")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Acción ilegal: {e}")

    # Broadcast state update after human action
    await _broadcast_state(req.game_id)

    # Avanzar automáticamente hasta que toque otro humano
    await _auto_advance_until_human(req.game_id)

    # El estado final es el que quedó después del auto-advance
    final_state: GameState = session["state"]

    # Persistencia: auto-guardar registro al terminar; si sigue viva, respaldar sesión
    if final_state.game_over:
        if not session.get("saved_to"):
            await _persist_game(req.game_id, session)
        delete_session_from_disk(req.game_id)
    else:
        save_session_to_disk(req.game_id)

    # Broadcast final state after auto-advance (incluye saved_to si terminó)
    await _broadcast_state(req.game_id)

    return {
        "game_id": req.game_id,
        "state": _state_summary(final_state, session),
        "done": bool(final_state.game_over),
        "outcome": final_state.outcome,
        "step": session["step_idx"],
        "saved_to": session.get("saved_to"),
    }


@app.post("/save/{game_id}")
async def save_game(game_id: str) -> Dict[str, Any]:
    """
    Guarda la sesión en PostgreSQL (y filesystem como fallback).
    Compatible con ai_ready_export.py y train_bc.py.
    Idempotente: si la partida ya fue auto-guardada, devuelve ese registro.
    """
    session = _get_session(game_id)
    saved_to = session.get("saved_to")
    if not saved_to:
        saved_to = await _persist_game(game_id, session)
    if session["state"].game_over:
        delete_session_from_disk(game_id)

    return {
        "game_id": game_id,
        "saved_to": saved_to,
        "steps": len(session["records"]),
        "outcome": session["state"].outcome,
    }


@app.get("/setup_preview/{seed}")
def setup_preview(seed: int, draw_mode: str = "") -> Dict[str, Any]:
    """
    Preview REAL del setup para una semilla: habitaciones especiales y roles,
    calculado con el mismo código del engine (no aproximación en JS).
    """
    cfg = Config()
    dm = (draw_mode or "").upper()
    if dm in ("FIXED", "RANDOM_UNIQUE", "RANDOM_WITH_REPLACEMENT"):
        import dataclasses
        cfg = dataclasses.replace(cfg, ROLE_DRAW_MODE=dm)
    try:
        state = make_smoke_state(seed=seed, cfg=cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo generar preview: {e}")

    specials = [
        {"room": str(rid), "special_id": r.special_card_id}
        for rid, r in state.rooms.items()
        if r.special_card_id
    ]
    return {
        "seed": seed,
        "draw_mode": cfg.ROLE_DRAW_MODE,
        "special_rooms": sorted(specials, key=lambda s: s["room"]),
        "roles": {str(pid): p.role_id for pid, p in state.players.items()},
    }


FS_REPORTS_PATH = os.path.join("runs", "bug_reports.jsonl")


@app.post("/report")
async def submit_report(req: ReportRequest) -> Dict[str, Any]:
    """
    Guarda un reporte de error enviado desde el frontend (HALI).
    PostgreSQL si hay pool (Render: el filesystem es efímero); si no, jsonl local.
    """
    description = (req.description or "").strip()
    if not description:
        raise HTTPException(status_code=400, detail="El reporte necesita una descripción.")
    if len(description) > 4000:
        description = description[:4000]

    category = (req.category or "otro")[:32]

    # Contexto acotado y SIEMPRE JSON válido: si excede el límite, se reemplaza
    # por un marcador (nunca se corta a media cadena — eso rompía /reports).
    context_json = json.dumps(_json_safe(req.context or {}), ensure_ascii=False)
    if len(context_json) > 60_000:
        context_json = json.dumps({"_truncated": True, "original_size": len(context_json)})
    context_stored = json.loads(context_json)

    report_id = str(uuid.uuid4())[:8]
    created_at = datetime.now()

    saved_to = None
    if _db_pool:
        try:
            async with _db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO carcosa_reports (id, game_id, client_id, category, description, context, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    report_id, req.game_id, req.client_id,
                    category, description, context_json, created_at,
                )
            saved_to = "postgresql://carcosa_reports"
        except Exception as e:
            print(f"[REPORT] PG save failed: {e}, falling back to filesystem")

    if not saved_to:
        try:
            os.makedirs("runs", exist_ok=True)
            with open(FS_REPORTS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "id": report_id,
                    "game_id": req.game_id,
                    "client_id": req.client_id,
                    "category": category,
                    "description": description,
                    "context": context_stored,
                    "created_at": created_at.isoformat(),
                }, ensure_ascii=False) + "\n")
            saved_to = FS_REPORTS_PATH
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"No se pudo guardar el reporte: {e}")

    print(f"[REPORT] {report_id} ({req.category}) game={req.game_id}: {description[:80]}")
    return {"report_id": report_id, "saved_to": saved_to}


@app.get("/reports")
async def list_reports(limit: int = 100) -> Dict[str, Any]:
    """Lista los reportes de error acumulados (para recolectarlos y triarlos)."""
    limit = max(1, min(1000, int(limit)))

    def _safe_ctx(raw: Any) -> Any:
        # Una fila con JSON corrupto no debe tumbar todo el listado.
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"_corrupt": True}

    if _db_pool:
        try:
            async with _db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, game_id, client_id, category, description, context, created_at
                    FROM carcosa_reports ORDER BY created_at DESC LIMIT $1
                """, limit)
            return {
                "reports": [
                    {
                        "id": r["id"], "game_id": r["game_id"], "client_id": r["client_id"],
                        "category": r["category"], "description": r["description"],
                        "context": _safe_ctx(r["context"]),
                        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                    }
                    for r in rows
                ],
                "storage": "postgresql",
            }
        except Exception as e:
            print(f"[REPORT] PG list failed: {e}, falling back to filesystem")

    reports: List[Dict[str, Any]] = []
    if os.path.exists(FS_REPORTS_PATH):
        with open(FS_REPORTS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        reports.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    reports.reverse()
    return {"reports": reports[:limit], "storage": "filesystem"}


@app.get("/health")
def health() -> Dict[str, Any]:
    """Health check básico."""
    return {
        "status": "ok",
        "active_sessions": len(_sessions),
        "ws_connections": {gid: len(conns) for gid, conns in _ws_connections.items()},
        "db_connected": _db_pool is not None,
    }


@app.get("/games")
async def list_games(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Lista partidas guardadas (PostgreSQL, o índice filesystem como fallback)."""
    if _db_pool:
        async with _db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, seed, created_at, completed_at, outcome, rounds, human_players
                FROM carcosa_games
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """, limit, offset)
            total = await conn.fetchval("SELECT COUNT(*) FROM carcosa_games")
        return {
            "games": [
                {
                    "id": row["id"],
                    "seed": row["seed"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
                    "outcome": row["outcome"],
                    "rounds": row["rounds"],
                    "human_players": row["human_players"],
                }
                for row in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "storage": "postgresql",
        }

    entries = _fs_index_read()
    return {
        "games": entries[offset:offset + limit],
        "total": len(entries),
        "limit": limit,
        "offset": offset,
        "storage": "filesystem",
    }


@app.get("/games/{game_id}/download")
async def download_game(game_id: str):
    """Descarga el JSONL de una partida guardada (PG o filesystem)."""
    if _db_pool:
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT jsonl_data FROM carcosa_games WHERE id = $1
            """, game_id)
        if row:
            return Response(
                content=row["jsonl_data"],
                media_type="application/x-ndjson",
                headers={"Content-Disposition": f"attachment; filename={game_id}.jsonl"}
            )

    entry = next((e for e in _fs_index_read() if e.get("id") == game_id), None)
    if entry and entry.get("path") and os.path.exists(entry["path"]):
        return FileResponse(
            entry["path"],
            media_type="application/x-ndjson",
            filename=f"{game_id}.jsonl",
        )

    raise HTTPException(status_code=404, detail="Game not found")


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws/{game_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    """
    WebSocket endpoint for real-time game state updates with keepalive.
    """
    await websocket.accept()

    session = _sessions.get(game_id)
    if not session:
        # Partida inexistente (expirada o server reiniciado sin sesión): avisar y cerrar
        # en vez de dejar al cliente esperando updates que nunca llegarán.
        try:
            await websocket.send_text(json.dumps({"type": "error", "code": "game_not_found", "detail": f"Partida {game_id} no existe."}))
            await websocket.close()
        except Exception:
            pass
        return

    # Register connection
    if game_id not in _ws_connections:
        _ws_connections[game_id] = set()
    _ws_connections[game_id].add(websocket)

    # Send current state immediately upon connection
    await websocket.send_text(json.dumps({
        "type": "state_update",
        "state": _state_summary(session["state"], session),
        "active_player": _active_actor(session["state"]),
    }))

    try:
        while True:
            try:
                # Esperar mensajes del cliente o mantener conexión viva con timeouts
                data = await asyncio.wait_for(websocket.receive_text(), timeout=20.0)
            except asyncio.TimeoutError:
                # Enviar ping al cliente
                await websocket.send_text(json.dumps({"type": "ping"}))
    except Exception:
        pass
    finally:
        # Remove connection
        if game_id in _ws_connections:
            _ws_connections[game_id].discard(websocket)
            if not _ws_connections[game_id]:
                _ws_connections.pop(game_id, None)

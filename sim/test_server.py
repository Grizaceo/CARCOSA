"""
sim/test_server.py — Script de test manual para game_server (Sprint 1).

Ejecutar con el servidor corriendo en otro terminal:
    python3 -m uvicorn sim.game_server:app --host 127.0.0.1 --port 8765

Luego en otro terminal:
    cd /ruta/al/proyecto && python3 sim/test_server.py
"""

import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8765"


def req(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = json.loads(e.read())
        print(f"  ERROR {e.code}: {detail}")
        sys.exit(1)


def main():
    print("=" * 60)
    print("CARCOSA Game Server — Test Manual (Sprint 1)")
    print("=" * 60)

    # 1. Health check
    print("\n[1] GET / (health check)")
    r = req("GET", "/")
    print(" ", r)
    assert r["status"] == "ok"

    # 2. Start game
    print("\n[2] POST /start  seed=1")
    r = req("POST", "/start", {"seed": 1})
    game_id = r["game_id"]
    state = r["state"]
    print(f"  game_id: {game_id}")
    print(f"  active_actor: {state['active_actor']}")
    print(f"  round: {state['round']} phase: {state['phase']}")
    print(f"  players: {list(state['players'].keys())}")

    # 3. Get state
    print(f"\n[3] GET /state/{game_id}")
    r = req("GET", f"/state/{game_id}")
    print(f"  phase={r['state']['phase']} actor={r['state']['active_actor']}")

    # 4. Get legal actions
    actor = state["active_actor"]
    print(f"\n[4] GET /legal/{game_id}/{actor}")
    r = req("GET", f"/legal/{game_id}/{actor}")
    actions = r["actions"]
    print(f"  {len(actions)} acciones legales para {actor}")
    for a in actions[:5]:
        print(f"    - {a['type']}  data={a['data']}")

    if not actions:
        print("  ERROR: No hay acciones legales")
        sys.exit(1)

    # 5. Apply first action
    first_action = actions[0]
    print(f"\n[5] POST /act  actor={actor} type={first_action['type']}")
    r = req(
        "POST",
        "/act",
        {
            "game_id": game_id,
            "actor": actor,
            "action_type": first_action["type"],
            "action_data": first_action["data"],
        },
    )
    print(f"  done={r['done']} outcome={r['outcome']}")
    print(f"  new active_actor: {r['state']['active_actor']}")

    # 6. Save session
    print(f"\n[6] POST /save/{game_id}")
    r = req("POST", f"/save/{game_id}")
    print(f"  saved_to: {r['saved_to']}")
    print(f"  steps: {r['steps']}")

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON OK")
    print("=" * 60)


if __name__ == "__main__":
    main()

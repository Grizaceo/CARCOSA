"""E2E: partida completa hasta Game Over. Browser host + driver HTTP que juega P1 rápido.
Verifica: overlay de Game Over en el navegador, auto-guardado server-side, /games y download."""
import asyncio, json, re, sys, urllib.request
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8799"
FAILURES = []

def check(cond, msg):
    print(f"[{'OK ' if cond else 'FAIL'}] {msg}")
    if not cond:
        FAILURES.append(msg)

def http(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data=data, timeout=30) as r:
        return json.loads(r.read())

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await (await browser.new_context()).new_page()
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        await page.goto(BASE + "/")
        await page.wait_for_selector("#typeP1")
        await page.fill("#seed", "23")
        # P2 → BOT (ciclar remote→bot)
        await page.click("#typeP2")
        check((await page.get_attribute("#typeP2", "data-control")) == "bot", "P2 configurado como BOT")
        await page.click("#btnStart")
        await page.wait_for_selector("#gameView:not(.hidden)", timeout=15000)
        game_id = (await page.inner_text("#activeGameId")).strip()
        print("   game:", game_id)

        # Driver HTTP toma control de P1 (enforcement estricto: hay que reclamar el asiento)
        http("POST", "/claim", {"game_id": game_id, "client_id": "e2e-driver", "seats": ["P1"], "mode": "add", "takeover": True})
        done, outcome, steps = False, None, 0
        for i in range(3000):
            st = http("GET", f"/state/{game_id}")["state"]
            if st["game_over"]:
                done, outcome = True, st["outcome"]
                break
            actor = st["active_actor"]
            if actor != "P1":
                await asyncio.sleep(0.05)
                continue
            legal = http("GET", f"/legal/{game_id}/P1")["actions"]
            if not legal:
                await asyncio.sleep(0.05)
                continue
            # preferir END_TURN para acelerar; si hay sacrificio, tomar la primera opción
            act = next((a for a in legal if a["type"] == "SACRIFICE"), None) \
                or next((a for a in legal if a["type"] == "ACCEPT_SACRIFICE"), None) \
                or next((a for a in legal if a["type"] == "END_TURN"), legal[0])
            r = http("POST", "/act", {"game_id": game_id, "actor": "P1", "client_id": "e2e-driver",
                                      "action_type": act["type"], "action_data": act["data"]})
            steps += 1
            if r["done"]:
                done, outcome = True, r["outcome"]
                check(r.get("saved_to"), f"respuesta /act final incluye saved_to: {r.get('saved_to')}")
                break
        check(done, f"partida llegó a game over (outcome={outcome}, acciones P1={steps})")

        # El navegador debe mostrar el overlay de Game Over vía WS
        try:
            await page.wait_for_selector("#gameOverOverlay:not(.hidden)", timeout=15000)
            title = (await page.inner_text("#gameOverTitle")).strip()
            details = (await page.inner_text("#gameOverDetails")).strip()
            check(bool(title), f"overlay Game Over visible: '{title}'")
            check("Rondas jugadas" in details, "detalles de la partida en overlay")
        except Exception as e:
            check(False, f"overlay Game Over no apareció: {e}")

        logs = await page.inner_text("#logContent")
        check("Registro de partida guardado" in logs, "bitácora registra el guardado de la partida")

        # Registro de partidas: /games y download
        games = http("GET", "/games")
        ids = [g["id"] for g in games["games"]]
        check(game_id in ids, f"/games lista la partida ({games['storage']}, total={games['total']})")
        entry = next(g for g in games["games"] if g["id"] == game_id)
        check(entry["outcome"] == outcome and entry["rounds"] >= 1, f"metadata: outcome={entry['outcome']} rounds={entry['rounds']} humans={entry['human_players']}")
        jsonl = urllib.request.urlopen(f"{BASE}/games/{game_id}/download", timeout=30).read().decode()
        lines = [l for l in jsonl.strip().split("\n") if l]
        rec0 = json.loads(lines[0])
        check(len(lines) > 20 and "action" in json.dumps(rec0), f"JSONL descargable con {len(lines)} transiciones")

        check(not errors, f"sin errores JS: {errors[:2]}")
        await browser.close()

    print("\n" + ("TODOS LOS CHECKS PASARON ✅" if not FAILURES else f"{len(FAILURES)} FALLAS ❌"))
    sys.exit(1 if FAILURES else 0)

asyncio.run(main())

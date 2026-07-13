"""E2E: rejoin tras F5 (host y guest), liberación de asientos al salir, tomar control."""
import asyncio, sys
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8799"
FAILURES = []

def check(cond, msg):
    print(f"[{'OK ' if cond else 'FAIL'}] {msg}")
    if not cond:
        FAILURES.append(msg)

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        host_ctx = await browser.new_context()
        guest_ctx = await browser.new_context()
        host = await host_ctx.new_page()
        guest = await guest_ctx.new_page()
        for p in (host, guest):
            p.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        errors = []
        host.on("pageerror", lambda e: errors.append("host:" + str(e)))
        guest.on("pageerror", lambda e: errors.append("guest:" + str(e)))

        # Host crea partida P1=YO, P2=AMIGO, bots
        await host.goto(BASE + "/")
        await host.wait_for_selector("#typeP1")
        await host.fill("#seed", "31")
        await host.click("#btnStart")
        await host.wait_for_selector("#gameView:not(.hidden)", timeout=15000)
        game_id = (await host.inner_text("#activeGameId")).strip()
        print("   game:", game_id)

        # Guest se une como P2
        await guest.goto(f"{BASE}/?game={game_id}")
        await guest.click("#btnJoinGame")
        await guest.wait_for_selector(".seat-choice", timeout=8000)
        await guest.click(".seat-choice[data-seat='P2']")
        await guest.wait_for_selector("#gameView:not(.hidden)", timeout=8000)

        # ── F5 del host: debe volver directo a la partida con P1 ──
        await host.reload()
        try:
            await host.wait_for_selector("#gameView:not(.hidden)", timeout=10000)
            logs = await host.inner_text("#logContent")
            check("Reconectado" in logs, "host rejoin automático tras F5")
            check("como P1" in logs, "host recupera su asiento P1")
        except Exception as e:
            check(False, f"host no volvió a la partida tras F5: {e}")

        # ── F5 del guest ──
        await guest.reload()
        try:
            await guest.wait_for_selector("#gameView:not(.hidden)", timeout=10000)
            logs = await guest.inner_text("#logContent")
            check("como P2" in logs, "guest rejoin automático con P2")
        except Exception as e:
            check(False, f"guest no volvió tras F5: {e}")

        # Sin replay masivo de overlays al reconectar
        overlay_visible = await host.eval_on_selector("#cardRevealOverlay", "e => !e.classList.contains('hidden')")
        check(not overlay_visible, "sin overlay de carta atascado tras rejoin")

        # ── Guest sale → asiento P2 liberado; host puede tomar control ──
        await guest.click("#btnLeaveGame")
        await asyncio.sleep(1.0)
        import json as _json, urllib.request
        st = _json.loads(urllib.request.urlopen(f"{BASE}/state/{game_id}").read())["state"]
        check("P2" not in st["seats"]["claims"], f"leaveGame liberó P2 (claims: {st['seats']['claims']})")
        # Botón unirse reactivado en guest
        btn_ok = await guest.eval_on_selector("#btnJoinGame", "b => !b.disabled")
        check(btn_ok, "botón Unirse reactivado tras salir")
        btn_start_ok = await guest.eval_on_selector("#btnStart", "b => !b.disabled")
        check(btn_start_ok, "botón Crear reactivado tras salir")

        # Host: cuando toque P2, debe aparecer 'Tomar control'
        took = False
        for i in range(30):
            await asyncio.sleep(0.5)
            actor = (await host.inner_text("#activeActorSpan")).strip()
            if actor == "P2":
                try:
                    await host.wait_for_selector("#actionsGrid button:has-text('Tomar control')", timeout=3000)
                    await host.click("#actionsGrid button:has-text('Tomar control')")
                    await host.wait_for_selector("#actionsGrid button.action-btn:has-text('Finalizar')", timeout=6000)
                    took = True
                    break
                except Exception:
                    pass
            elif actor == "P1":
                # jugar END_TURN para avanzar hasta P2
                try:
                    await host.click("#actionsGrid button.action-btn:has-text('Finalizar Turno')", timeout=3000)
                except Exception:
                    pass
        check(took, "host tomó control de P2 abandonado y ve sus acciones")

        check(not errors, f"sin errores JS: {errors[:3]}")
        await browser.close()

    print("\n" + ("TODOS LOS CHECKS PASARON ✅" if not FAILURES else f"{len(FAILURES)} FALLAS ❌"))
    sys.exit(1 if FAILURES else 0)

asyncio.run(main())

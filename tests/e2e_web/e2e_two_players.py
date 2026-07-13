"""E2E: host + invitado juegan CARCOSA en dos navegadores contra el server local."""
import asyncio, re, sys
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8799"
FAILURES = []

def check(cond, msg):
    tag = "OK " if cond else "FAIL"
    print(f"[{tag}] {msg}")
    if not cond:
        FAILURES.append(msg)

async def get_buttons(page):
    return await page.eval_on_selector_all(
        "#actionsGrid button.action-btn",
        "els => els.map(e => e.textContent.trim())"
    )

async def grid_text(page):
    return (await page.inner_text("#actionsGrid")).strip()

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        host_ctx = await browser.new_context()
        guest_ctx = await browser.new_context()
        host = await host_ctx.new_page()
        guest = await guest_ctx.new_page()
        host.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        guest.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        errors = {"host": [], "guest": []}
        host.on("pageerror", lambda e: errors["host"].append(str(e)))
        guest.on("pageerror", lambda e: errors["guest"].append(str(e)))

        # ── HOST: crear partida ────────────────────────────────────────────
        await host.goto(BASE + "/")
        await host.wait_for_selector("#lobbyView:not(.hidden)")
        await host.fill("#seed", "11")
        await host.wait_for_selector("#typeP1")
        # Defaults: P1=YO, P2=AMIGO, P3/P4=BOT
        ctl = {}
        for pid in ["P1", "P2", "P3", "P4"]:
            ctl[pid] = await host.get_attribute(f"#type{pid}", "data-control")
        check(ctl == {"P1": "local", "P2": "remote", "P3": "bot", "P4": "bot"},
              f"defaults de asientos: {ctl}")
        # Validador de setup real
        await host.wait_for_selector("#validatorContent .validator-row", timeout=8000)
        vtext = await host.inner_text("#validatorContent")
        check("Setup real del engine" in vtext, "validador usa preview real del servidor")

        await host.click("#btnStart")
        await host.wait_for_selector("#gameView:not(.hidden)", timeout=15000)
        game_id = (await host.inner_text("#activeGameId")).strip()
        check(re.fullmatch(r"[0-9a-f]{8}", game_id) is not None, f"game id: {game_id}")

        # ── GUEST: unirse por link y reclamar P2 ──────────────────────────
        await guest.goto(f"{BASE}/?game={game_id}")
        await guest.wait_for_selector("#joinExistingGame:not(.hidden)")
        await guest.click("#btnJoinGame")
        await guest.wait_for_selector(".seat-choice", timeout=8000)
        seats = await guest.eval_on_selector_all(".seat-choice", "els => els.map(e => [e.dataset.seat, e.dataset.taken])")
        free = [s for s, t in seats if not t]
        taken = [s for s, t in seats if t]
        check(free == ["P2"] and taken == ["P1"], f"picker: libres={free}, ocupados={taken}")
        await guest.click(".seat-choice[data-seat='P2']")
        await guest.wait_for_selector("#gameView:not(.hidden)", timeout=8000)
        check(True, "invitado dentro de la partida como P2")

        # ── Jugar turnos alternados ───────────────────────────────────────
        pages = {"host": (host, ["P1"]), "guest": (guest, ["P2"])}
        turns_played = 0
        dup_found = False
        for step in range(40):
            await asyncio.sleep(0.6)
            actor = (await host.inner_text("#activeActorSpan")).strip()
            if actor in ("P1",):
                page, other = host, guest
            elif actor in ("P2",):
                page, other = guest, host
            else:
                continue  # bot/KING: el server avanza solo

            try:
                await page.wait_for_selector("#actionsGrid button.action-btn", timeout=6000)
            except Exception:
                continue
            # chequear duplicados exactos
            btns = await get_buttons(page)
            if len(btns) != len(set(btns)):
                dup_found = True
                print("   DUP:", [b for b in btns if btns.count(b) > 1][:4])
            # el otro jugador NO debe ver botones de acción
            other_btns = await get_buttons(other)
            other_txt = await grid_text(other)
            if other_btns:
                check(False, f"turno de {actor}: el otro navegador ve botones {other_btns[:3]}")
            elif step == 2:
                check("Esperando" in other_txt or "bot" in other_txt or "Rey" in other_txt,
                      f"otro navegador muestra espera: '{other_txt[:60]}'")

            # jugar: preferir un MOVE la primera acción, si no Finalizar Turno
            target = None
            for b in btns:
                if "Sacrificar" in b or "Acceptar" in b:
                    target = b; break
            if target is None:
                moves = [b for b in btns if b.startswith("🚶")]
                ends = [b for b in btns if "Finalizar Turno" in b]
                target = (moves[0] if moves and step % 3 == 0 else (ends[0] if ends else btns[0]))
            await page.click(f"#actionsGrid button.action-btn:has-text('{target.split(chr(10))[0][:25]}')")
            turns_played += 1

        check(not dup_found, "sin botones de acción duplicados en 40 pasos")
        check(turns_played >= 10, f"acciones humanas jugadas: {turns_played}")

        # logs visibles en ambos
        host_logs = await host.eval_on_selector_all("#logContent .log-entry", "els => els.length")
        guest_logs = await guest.eval_on_selector_all("#logContent .log-entry", "els => els.length")
        check(host_logs > 10 and guest_logs > 10, f"bitácora poblada (host={host_logs}, guest={guest_logs})")

        rnd = (await host.inner_text("#roundPill")).strip()
        print(f"   estado final: {rnd}, actor={await host.inner_text('#activeActorSpan')}")

        check(not errors["host"], f"sin errores JS en host: {errors['host'][:2]}")
        check(not errors["guest"], f"sin errores JS en guest: {errors['guest'][:2]}")

        await browser.close()

    print("\n" + ("TODOS LOS CHECKS PASARON ✅" if not FAILURES else f"{len(FAILURES)} FALLAS ❌"))
    sys.exit(1 if FAILURES else 0)

asyncio.run(main())

# E2E del playtest web (Playwright)

Requisitos: `pip install playwright && playwright install chromium`.

```bash
# terminal 1
uvicorn sim.game_server:app --host 127.0.0.1 --port 8799
# terminal 2
python tests/e2e_web/e2e_two_players.py   # host+invitado, turnos, sin duplicados
python tests/e2e_web/e2e_rejoin.py        # F5, liberar asiento, tomar control
python tests/e2e_web/e2e_gameover.py      # partida completa, auto-guardado, /games
```

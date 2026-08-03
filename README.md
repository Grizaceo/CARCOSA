# CARCOSA

Motor de simulación, entrenamiento y documentación canónica para el juego de mesa cooperativo **CARCOSA** (universo *The Yellow King / Carcosa*): 3 pisos, 12 habitaciones + pasillos, 4 jugadores vs monstruos y el Rey, recolectar 4 llaves y escapar por el Umbral.

El repositorio combina tres capas:

- `engine/`: reglas, estado, tablero, cartas, monstruos, habitaciones especiales y condiciones de victoria/derrota. **Fuente única de verdad del juego.**
- `sim/` y `train/`: simulación headless, server multijugador, políticas de bots, behavioral cloning y reinforcement learning.
- `web/`, `web/hali/`, `godot_client/`: tres frontends jugables (2D canvas, isométrico 2.5D, y 3D Godot).
- `docs/` y `documentos/`: canon operativo, reportes técnicos y material de referencia.

## Regla de oro

**El motor (`engine/`) es la única fuente de verdad de las reglas.** Los frontends (`web/`, `web/hali/`, `godot_client/`) NO implementan reglas: leen `GET /legal` + `GET /state` y envían `POST /act`. Para cambiar una regla, se edita `engine/`, no el JS/GDP.

## Estado del proyecto (2026-08-03)

- Motor de reglas determinista (verificado byte-a-byte, seed 42, 300 pasos, 2 corridas idénticas).
- **439 tests pasan** (1 deseleccionado: `test_smoke_pipeline`, requiere `sb3_contrib` ausente localmente — no es regresión).
- Server multijugador FastAPI funcional: hotseat local + asientos remotos + bots de relleno (política GOAL).
- Tres frontends: `web/` (2D canvas playtest), `web/hali/` (isométrico 2.5D jugable), `godot_client/` (3D con Godot MCP Native).
- Material Print & Play fiel al código actual: `docs/releases/Carcosa_Reglas_PnP_v2026-08-02.pdf`.

### Deuda conocida (auditoría 2026-07-12, abierta)

- **Bots**: 2 políticas crashean al instante (`RandomPolicy`, `HabitanteDeCarcosa`); pathfinding no cruza pisos (suben por suerte); anti-stall muertos.
- **RL**: el agente elige solo tipo de acción (no destino); 59/60 episodios no llegan a `game_over` → señal terminal casi nula. BCNN/HYBRID dan `FileNotFoundError` (falta `models_bc/bc_mlp_all_best.pt`).
- **Sesiones**: `GameState.from_dict` pierde `role_id` / double-roll / monster stun al restaurar.

## Inicio rápido

### Server multijugador (recomendado para jugar)

```bash
cd ~/.hermes/workspace/ACTIVE/CARCOSA
pip install -e .            # entorno con FastAPI/uvicorn
CONDA_NO_PLUGINS=true uvicorn sim.game_server:app --host 0.0.0.0 --port 8765
```

Luego abre en el navegador:

- `http://localhost:8765/` → frontend 2D (playtest)
- `http://localhost:8765/hali` → frontend isométrico 2.5D

Contrato de API (única fuente que consumen los frontends):

- `POST /start` → `{game_id, state}` (configura asientos con `players_config`: `control` = `local` | `remote` | `bot`)
- `GET /state?game_id=...` → estado resumido
- `GET /legal?game_id=...&actor=...` → acciones legales (el frontend solo muestra lo que el server dice)
- `POST /act` → aplica acción y devuelve nuevo estado
- `POST /claim` → reclamar asiento humano (multijugador remoto)

### Simulación headless

```bash
python -m sim.runner --seed 1 --max-steps 400 --policy GOAL
# genera runs/<ts>_<policy>/seedN.jsonl + _summary.json (replay renderizable paso a paso)
```

### Tests

```bash
pytest -q                       # 439 pasan (excluye e2e_web / smoke_pipeline por defecto)
pytest -q -k "not e2e_web"      # suite completa sin el e2e de navegador
```

### Godot 3D client

```bash
cd godot_client
./launch_carcosa_mcp.sh         # levanta Godot 4.x + MCP server en puerto 9080
```

Requiere Godot 4.6+ y el addon `godot_client/addons/godot_mcp/`.

## Estructura

```text
engine/          Motor principal del juego (reglas, estado, transiciones, legalidad, RNG)
sim/             Runner headless, server multijugador, políticas de bots, métricas
train/           Entornos y pipelines BC / RL (torch + sb3_contrib)
web/              Frontend 2D canvas (playtest)
web/hali/        Frontend isométrico 2.5D jugable
godot_client/     Cliente 3D Godot + MCP Native
tests/           Suite de pruebas funcionales y canonicidad (439 tests)
tools/           Scripts de análisis y soporte (run_versioned, ai_ready_export, experiment)
docs/            Documentación técnica y canon (incl. releases/ con PnP)
documentos/      Reportes operativos y experimentales
```

## Documentación canónica

Para la fuente de verdad de las reglas del juego:

- [docs/releases/Carcosa_Reglas_PnP_v2026-08-02.pdf](docs/releases/Carcosa_Reglas_PnP_v2026-08-02.pdf) — reglas PnP fieles al código actual
- [docs/Carcosa_Canon_Actualizado_PnP_v0_4.pdf](docs/Carcosa_Canon_Actualizado_PnP_v0_4.pdf) — canon base de comparación
- [docs/AUDIT_SIM_BOTS_RL_2026-07-12.md](docs/AUDIT_SIM_BOTS_RL_2026-07-12.md) — auditoría funcional de sim/bots/RL

## Licencia

Este repositorio se publica bajo `CC BY-NC-SA 4.0`. Ver [LICENSE](LICENSE).

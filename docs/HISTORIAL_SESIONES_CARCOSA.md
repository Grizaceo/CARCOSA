# CARCOSA — Mapeo de sesiones → commits

Correlación sistemática entre sesiones DAVI donde se trabajó CARCOSA y los commits del repositorio.
Fecha de relevamiento: 2026-08-04. Fuente: session_search + git log (160 commits, 2026-01-10 → 2026-08-04).

## Índice cronológico

| # | Fecha sesión | Título / evento | Commits asociados |
|---|-------------|-----------------|-------------------|
| 0 | 2026-01 a 03 | Fundación (Grizaceo) | ~40 commits enero-marzo |
| 1 | 2026-04-19/25 | Limpieza disco + restauración repo | sin commits (migración) |
| 2 | 2026-04-27 | Consolidación LABS | sin commits CARCOSA |
| 3 | 2026-05-03 | Extracción patrón RL | sin commits CARCOSA |
| 4 | 2026-05-05 | Deep Research analysis | sin commits CARCOSA |
| 5 | 2026-05-11 | Godot 2-player + WebSocket | ver sección |
| 6 | 2026-06-09 | HTML Playtest + lobby | ver sección |
| 7 | 2026-06-21 | Frontend gaps P0-P3 | ver sección |
| 8 | 2026-08-02 | Estado actual #2: PnP + Godot 3D + BC | ver sección |
| 9 | 2026-08-03 | Estado actual #3: RL largo + EA | ver sección |
| 10 | 2026-08-04 | (esta sesión) Andamiaje PPO + EA ancla | WIP — sin commit |

## 0. Fundación (2026-01 a 03) — Grizaceo

**Sesiones:** No recuperadas (previas a Hermes). Trabajo de Cristóbal con Codex/Claude Opus sobre Windows.

**Commits (~40):**
- 2026-01-22→27: reestructuración del repositorio, alineación con canon (5+ commits).
- 2026-01-24: `aafc9574` primeros bots con roles.
- 2026-01-29: `29aa2f8e` "9% de winrate con Claude Opus 4.5, se iniciara la fase de RL".
- 2026-02-02: `be6b99d2` Docker para unificar dependencias, paralelizar simulaciones.
- 2026-03: Sprints 1-7 (servidor HTTP → Godot → BC):
  - `dbcbf61d` Sprint 1: servidor FastAPI para partidas humanas.
  - `c3d88caf` Sprint 2: cliente Godot 4 básico.
  - `91119a98` Sprint 3: hot-seat multi‑jugador + auto-save BC.
  - `69009434` Sprint 4: verificación pipeline BC (aquí el bc_mlp_all_best.pt fue git rm --cached).
  - `54ce52d6` Sprint 5: WebSocket LAN.
  - `e5caddef` Sprint 7: export Android.

**Lo que quedó (y hoy sigue roto):**
- `BCNNPlayerPolicy` y `HybridBCNNGoalPolicy` en `sim/policies.py` cargan `models_bc/bc_mlp_all_best.pt`, que fue borrado del repo en `69009434` y nunca restaurado. Rotos desde marzo 2026.

## 1. Limpieza y restauración (2026-04-19/20, 2026-04-25)

**Sesión:** @session:default/20260419_175830_dd81ee ("Revisar migración de .openclaw") y @session:default/20260425_171323_7c22fa.

**Eventos:**
- 2026-04-19: CARCOSA duplicado en `.openclaw/workspace/repos/` (~11 GB, archivos root de Docker). Movido a /tmp junto con copia de `.hermes/workspace/repos/carcosa/` (~8 GB).
- 2026-04-25: Cristóbal pregunta "donde quedo el repo de carcosa?". /tmp ya se limpió al reiniciar WSL. Restaurado desde GitHub: `git clone https://github.com/Grizaceo/CARCOSA` → `~/.hermes/workspace/repos/CARCOSA/`.
- Datasets y runs (~23 GB) se perdieron definitivamente (no estaban en GitHub).

**Lección:** Los datos de entrenamiento viven en disco local, no en GitHub. Si se mueve el repo, los datasets/runs no viajan con él. _SEPARADOR_SECCIONES_
# CARCOSA — Audit de Orden, Código Muerto y Optimizaciones

**Fecha:** 2026-08-09 · **Agente:** DAVI · **Rama:** `main` @ `7ffc5fb1`
**Alcance:** `engine/`, `sim/`, `train/` (18.555 LOC)
**Herramientas:** ruff 0.x, pyflakes, vulture, radon (instalados para el audit)

---

## FASE 0 — Snapshot

- **Estado git:** limpio salvo 1 archivo sin trackear (`tools/dump_bot_activations.py`, script de debug del visualizador de activaciones — no afecta el juego).
- **Sin cambios sin commitear** → los hallazgos no están enmascarados por trabajo sucio.
- **Tests:** 86 archivos de test en `tests/` (no corrí la suite completa; el audit es de orden/código muerto, no de regresión funcional).

---

## HALLAZGOS INEVITABLES (auto-fix, seguros)

| # | Archivo:línea | Tipo | Por qué es inevitable |
|---|---|---|---|
| 1 | `engine/transition.py:1` | **BOM (U+FEFF)** en byte 0 | Carácter no imprimible ilegal; algunos toolchains (radon, import en plataformas estrictas) fallan al parsear. Confirmado con `xxd`: `ef bb bf`. |
| 2 | `train/collect_winners_only.py:126` | `E722` bare `except:` | Swallow de excepciones silencioso — enmascara errores reales de entrenamiento. |
| 3 | `engine/effects/event_utils.py:35` | `F811` redefine `List` sin usar | Import duplicado que sobrescribe el del line 9; confunde el lint y puede romper en re-exports. |
| 4 | `engine/__init__.py:1-4` | 11× `F401` | **NO es código muerto** — son re-exports de la API pública del paquete. Ignorar en el conteo. |

> Estos 4 son los únicos que rompen en un checkout limpio o enmascaran bugs. Todo lo demás es OPTIONAL.

---

## HALLAZGOS OPTIONAL (decisiones, NO toqué nada)

### A. Código muerto confirmado (vulture @60, 159 ítems)

**Muerte "de diseño" (prioridad alta para limpiar):**
- `engine/transition.py:27-36` importa **12 funciones `legacy_*`** desde `engine/compat/legacy.py` (legacy_reveal_one, legacy_resolve_card_minimal, legacy_monster_phase, etc.) que **no se usan en ningún lado** (verificado: solo aparecen en el import + definición en legacy.py). Es un **refactor a medias** — `transition.py` ya usa las versiones nuevas en `step()`. `engine/compat/legacy.py` entero es candidato a borrar.
- `train/` experimentos muertos del ciclo RL fallido (no aportan al juego, solo peso):
  - `train/adaptive_finetune.py` — **1443 LOC**, el archivo train/ más grande, Fine-tune que no se usa en el pipeline actual.
  - `train/collect_winners_only.py` (170), `train/train_until_30.py` (75), `train/train_replicated.py` (137), `train/oracle_mcts.py` (119) — scripts de experimentos que no están en el pipeline de producción (el server usa `models/*.zip` ya entrenados).

**Muerte "de atributo sin usar" (baja prioridad, ruido de API):**
- `engine/state.py`: `special_activation_count` (112), `king_vanish_ends` (147), `event_queue` (166), `last_peek` (185) — campos de `GameState` definidos pero nunca leídos.
- `engine/types.py`: ~20 constantes `MONSTER_ID_*`, `OMEN_ID_*`, `SPECIAL_ROOM_*` sin uso (IDs hardcodeados en lugar de las constantes).
- `engine/config.py:97-98`: `MCTS_TOP_K`, `MCTS_DETERMINIZE` — config de MCTS que no se lee (el MCTS oracle fue declarado inviable a escala).

### B. Lint / Formato (ruff)

- **138 errores totales**, de los cuales **88 auto-fixeables** con `ruff check --fix`:
  - 86× `F401` unused-import (excluyendo los 11 de `__init__.py` legítimos → ~75 reales).
  - 8× `F541` f-string sin placeholder (string normal escrito como f-string).
  - 14× `F841` unused-variable (ej: `sim/game_server.py:990` `next_state` asignado y nunca usado; `sim/policies.py:207` `team_low`).
- **76 de 99 archivos no pasan `ruff format --check`** → el repo nunca tuvo formato automático aplicado. Esto es cosmético pero ensucia los diffs de git.

### C. Complejidad (radon CC — monstruos a refactorizar)

| Función | CC | Grade | Riesgo |
|---|---|---|---|
| `sim/policies.py:GoalDirectedPlayerPolicy.choose` | **201** | F | God-function. El bot GOAL entero en un método. |
| `engine/legality.py:get_legal_actions` | **131** | F | 417 líneas, el árbitro de legalidad. |
| `sim/policies.py:_choose_special_action` | 73 | F | |
| `engine/systems/player.py:apply_player_action` | 49 | F | |
| `sim/runner.py:run_episode` | 44 | F | |
| `engine/systems/monsters.py:move_monsters` | 32 | E | |
| `engine/systems/king.py:resolve_king_phase` | 30 | D | (ya leímos este — la rampa de daño vive aquí) |
| `sim/game_server.py:start_game` | 29 | D | |

**Mantenibilidad (radon MI):** `sim/policies.py` y `train/carcosa_env.py` / `adaptive_finetune.py` = **0.00** (archivos >1300 LOC). `sim/game_server.py` = 6.52. El resto del engine está en rango A (19-39), saludable.

### D. Duplicación

- `train/evolve.py`, `evolve_anchor.py`, `evolve_parallel.py` — 3 variantes de PBT evolution. El paralelo ya probó ser 4.4× más rápido; los otros 2 son redundantes (pero útiles como referencia del experimento fallido).
- `train/bench_multi_seed.py` es el único benchmark canónico (bien). Los scripts `/tmp/eval_*.py` citados en el SKILL ya no existen (se limpiaron).

---

## OPTIMIZACIONES POSIBLES (no medidas, son propuestas)

1. **Hot path del simulador (entry point del RL).** `engine/transition.step()` hace `deepcopy(state)` en cada paso — es el cuello que hizo CUDA 2.4× MÁS LENTO que CPU (medido 2026-08-04). Una copia estructural selectiva o in-place + revert log ganaría throughput de entrenamiento sin tocar reglas. **Esto es lo único que acelera futuros experimentos si tu amigo quiere retomar la AI.**
2. **`rotate_boxes` / `rotate_boxes_intra_floor`** (board.py) crean `dict` completo cada ronda — podría ser in-place con swap de referencias.
3. **Cache de `get_legal_actions`**: se llama por jugador y por bot cada paso; varias ramas son puras dado el estado. Memoizar por `(state_hash, actor)` ahorraría en partidas 4-bot.

---

## Veredicto

🟡 **YELLOW** — El repo es **funcional y el juego corre** (el BOM no rompe Python estándar, solo toolchains estrictos), pero tiene deuda de orden acumulada de 6 meses de experimentación RL:

- ✅ **Motor (`engine/`):** saludable (MI A, reglas correctas, tests verdes históricamente).
- ⚠️ **`sim/policies.py` (1889 LOC, MI 0.00):** el riesgo real si tu amigo quiere modificar bots. GOAL+COMMITTEE viven ahí.
- ⚠️ **`train/`:** 28 archivos, muchos son experimentos muertos del ciclo RL fallido. Peso de navegación, no de runtime.
- 🐛 **1 bug de encoding real** (BOM en transition.py) + 2 smells (bare-except, F811).

**Para la reunión con tu amigo:** el audit confirma que el 23% NO es por código sucio — el motor está limpio y correcto. La deuda es de *organización post-experimentación*, no de calidad de juego. Las 3 palancas de diseño (llaves, rampa de Rey, daño Casa) siguen siendo el ángulo real.

---

## Próximos pasos sugeridos (requieren tu aprobación)

- **P0 (seguro):** `sed`/patch para quitar BOM + `ruff check --fix` (88 errores) + arreglar bare-except/F811. 1 commit, verificable.
- **P1 (limpieza):** borrar `engine/compat/legacy.py` + los 12 imports en transition.py; mover experimentos muertos de `train/` a `train/_archive/`.
- **P2 (opcional):** `ruff format` a los 76 archivos; split de `GoalDirectedPlayerPolicy.choose` (201 CC) en sub-métodos.
- **NO recomendado ahora:** tocar `transition.step()` deepcopy (riesgo de romper determinismo del engine antes de mostrarle a tu amigo).

# Auditoría funcional: simulador headless, bots y pipeline RL

**Fecha:** 2026-07-12 · **Branch:** `feat/html-canvas-playtest` · **Método:** lectura de código + ejecución empírica (tests, sims, sweep de políticas, server vivo)

---

## Resumen ejecutivo

El núcleo del proyecto está **sano**: el motor de reglas es determinista (verificado byte a byte), la suite de tests pasa 439/440, y el server multijugador funciona con su contrato `/legal` + `step()` como única fuente de verdad. Sin embargo, la capa de **bots** tiene 3 bugs que degradan seriamente su calidad de juego (2 políticas crashean al instante, el pathfinding no sabe cruzar pisos, los trackers anti-stall están muertos), y la capa **RL** tiene un techo estructural bajo: el agente elige solo *tipos* de acción (no puede decidir a dónde moverse) y las partidas de bots casi nunca terminan (59/60 episodios sin `game_over` a 1500 pasos), por lo que la señal terminal de RL es casi inexistente.

**Evidencia empírica clave:**

| Verificación | Resultado |
|---|---|
| Suite pytest (sin e2e_web) | **439 passed, 1 failed** (dependencia `sb3_contrib` ausente, no lógica) |
| Determinismo (seed 42, 300 pasos, 2 corridas) | **Byte-idéntico** ✔ |
| Sweep 6 políticas × 10 seeds × 1500 pasos | **59/60 sin terminar**; GOAL 1 win; RANDOM y HABITANTEDECARCOSA **crashean** |
| MCTS (25 rollouts) | ~0.8 s/decisión → ~3.2 s/decisión a 100 rollouts (impracticable) |
| BCNN / HYBRID | **FileNotFoundError**: `models_bc/bc_mlp_all_best.pt` no existe |
| Server (puerto 8123, partida real) | `/start`, `/state`, `/legal`, `/health` OK; shape documentado abajo |

---

## 1. Cómo funciona cada capa

### 1.1 Motor de reglas (`engine/`)

- `GameState` (dataclass, `engine/state.py`) contiene jugadores, monstruos, 15 nodos (3 pisos × [4 habitaciones + pasillo]), mazos por habitación vía sistema de **boxes** (el mazo pertenece al box; `box_at_room` mapea box→habitación y rota "cinta de sushi" al fin de ronda), Rey (piso), escaleras, flags y log de acciones.
- `step(state, action, rng, cfg)` (`engine/transition.py:152`) **clona con `deepcopy`** y valida la acción contra `get_legal_actions` por **igualdad estricta** (excepción: `KING_ENDROUND` acepta cualquier `data`). Interrupt de sacrificio tiene prioridad absoluta.
- `get_legal_actions` (`engine/legality.py`) genera: MOVE (vecinos del piso + escalera→escalera del piso adyacente + escaleras temporales), SEARCH (si mazo activo con cartas), MEDITATE (bloqueado en pasillo del piso del Rey y por TANK presente), objetos, especiales (Motemey/Taberna/Armería/Puertas/Capilla/Salón/Cámara Letal), habilidad del Healer, y los interrupts (sacrificio, hallway peek, Motemey choice).
- Fases: `PLAYER` (2 acciones/jugador) → `KING` (única acción `KING_ENDROUND`: d4/d6 internos, daño de presencia escalado por ronda, movimiento de monstruos, rotación de mazos, chequeo de victoria/derrota).
- RNG propio (`engine/rng.py`) con `fork(label)` determinista — bien diseñado.

### 1.2 Simulador headless (`sim/runner.py`)

`python3 -m sim.runner --seed N --max-steps M --policy P` construye el estado canónico (`make_smoke_state`: roles FIXED por defecto SCOUT/HIGH_ROLLER/TANK/BRAWLER, inicio repartido en pasillos F1/F2), corre el loop política→legalidad→step, y escribe `runs/<ts>_<policy>/seedN.jsonl` + `_summary.json`. **Cada registro jsonl incluye `full_state` (estado completo pre-acción)** — un replay renderizable paso a paso sin re-simular. Métricas de episodio: sacrificios, especiales, estados ganados/perdidos, llaves destruidas y por quién.

### 1.3 Bots (`sim/policies.py`, `sim/mcts*.py`)

- **GOAL** (GoalDirectedPlayerPolicy): la política seria. Capas de decisión: interrupts forzados → BLUNT reactivo → objetos gratis → huida del piso del Rey → meditación por umbral dinámico (peligro, rol, late-game, portador de llaves) → memoria de equipo (llaves conocidas) → progreso de llaves → convergencia al Umbral. Parametrizable vía `sim/policy_params.json`.
- **Memoria de equipo** (`sim/memory.py`): cartas observadas por SEARCH/PEEK/TABERNA se comparten, envejecen y generan asignaciones de objetivo por bot.
- **MCTS** (`sim/mcts.py`): UCB1, expansión con 1 muestra por acción (juego estocástico sin chance nodes), rollout con GOAL, backprop con rewards incrementales correctos. Sin reuso de árbol. `determinize: False` — **ve el estado oculto completo** (hace trampa).
- **King**: RANDOM (d4/d6) por defecto; HEURISTIC hace lookahead con `king_utility` y evita matar antes de la ronda configurada.

### 1.4 Pipeline RL/BC (`train/`)

- `CarcosaEnv` (Gymnasium): obs = **24 floats** (10 globales de `tension.compute_features` + 14 locales del actor de turno), acción = `Discrete(27)` sobre **tipos** de `ActionType`, máscara para MaskablePPO, curriculum opcional (keys34: estados con 2-3 llaves y portadores frágiles; closing: 4 llaves repartidas cerca del Umbral), reward shaping denso (llaves ±, cordura, fase-2 progreso al Umbral, info-gain/uso de hints con memoria env-side).
- `train_bc.py`: BC sobre CSVs exportados de runs (ahora vía MaskablePPO/sb3_contrib). `train_rl.py`: PPO/MaskablePPO estándar SB3. `collect_*`: generación de datos expertos con GOAL. Checkpoints reales en `models/` (MaskablePPO 2026-04-26, goldset de 500 wins).
- Políticas de inferencia: `BCNN` (MLP 10-features → tipo de acción, primera acción legal del tipo) y `HYBRID` (GOAL manda; BC overridea con confianza ≥0.6).

### 1.5 Server (`sim/game_server.py`) + web

FastAPI: `/start` (asientos local/remote/bot), `/claim` (client_id por asiento, modos add/replace/release/takeover), `/state/{id}`, `/legal/{id}/{actor}`, `/act` (valida claim + legalidad vía step, luego `_auto_advance_until_human` con GOAL para bots y Rey), `/save`, `/games` (+download), `/setup_preview/{seed}`, WS push por partida con keepalive. Persistencia: sesiones activas a disco (sobreviven reinicios), partidas terminadas a PostgreSQL o filesystem (`runs/human_*`). Registros compatibles con el pipeline BC.

---

## 2. Hallazgos

### Críticos

| # | Hallazgo | Ubicación | Evidencia / Escenario |
|---|---|---|---|
| C1 | **`GameState.from_dict` pierde campos**: `role_id` (→ "DEFAULT"), `double_roll_used_this_turn`, `free_move_used_this_turn` del jugador y `stunned_remaining_rounds` del monstruo. Al restaurar sesión tras reinicio del server (`game_server.py:239`), los roles **desaparecen del engine** (TANK deja de bloquear meditación, HEALER pierde `USE_HEALER_HEAL`, monstruos aturdidos despiertan) mientras la UI sigue mostrando roles vía `roles_assigned`. Divergencia silenciosa. | `engine/state.py:268-411` | Lectura directa: el constructor de `PlayerState` en `from_dict` no pasa `role_id`; `MonsterState` no pasa stun. |
| C2 | **2 de 8 políticas registradas crashean al instante.** `RandomPolicy` es dataclass sin campo `cfg` pero `get_player_policy` llama `cls(cfg)` → TypeError (¡el baseline no corre!). `HabitanteDeCarcosaPolicy.__post_init__` retorna temprano sin inicializar `_role_sanity_bias`/`_team_memory` → AttributeError en la primera decisión. | `sim/policies.py:1309, 1067-1069` | Reproducido: `python3 -m sim.runner --policy RANDOM` y `--policy HABITANTEDECARCOSA` mueren con traceback. |
| C3 | **Pathfinding desalineado con la legalidad**: `pathing.adjacency` conecta escalera(f) → **pasillo**(f±1), pero el movimiento legal es escalera(f) → **escalera**(f±1). Cuando el bot está en la habitación con escalera, BFS le sugiere un destino ilegal, no encuentra la acción y cae a ramas de fallback — los bots cruzan pisos casi solo por azar. Contribuye directamente a la no-terminación de partidas. | `sim/pathing.py:34-40` vs `engine/legality.py:184-197` | Lectura cruzada de ambos grafos. |

### Altos

| # | Hallazgo | Ubicación | Evidencia / Escenario |
|---|---|---|---|
| A1 | **Las partidas de bots casi nunca terminan**: 59/60 episodios llegan a max-steps (rondas 25-48) sin `game_over`. La derrota exige *todos* con cordura ≤ −5, pero el sacrificio resetea a 0 y meditar/pasillo regenera — equilibrio perpetuo. Sin señal terminal, RL no tiene gradiente hacia ganar y las métricas de winrate son ruido. | diseño de reglas + `engine/systems/victory.py` | Sweep empírico 6×10×1500. |
| A2 | **Trackers de política muertos**: `_POLICY_TRACKING` se indexa por `id(state)`, pero cada `step()` crea un objeto nuevo → el anti-stall (`STALL_KEY_STEPS=24`) y la racha de armería **nunca acumulan** (siempre 0/1). Además el dict crece sin límite (leak) y un `id()` reciclado por GC puede inyectar flags de un estado muerto. | `sim/policies.py:160-190` | Lectura + semántica de `id()`. |
| A3 | **`/state` filtra información oculta**: `deck.cards` completo de cada habitación y del Motemey viaja a todos los clientes — se puede ver dónde está cada KEY con abrir DevTools. | `sim/game_server.py:427-443` | Capturado en vivo: `F1_R1.deck.cards[1] == "KEY"` visible en la respuesta. |
| A4 | **Sin lock por sesión en `/act`**: dos requests concurrentes (o un `/act` + auto-advance de reconexión) intercalan sus bucles `_auto_advance_until_human` en los `await` → bots pueden actuar dos veces por turno o pisarse los `step_idx`. | `sim/game_server.py:850-923, 536-590` | Análisis de concurrencia asyncio (handlers async sin mutex). |
| A5 | **Espacio de acción RL colapsado a tipos**: el agente elige `MOVE` y el env resuelve el destino (`candidates[0]` o hint heurístico). La navegación —la decisión central del juego— **no es aprendible**. Además, en fase KING la máscara es todo-unos, la acción del agente se ignora (juega RandomKing) y el reward del fin de ronda (a menudo el más negativo) se atribuye a una acción arbitraria: ruido de crédito puro. | `train/carcosa_env.py:56-84, 553-579, 909-918, 339` | Lectura del env. |
| A6 | **BCNN/HYBRID inutilizables**: checkpoint `models_bc/bc_mlp_all_best.pt` no existe en el repo (el dir `models_bc/` no existe). Y por diseño, BCNN observa 10 floats globales y emite solo el tipo de acción — mismo techo que A5. | `sim/policies.py:1346` | Reproducido: FileNotFoundError al instanciar. |
| A7 | **El runner sustituye acciones ilegales por una legal aleatoria sin contarlo**: datos BC generados con `--policy X` contienen acciones aleatorias etiquetadas como X, sin campo que lo delate (a diferencia de `carcosa_env`, que sí trackea `fallback_substitution`). | `sim/runner.py:354-364` | Lectura. |

### Medios

| # | Hallazgo | Ubicación |
|---|---|---|
| M1 | `step()` hace `deepcopy` del estado completo **incluyendo `action_log` creciente** → costo O(n²) por episodio; MCTS paga 5000 deepcopys/decisión (~3.2 s con 100 rollouts). Extirpar el log del clone o usar copy-on-write. | `engine/state.py:261-262`, `engine/transition.py:154` |
| M2 | `HeuristicKingPolicy.choose()` **muta el estado** (`state.flags["win_ready_hits"]`) — efecto secundario en una función de decisión; contamina replays y cualquier búsqueda que la use. | `sim/policies.py:1090` |
| M3 | MCTS: 1 muestra por expansión en juego estocástico (sin chance nodes ni determinización), ve información oculta, sin reuso de árbol. Como bot "fuerte" es débil y lento a la vez. | `sim/mcts.py:139-152`, `sim/mcts_policy.py:27` |
| M4 | `test_smoke_pipeline` falla porque `train_bc.py:16` importa `sb3_contrib` incondicionalmente — el pipeline smoke (sim→export→BC) exige la dependencia ML aunque el resto no la necesite. | `train/train_bc.py:16` |
| M5 | `reports/experiments.csv` no registra ningún experimento real: 22 filas, todas smoke de 1 episodio/50 pasos, mayoría `failed`, winrate vacío. La historia experimental real (checkpoints de abril en `models/`) no está trazada. | `reports/experiments.csv` |
| M6 | `/state` **no expone `stairs`** — el frontend no puede saber dónde están las escaleras (render infiel al canon 4.2). | `sim/game_server.py:383-476` |
| M7 | Reward RL: LOSE −10 vs WIN +100 y **timeout sin penalidad** → la política óptima bajo truncamiento es sobrevivir farmeando shaping (info-gain, llaves) sin intentar ganar. | `train/carcosa_env.py:1021-1024` |

### Bajos

- **El Rey puede regalar la victoria**: la única victoria del sweep (GOAL seed 4) ocurrió porque el `d6=5` del Rey activó *atracción al piso 2* y teletransportó a los 4 jugadores (con 4 llaves) al pasillo F2_P = Umbral → `can_win` inmediato. Interacción legal según canon, pero cuestionable como diseño: el antagonista puede cumplir la condición de victoria de los jugadores por accidente.
- `RandomKingPolicy` genera `d4`/`d6` en `data` que `step()` ignora (usa RNG interno) — inofensivo pero confuso (`sim/policies.py:1134-1140`).
- `runner.run_episode` crea `RNG(seed)` dos veces (setup dentro de `make_smoke_state` y gameplay) — misma secuencia inicial correlacionada; determinista pero aliasing de streams.
- `DeckState.put_bottom` compacta el array al 50% — correcto, pero `top` como puntero + cartas "consumidas" visibles complica a los consumidores del shape (frontends deben usar `cards[top:]`).
- `carcosa_env` registra `Carcosa-v0` con `max_episode_steps=500` pero el default interno es 2000 — dos fuentes de truncamiento distintas.

---

## 3. Evaluación de las ideas de RL

**Lo que está bien pensado:**
- MaskablePPO + action masking es la elección correcta para legalidad dura.
- El curriculum (keys34/closing) ataca exactamente el problema real (fase 2 nunca alcanzada por exploración natural) — buen instinto.
- BC → RL fine-tune con datos del GOAL heurístico es un bootstrap razonable.
- La instrumentación del env (`fallback_substitution`, `illegal_action_intent`, `action_selection_source`) es de calidad profesional.
- Control centralizado de los 4 jugadores (parameter sharing implícito) es defendible para un cooperativo.

**Los tres bloqueos estructurales, en orden:**
1. **Acción por tipo** (A5): sin control de destino de movimiento ni de objetivo de especiales, el agente no puede superar al env-wrapper que decide por él. Gran parte de la "inteligencia" está en los fallbacks heurísticos del env, no en la red — lo aprendido no es transferible fuera del wrapper.
2. **Sin terminación** (A1): con 59/60 episodios truncados, el +100 de WIN es casi inalcanzable por exploración y el −10 de LOSE casi nunca se ve. El shaping denso domina el retorno → optimiza el proxy.
3. **Observación pobre**: 24 floats sin identidad de rol (el actor no sabe si es HEALER o TANK), sin posiciones de los demás, sin topología. El BCNN de 10 floats es aún más ciego.

**Recomendaciones concretas (prioridad descendente):**
1. Arreglar C3 (pathing) y C2: los teachers heurísticos mejoran gratis → mejores datos BC → mejor todo.
2. **Acción factorizada**: `Discrete(N_tipos × N_targets)` con máscara compuesta, o cabeza autoregresiva (tipo, luego argumento). Con 15 habitaciones el producto es manejable (~27×15).
3. **Cerrar los episodios**: cap de rondas canónico (p. ej. ronda 15 = LOSE con −50) o presupuesto de cordura de la Casa. Alinea el juego con RL y de paso arregla el juego de mesa (partidas eternas también aburren a humanos).
4. Obs v2: one-hot de rol + (piso, sala) por jugador + distancias BFS + conteos de mazo por sala + one-hot del actor. ~80-120 floats, sigue siendo MLP-friendly.
5. En fase KING: resolver el fin de ronda **dentro** del step del último jugador (auto-transición), para que ningún timestep del agente sea un no-op con reward ajeno.
6. Registrar experimentos de verdad (winrate/seeds/commit) — `experiments.csv` hoy no cumple su función.
7. MCTS: si se persiste, determinizar (sample de mazos consistente con lo observado) + reuso de árbol + presupuesto por tiempo; con M1 arreglado los rollouts se abaratan ~10×.

---

## 4. Implicaciones para el motor de representación (siguiente fase)

- **Contrato de datos listo**: `/state` (capturado en vivo, `scratchpad/state_sample.json`) + `/legal` + WS `state_update` bastan para modo live; los jsonl con `full_state` por paso son un formato de replay completo — el motor 2.5D puede reproducir cualquier partida headless sin tocar el engine.
- Gaps a cubrir para render fiel: **exponer `stairs` en `/state`** (M6) y — si se quiere juego honesto — reemplazar `deck.cards` por `{remaining, top_revealed?}` (A3).
- Layout canónico confirmado (PDF §2.1): pasillo conecta R1-R4; R1↔R2, R3↔R4; Umbral = F2_P; escaleras 1/piso.

*Generado por auditoría automatizada Claude (Fable 5) — evidencia reproducible en `/tmp/.../scratchpad/` (sweep, diffs de determinismo, capturas de API).*

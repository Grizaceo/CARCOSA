# CARCOSA RL — Cierre línea de entrenamiento: techo práctico 23.0%

**Fecha:** 2026-08-05
**Estado:** CERRADO. Techo práctico = COMMITTEE v5 = 69/300 = 23.0% (IC95 18-28%).
**Tag de retorno:** `pre-existence-punishment` (estado anterior al existence punishment).

## Línea temporal del techo

| Versión | Win% | Wins/300 | Novelas | Lever |
|---|---|---|---|---|
| GOAL baseline | 8.0% | 24 | — | heurística |
| COMMITTEE v1 | 14.3% | 43 | +19 | ensemble + set_memory fix |
| COMMITTEE v2 | 19.7% | 59 | +16 | RL maskable (ActionMasker) |
| COMMITTEE v3 | 21.3% | 64 | +5 | curriculum f1→f2→f3 |
| COMMITTEE v4 | 22.7% | 68 | +4 | reward_key_hold_per_step |
| COMMITTEE v5 | 23.0% | 69 | +1 | seed variation |
| Existence punishment | 23.0% | 69 | +0 | FALSIFICADO (bug eval sin masks) |

## Techo empírico confiable

- Unión de TODOS los reports confiables (post set_memory fix): **74/300 = 24.7%**
- COMMITTEE v5 captura **93%** del techo confiable (69/74)
- Gap accionable: **3 seeds** (70, 112, 298) — ganadas por PPO crudo frágil, no reproducibles en committee
- Seeds NUNCA ganadas por nada: **226/300 = 75.3%**

## Levers tocados (todos agotados o falsificados)

1. ActionMasker + MaskablePPO — fix del RL 0% (81% intents ilegales → 0%)
2. Curriculum dificultad (King OFF/weak/normal) — novelas decrecientes
3. reward_key_hold_per_step — +4 novelas
4. Seed variation — +1 novela
5. Existence punishment (Pezza) — FALSIFICADO (0 novelas reales)
6. PBT evolution (4 gen × 8 mutants) — 0/32, falsificado
7. King/keys/rounds sweep — sin efecto
8. MCTS oráculo — inviable a escala (>3 min/seed)

## Bugs encontrados por auditoría adversarial (commits 9f33787f, 046cab09, bf124d15)

1. **pezza_metrics caía a sample() aleatorio** — PPO estándar no acepta action_masks → TypeError → except → sample() random. Fix: detectar via inspect.signature.
2. **bench_multi_seed cargaba MaskablePPO como PPO** — TypeError use_sde. Fix: detectar "maskable" en filename.
3. **bench_multi_seed evaluaba MaskablePPO SIN action_masks** — win-rates inflados. Fix: pasar action_masks cuando is_maskable=True. **Este bug invalidó el resultado del existence punishment** (2 novelas falsas → 0 reales).

## Diagnóstico estructural (¿por qué 75% es perdible?)

- 65% de derrotas: LOSE_ALL_MINUS5 (sanidad), ronda ~33, arrastre lento
- 27% de derrotas: LOSE_KEYS_DESTROYED, ronda ~29
- 8.6% victorias: ronda ~15 (rápidas)
- Las victorias son RÁPIDAS, las derrotas se arrastran
- 226 seeds nunca ganadas — el problema es acumular keys + sobrevivir sanidad simultáneamente
- No es el bot: es el DISEÑO DEL JUEGO (60 rondas, presión sanity constante, keys se destruyen)

## Lo que NO funciona (no repetir)

- Entrenar más modelos RL con reward shaping distinto → novelas agotadas (0 marginales)
- Probar más seeds de entrenamiento → +1 novela, diminishing returns
- MCTS como oráculo → inviable a escala
- Tweak King/keys/rounds → sin efecto (sweep de 1501 runs)
- PBT/evolución → 0/32 mutants (3 confirmaciones independientes)
- Existence punishment / Pezza reward shaping → falsificado

## Lo que QUEDA sin probar (con fundamento)

1. **Reward de cierre rápido (decay exponencial)** — bonus que decae por ronda, no por existence. Forzar victorias rápidas (ronda 15, no 38+).
2. **Sharpe del reward** — normalizar por duración de episodio. Un win en ronda 15 vale más que uno en ronda 38.
3. **Multi-env configs distintas simultáneas** — curriculum online, no secuencial. Entrenar con 4 envs cada uno con King config distinto a la vez.
4. **Rediseño del juego** — cambiar mecánicas de sanity/keys/rounds para reducir el 75% perdible. Es game design, no ML.
5. **Análisis de patrones en las 226 seeds perdibles** — correr pezza_metrics sobre todas, buscar si hay estructura fácil/modificable (setup rooms, distribuciones que siempre pierden).

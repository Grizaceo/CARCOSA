# CARCOSA — Plantilla de delegación Nemotron + 4060

Usar esta plantilla cuando Cristóbal pida lanzar un ciclo autónomo de ML para CARCOSA con mínima intervención de DAVI.

## Rol de cada agente

- **Nemotron / OpenShell**: director de experimento, análisis, priorización e iteración.
- **4060 local**: ejecución de tests, entrenamiento, evaluación y generación de artefactos.
- **DAVI**: coordinación liviana al inicio y revisión al cierre.

## Objetivo por defecto

Mejorar la **conversión de 3 → 4 llaves** sin abrir demasiado el scope.

## Restricciones por defecto

- No tocar `runs/` históricos salvo necesidad experimental concreta.
- No reestructurar el repo completo.
- No cambiar el canon del juego.
- Priorizar cambios pequeños, medibles y atribuibles.

## Presupuesto por defecto

- Hasta las **17:00** hora local si se está trabajando en una ventana diaria acotada.
- Si no aplica una hora de cierre explícita: **20.000 timesteps totales**.
- Máximo **3 iteraciones**.
- Máximo **2 cambios de código sustantivos**.

## Hipótesis prioritarias sugeridas

1. Shaping específico del tramo **3→4 llaves**.
2. Selector/funnel orientado a `rate_reached_4_keys`.
3. Curriculum de estados cercanos a 3 llaves.
4. Reducción de desalineación entre acción deseada y ejecutada si afecta el embudo de llaves.

## Modo de trabajo

Nemotron debe:
1. revisar el estado actual del pipeline relevante (`train/adaptive_finetune.py`, `train/carcosa_env.py`, tests y docs recientes)
2. elegir **una hipótesis principal**
3. aplicar cambios acotados
4. pedir a la 4060 la ejecución necesaria
5. evaluar los resultados
6. iterar solo si sigue dentro del presupuesto y hay señal útil

## Regla de comunicación

Durante el ciclo, minimizar la intervención de DAVI. El loop ideal es:

**Nemotron ↔ 4060**

DAVI entra solo:
- al inicio, para lanzar o dejar el contrato claro
- al final, para revisar el resumen y decidir con Cristóbal

## Entregable final obligatorio

Nemotron debe dejar un cierre compacto con:
1. hipótesis elegida
2. cambios hechos
3. experimentos corridos
4. métricas/resultados
5. recomendación final

## Prompt base sugerido

```text
Revisa el pipeline actual de entrenamiento de bots en CARCOSA, con foco exclusivo en mejorar la conversión de 3 → 4 llaves.

Archivos prioritarios:
- train/adaptive_finetune.py
- train/carcosa_env.py
- tests/test_adaptive_selector_lexicographic.py
- tests/test_carcosa_env_curriculum.py
- tests/test_carcosa_env_phase_shaping.py
- documentos/estado_bots_rewards_2026-03-06.md

Tu rol es director de experimento. La 4060 local ejecutará lo pesado; tú debes priorizar, decidir y analizar.

Restricciones:
- no tocar runs históricos salvo necesidad concreta
- no reestructurar el repo completo
- no cambiar el canon del juego
- prioriza cambios pequeños y medibles

Presupuesto:
- hasta las 17:00 hora local o, si no aplica, 20.000 timesteps totales
- máximo 3 iteraciones
- máximo 2 cambios de código sustantivos

Objetivo:
mejorar la conversión de 3 → 4 llaves, no optimizar todavía el win-rate global si eso abre demasiado el scope.

Entrega final obligatoria:
1. hipótesis elegida
2. cambios hechos
3. experimentos corridos
4. métricas/resultados
5. recomendación final
```

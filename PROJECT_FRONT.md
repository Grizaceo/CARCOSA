---
project: CARCOSA
status: active-and-delegable
reviewed_at: 2026-03-19
reviewer: DAVI
priority: high
repo_path: /home/gris/.openclaw/workspace/repos/CARCOSA
vault_note: /mnt/c/Users/usuario/.openclaw/workspace/Vault/Proyectos/Carcosa.md
---

# Ficha de proyecto

## Qué es
Proyecto principal de juego + motor de simulación + entorno de entrenamiento para CARCOSA.

## Juicio rápido
No es un repo para “auditar desde cero”, sino un frente activo y ya bastante conocido.

Tiene:
- motor canónico del juego
- simulación
- behavioral cloning / RL
- tests
- documentación técnica
- canon operativo

## Lectura DAVI
Es un proyecto vivo, con valor alto y continuidad temática clara.
La revisión actual no necesita redescubrir el repo, sino dejar punto de reentrada limpio.

## Estado útil para trabajo futuro
- repo importante / prioritario
- evitar gastar contexto revisando `Runs/` a fondo salvo necesidad explícita
- arquitectura preferida para iteración ML ya definida: **4060/local ejecuta, Nemotron/OpenShell analiza, DAVI coordina solo al inicio/cierre**
- objetivo por defecto de delegación actual: **mejorar conversión de 3 → 4 llaves**

## Qué rescatar / mantener presente
- `docs/Carcosa_Libro_Tecnico_CANON.md`
- `docs/AI_DATA_GUIDE.md`
- `configs/experiment.default.yaml`
- `train/adaptive_finetune.py`
- `train/carcosa_env.py`
- tests de selector/curriculum/phase shaping
- `docs/NEMOTRON_DELEGATION_TEMPLATE.md`

## Próximo punto de reentrada
Si se retoma sin nueva instrucción, empezar por:
1. objetivo experimental vigente
2. plantilla de delegación a Nemotron
3. revisar solo los módulos necesarios para 3→4 llaves
4. evitar exploración amplia de runs históricos

## Veredicto actual
**active-and-delegable**

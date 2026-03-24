# CARCOSA Autopilot ML — Plan de Implementación

**Objetivo**: Ciclo autónomo de mejora de bots usando Copilot Agents, sin intervención manual entre iteraciones.

---

## Estado Actual (punto de partida)

| Componente | Estado | Notas |
|---|---|---|
| `sim/policies.py` | ✅ GoalDirectedPlayerPolicy funcional | ~7.5% winrate |
| `tools/generate_dataset.py` | ✅ Listo, paralelo | 1.2s/episodio, ~500 eps en 3min con 4 workers |
| `tools/ai_ready_export.py` | ✅ Listo | Convierte JSONL → CSV/Parquet para BC/RL |
| `train/train_bc.py` | ✅ Listo | Behavioral Cloning MLP/Transformer |
| `train/train_rl.py` | ✅ Listo | PPO/A2C con StableBaselines3 |
| `train/carcosa_env.py` | ✅ Listo | Gym env con action masking |
| `models_bc/bc_mlp_all_best.pt` | ✅ Modelo previo | Baseline de entrenamiento anterior |
| `reports/experiments.csv` | ✅ Tracking histórico | Registra todos los experimentos |

### Causa Raíz de 7.5% (para que el agente entienda)
- `apply_minus5_consequences()` destruye TODAS las llaves del jugador cuando llega a -5
- Partidas duran 25-47 rondas (deberían terminar en 8-16 rondas para ganar)
- King inflige 4 dmg/ronda desde ronda 10+, con HOUSE_LOSS 1/ronda adicional
- Ganar requiere: 4 llaves encontradas + todos en F2_P antes de que expire sanity

---

## Arquitectura del Autopilot

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AUTOPILOT LOOP (N iteraciones)                    │
│                                                                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │  AGENT 1    │    │  AGENT 2    │    │  AGENT 3    │              │
│  │  Dataset    │    │  Training   │    │  Eval +     │              │
│  │  Generator  │───▶│  BC + RL    │───▶│  Benchmark  │──┐           │
│  │  (paralelo) │    │  (GPU/CPU)  │    │  (30+ seeds)│  │           │
│  └─────────────┘    └─────────────┘    └─────────────┘  │           │
│         ▲                                                 │           │
│         └─────── si mejora: actualizar baseline ──────────┘           │
│                  si no mejora: ajustar hiperparámetros                │
└─────────────────────────────────────────────────────────────────────┘
```

El "autopilot" es un script orquestador que llama agentes de Copilot para tareas específicas en cada fase.

---

## Fase 0: Setup (una vez)

### 0.1 Verificar dependencias ML
```bash
cd /home/gris/.openclaw/workspace/repos/CARCOSA
pip install -r requirements-ml.txt
python tools/check_torch.py   # ya existe en el repo
```

### 0.2 Crear script maestro de autopilot
Crear `tools/autopilot.py` — el orchestrator principal.

### 0.3 Crear BCNNPolicy en sim/policies.py
Una nueva policy class que carga `models_bc/bc_mlp_all_best.pt` y lo usa para inferencia.
El esqueleto ya existe (ver `models_bc/`).

---

## Fase 1: Primer Dataset Semilla (30 min aprox)

**Comandos a ejecutar:**
```bash
# 500 episodios con heurística GOAL como policy semilla
python tools/generate_dataset.py \
    --episodes 500 \
    --workers 4 \
    --policy GOAL \
    --out-dir datasets/seed_v1

# Convertir JSONL a CSV para entrenamiento BC
python tools/ai_ready_export.py \
    --input datasets/seed_v1/seed*.jsonl \
    --mode bc \
    --output data/bc_v1.csv

# Extra: exportar también las partidas GANADORAS por separado (alta calidad)
python tools/ai_ready_export.py \
    --input datasets/seed_v1/seed*.jsonl \
    --mode bc \
    --filter-outcome WIN \
    --output data/bc_v1_wins_only.csv
```

**Por qué 500 episodios:**
- ~7.5% winrate → ~37 episodios ganadores (suficiente señal)
- BC entrena mejor con mezcla de ganados (label=qué hacer) + perdidos (label=qué evitar)
- 500 episodios ≈ 200k pasos, suficiente para BC inicial

---

## Fase 2: Entrenar BC Inicial

```bash
# Entrenar con TODAS las partidas (aprende la política completa)
python train/train_bc.py \
    --data data/bc_v1.csv \
    --epochs 200 \
    --batch-size 128 \
    --lr 1e-3 \
    --hidden-sizes 256 128 64 \
    --save-dir models_bc \
    --device cuda  # o cpu si no hay GPU disponible

# Entrenar versión "elite" solo con victorias
python train/train_bc.py \
    --data data/bc_v1_wins_only.csv \
    --filter-outcome WIN \
    --epochs 300 \
    --batch-size 64 \
    --save-dir models_bc/elite_v1 \
    --device cuda
```

**Checkpoint guardado como:** `models_bc/bc_mlp_v1.pt`

---

## Fase 3: Integrar BC Model como Policy

### 3.1 Crear BCNNPlayerPolicy en sim/policies.py

```python
class BCNNPlayerPolicy(PlayerPolicy):
    """Policy neuronal entrenada con Behavioral Cloning."""
    
    def __init__(self, model_path: str = "models_bc/bc_mlp_all_best.pt"):
        import torch
        from train.model import CarcosaPolicyNet
        self.model = CarcosaPolicyNet(obs_dim=10, num_actions=20)
        checkpoint = torch.load(model_path, map_location="cpu")
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()
    
    def choose(self, state: GameState, rng: RNG) -> Action:
        # 1. Extraer features del estado actual
        # 2. Obtener logits del modelo
        # 3. Maskear acciones ilegales
        # 4. Argmax sobre logits legales
        ...
```

**Verificar si ya existe en el código:**
```bash
grep -n "BCNNPlayerPolicy\|bc_policy\|load.*bc.*pt" /home/gris/.openclaw/workspace/repos/CARCOSA/sim/policies.py
```

### 3.2 Registrar en runner.py

```python
# En get_player_policy():
elif policy_name == "BCNN":
    from sim.policies import BCNNPlayerPolicy
    return BCNNPlayerPolicy(model_path=getattr(cfg, "BC_MODEL_PATH", "models_bc/bc_mlp_all_best.pt"))
```

---

## Fase 4: Benchmark Comparativo

```bash
# Benchmark heurística actual
python tools/bench_winrate.py --seeds 50 --max-steps 900 --policy GOAL

# Benchmark modelo BC
python tools/bench_winrate.py --seeds 50 --max-steps 900 --policy BCNN

# Benchmark modelo BC elite (solo entrenado con victorias)
python tools/bench_winrate.py --seeds 50 --max-steps 900 --policy BCNN_ELITE
```

**Criterio de mejora:** BC supera ≥ 10% winrate para continuar al loop RL.

---

## Fase 5: Fine-tune con RL (PPO + Action Masking)

Si BC ≥ 10%:
```bash
# RL Fine-tuning partiendo del modelo BC
python train/train_rl.py \
    --algo ppo \
    --timesteps 500000 \
    --n-envs 8 \
    --pretrain-model models_bc/bc_mlp_v1.pt \
    --save-dir models_rl/ppo_v1

# Evaluación
python train/run_eval.py --model models_rl/ppo_v1/best_model.zip --episodes 50
```

---

## Script Autopilot Completo (tools/autopilot.py)

Crear este archivo para orquestar todo el loop automáticamente:

```python
"""
CARCOSA Autopilot - Ciclo autónomo de mejora de bots.

Ejecuta el ciclo: Generate → Export → Train BC → Benchmark → (quizás RL) → repeat

Uso:
    python tools/autopilot.py --iterations 5 --episodes-per-iter 300 --workers 4
    python tools/autopilot.py --iterations 10 --target-winrate 0.25
"""

import subprocess, json, sys, argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent

def run_generation(iteration: int, n_episodes: int, workers: int) -> dict:
    """Fase 1: Generar dataset."""
    out_dir = ROOT / f"datasets/auto_iter{iteration:02d}"
    # ... llamar generate_dataset.py ...

def run_export(iteration: int) -> Path:
    """Fase 2: Convertir JSONL a CSV."""
    # ... llamar ai_ready_export.py ...

def run_training(iteration: int, csv_path: Path, prev_model: Path) -> Path:
    """Fase 3: Entrenar BC (+ fine-tune RL si iteración > 2)."""
    # ... llamar train_bc.py con warm-start del modelo anterior ...

def run_benchmark(policy: str, seeds: int = 40) -> float:
    """Fase 4: Benchmark y retornar winrate."""
    # ... llamar bench_winrate.py y parsear output ...

def main():
    # Loop principal con logging, checkpoints, y criterio de parada
    best_winrate = 0.075  # baseline heurístico
    ...
```

---

## Paralelización con Múltiples Agentes Copilot

### Cuándo y cómo paralelizar

Las fases **no son todas paralelizables** entre sí (hay dependencias), pero DENTRO de cada fase sí:

| Fase | Paralelizable | Cómo |
|---|---|---|
| Generación de dataset | ✅ Sí | `--workers 4-8` en generate_dataset.py |
| Export/preparación | ✅ Sí | Procesar múltiples JSONL en paralelo |
| Entrenamiento | ⚠️ Parcial | BC + RL en paralelo si hay GPU; múltiples seeds de HP |
| Benchmark | ✅ Sí | Múltiples policies en paralelo |

### Estrategia Multi-Agente para sesión Copilot

Para usar múltiples agentes Copilot en **la misma sesión**, lanzar subagents para:

```
AGENTE PRINCIPAL (orquestador)
├── Subagente A: Ejecutar generate_dataset.py --workers 4
├── Subagente B: Analizar dataset previo + calcular métricas de mejora
├── Subagente C: Revisar y sugerir ajustes de hiperparámetros BC
└── Subagente D: Validar que el código de BCNNPlayerPolicy funciona
```

**Instrucción para el agente orquestador:**
> "Eres el coordinador del ciclo de mejora de CARCOSA. Tu rol es:
> 1. Decidir qué hace cada subagente en la iteración actual
> 2. Integrar los resultados
> 3. Decidir si continuar o ajustar la estrategia
> 4. Mantener `reports/experiments.csv` actualizado"

---

## Cronograma estimado por iteración

| Paso | Tiempo (CPU) | Tiempo (GPU) |
|---|---|---|
| Generar 500 episodios (4 workers) | ~3 min | ~3 min |
| Export JSONL → CSV | ~2 min | ~2 min |
| Train BC (200 epochs, 200k pasos) | ~15 min | ~3 min |
| Benchmark 50 seeds | ~3 min | ~3 min |
| **Total por iteración** | **~23 min** | **~11 min** |

5 iteraciones: ~2h CPU, ~1h GPU.

---

## Criterios de Convergencia / Parada

```python
STOP_IF_WINRATE >= 0.30      # 30% es muy bueno para este juego
STOP_IF_NO_IMPROVEMENT_FOR = 3   # iteraciones sin mejora
MIN_IMPROVEMENT_PER_ITER = 0.02  # al menos +2% para continuar
MAX_ITERATIONS = 15
```

---

## Checklist para la Conversación Nueva

Antes de iniciar, verificar:

- [ ] `pip install -r requirements-ml.txt` ejecutado exitosamente
- [ ] `python tools/check_torch.py` sin errores (confirmar GPU si disponible)
- [ ] `python tools/generate_dataset.py --episodes 5 --policy GOAL` genera archivos OK
- [ ] `python train/train_bc.py --help` sin errores de import
- [ ] Baseline actual: **7.5% winrate** con `GoalDirectedPlayerPolicy` (policy_params.json v2)

---

## Prompt para Iniciar la Conversación Nueva

Copiar esto como primer mensaje:

```
Quiero iniciar el ciclo de autopilot ML para CARCOSA.

Contexto:
- Simulador Python en /home/gris/.openclaw/workspace/repos/CARCOSA
- Policy heurística actual: 7.5% winrate (GoalDirectedPlayerPolicy en sim/policies.py)  
- Los bots pierden porque apply_minus5_consequences destruye todas las llaves del jugador
  cuando llega a -5 sanity (~26 eventos/partida → espiral de destrucción de llaves)
- La infraestructura ML ya existe: train/train_bc.py, train/carcosa_env.py, train/train_rl.py
- El generador de datos ya existe: tools/generate_dataset.py (1.2s/ep, paralelo)

Plan: docs/AUTOPILOT_PLAN.md (este archivo)

Tarea: Ejecutar el ciclo completo siguiendo el plan. Comenzar por Fase 0 (verificar deps)
y Fase 1 (generar dataset semilla de 300 episodios con 4 workers).
Luego Fase 2 (train BC) y Fase 4 (benchmark comparativo BC vs GOAL).
```

---

## Archivos Clave de Referencia

| Archivo | Para qué |
|---|---|
| `sim/policies.py` | Toda la lógica de bots; añadir BCNNPlayerPolicy aquí |
| `sim/policy_params.json` | Parámetros de GoalDirectedPlayerPolicy (v2 actual) |
| `train/model.py` | CarcosaPolicyNet (MLP) y CarcosaTransformerPolicy |
| `train/dataset.py` | CarcosaDataset — cómo cargar CSV para BC |
| `train/carcosa_env.py` | Gym wrapper para RL (StableBaselines3) |
| `engine/tension.py` | `compute_features()` — las 10 features del estado |
| `models_bc/bc_mlp_all_best.pt` | Último modelo BC guardado |
| `reports/experiments.csv` | Log histórico de experimentos |
| `tools/ai_ready_export.py` | Convierte JSONL runs → CSV para training |

---

## Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| BC imita pérdidas (7.5% victorias < datos ganados) | Usar `--filter-outcome WIN` para BC elite; mezclar ambos |
| Modelo RL aprende estrategia equivocada | Pre-entrenar con BC primero, luego fine-tune RL |
| Overfitting a seeds de entrenamiento | Evaluar siempre en seeds diferentes (start-seed=5001) |
| Tiempo de entrenamiento demasiado largo | Usar GPU; reducir timesteps RL inicialmente |
| Loop sin convergencia | Hard-stop en 15 iteraciones; revisar reward function en carcosa_env.py |

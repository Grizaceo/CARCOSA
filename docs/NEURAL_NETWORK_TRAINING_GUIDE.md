# Guía de Entrenamiento de Redes Neuronales para CARCOSA

## Objetivo

Entrenar agentes de IA que **imiten el comportamiento de jugadores humanos** de CARCOSA usando los bots heurísticos existentes como proxy inicial. Estos agentes permitirán:

1. **Testeo de balance**: Simular partidas con "jugadores virtuales" para probar nuevas cartas, roles, etc.
2. **Desarrollo de versión digital**: Base para IA adversarial en el juego digital
3. **Análisis estratégico**: Descubrir estrategias óptimas y debilidades del diseño

---

## Glosario Rápido

| Término | Significado |
|---------|-------------|
| **Behavioral Cloning (BC)** | Aprendizaje supervisado donde la red aprende a imitar decisiones de un experto |
| **Imitation Learning** | Término general que incluye BC y otras técnicas |
| **Reinforcement Learning (RL)** | La red aprende por prueba y error, recibiendo rewards |
| **Gymnasium** | Librería estándar para definir entornos de RL (sucesor de OpenAI Gym) |
| **Policy Network** | Red neuronal que mapea: estado → probabilidad de cada acción |
| **Transformer** | Arquitectura de red con "atención" (usada en GPT, etc.) |
| **MLP** | Multi-Layer Perceptron - red neuronal básica (fully connected) |

---

## Arquitectura Recomendada

### Fase 1: Behavioral Cloning (Supervisado)

```
┌─────────────────┐     ┌──────────────┐     ┌────────────────┐
│  Observation    │ ──▶ │  Policy Net  │ ──▶ │  Action Probs  │
│  (10 features)  │     │  (MLP/Trans) │     │  (softmax)     │
└─────────────────┘     └──────────────┘     └────────────────┘
         │                                           │
         │           CrossEntropyLoss               │
         └──────────────────────────────────────────┘
```

**Input (Observation Vector):**
```python
[P_sanity, P_keys, P_mon, P_umbral, P_debuff, P_king_risk, P_crown, P_round, tension, king_floor_norm]
# 10 features normalizados [0, 1]
```

**Output:**
```python
# Probabilidad de cada acción posible
[P(MOVE), P(SEARCH), P(MEDITATE), P(END_TURN), P(SACRIFICE), ...]
```

### Fase 2: Fine-tuning con RL (Opcional)

Después del pre-entrenamiento con BC, se puede refinar con RL:
- PPO (Proximal Policy Optimization)
- A2C (Advantage Actor-Critic)

---

## Redes Existentes Aplicables

### 1. **Pequeñas (Recomendadas para empezar)**

| Red | Parámetros | Uso |
|-----|------------|-----|
| **MLP 3-Layer** | ~10K | Baseline, rápido de entrenar |
| **MLP 5-Layer** | ~50K | Mejor capacidad, aún rápido |

### 2. **Medianas (Para refinamiento)**

| Red | Parámetros | Uso |
|-----|------------|-----|
| **Transformer Pequeño** | ~500K | Captura dependencias temporales |
| **LSTM/GRU** | ~200K | Memoria de secuencias |

### 3. **Referencia: Redes Usadas en Juegos Similares**

| Proyecto | Juego | Arquitectura | Notas |
|----------|-------|--------------|-------|
| [AlphaGo](https://www.nature.com/articles/nature16961) | Go | CNN + MCTS | Demasiado complejo para CARCOSA |
| [OpenAI Five](https://openai.com/five/) | Dota 2 | LSTM | Requiere recursos masivos |
| [PokerRL](https://github.com/EricSteinberger/PokerRL) | Poker | Feedforward | **Muy aplicable** - mismo tipo de problema |
| [Hanabi](https://github.com/google-deepmind/hanabi-learning-environment) | Hanabi | LSTM/Transformer | **Muy aplicable** - cooperativo con info oculta |
| [StableBaselines3](https://stable-baselines3.readthedocs.io/) | General | PPO/A2C/DQN | **Usar esto** - implementación lista |

**Recomendación:** Comenzar con **StableBaselines3** + **MLP Policy** para BC, luego evaluar si se necesita algo más complejo.

---

## Setup del Entorno

### Requisitos

```bash
# En PowerShell (Windows) o bash (WSL)
cd C:\Users\usuario\Desktop\Code\carcosa

# Activar venv
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate   # WSL

# Instalar dependencias de ML
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install gymnasium stable-baselines3 pandas numpy scikit-learn tensorboard
```

### Verificar GPU (RTX 4060)

```python
import torch
print(f"CUDA disponible: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
# Debería imprimir: NVIDIA GeForce RTX 4060
```

---

## Paso a Paso: Behavioral Cloning

### 1. Generar Datos de Entrenamiento

```bash
# Generar partidas con diferentes policies
for policy in GOAL COWARD BERSERKER SPEEDRUNNER; do
    for seed in {1..50}; do
        python -m sim.runner --seed $seed --policy $policy
    done
done
```

### 2. Exportar Dataset para BC

```bash
python tools/ai_ready_export.py \
    --input runs/*.jsonl \
    --mode bc \
    --output data/bc_training.csv \
    --filter-outcome WIN  # Solo partidas ganadas
```

Esto genera:
- `data/bc_training.csv` - Dataset principal
- `data/bc_training.action_mapping.json` - Mapeo acción→ID

### 3. Crear Dataset PyTorch

```python
# train/dataset.py
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader

class CarcosaDataset(Dataset):
    """Dataset para Behavioral Cloning de CARCOSA."""
    
    # Columnas de observación (features de entrada)
    OBS_COLS = [
        "obs_P_sanity", "obs_P_keys", "obs_P_mon", "obs_P_umbral",
        "obs_P_debuff", "obs_P_king_risk", "obs_P_crown", "obs_P_round",
        "obs_tension", "obs_king_floor_norm"
    ]
    
    def __init__(self, csv_path: str, filter_policy: str = None):
        self.df = pd.read_csv(csv_path)
        
        # Filtrar por policy si se especifica
        if filter_policy:
            self.df = self.df[self.df["policy"] == filter_policy]
        
        # Convertir a tensores
        self.observations = torch.tensor(
            self.df[self.OBS_COLS].values, 
            dtype=torch.float32
        )
        self.actions = torch.tensor(
            self.df["action_id"].values,
            dtype=torch.long
        )
        
    def __len__(self):
        return len(self.df)
    
    def __getitem__(self, idx):
        return self.observations[idx], self.actions[idx]
    
    @property
    def num_actions(self):
        return self.actions.max().item() + 1
    
    @property
    def obs_dim(self):
        return len(self.OBS_COLS)


def create_dataloaders(csv_path: str, batch_size: int = 64, val_split: float = 0.2):
    """Crea DataLoaders para train/val."""
    dataset = CarcosaDataset(csv_path)
    
    # Split train/val
    train_size = int(len(dataset) * (1 - val_split))
    val_size = len(dataset) - train_size
    train_ds, val_ds = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    
    return train_loader, val_loader, dataset.num_actions, dataset.obs_dim
```

### 4. Definir Red Neuronal

```python
# train/model.py
import torch
import torch.nn as nn

class CarcosaPolicyNet(nn.Module):
    """
    Policy Network para CARCOSA.
    Arquitectura MLP simple pero efectiva.
    """
    
    def __init__(self, obs_dim: int, num_actions: int, hidden_sizes: list = [128, 128, 64]):
        super().__init__()
        
        layers = []
        prev_size = obs_dim
        
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(0.1),  # Regularización
            ])
            prev_size = hidden_size
        
        # Capa final (logits para cada acción)
        layers.append(nn.Linear(prev_size, num_actions))
        
        self.network = nn.Sequential(*layers)
        
    def forward(self, obs):
        """
        Args:
            obs: Tensor [batch, obs_dim]
        Returns:
            logits: Tensor [batch, num_actions]
        """
        return self.network(obs)
    
    def predict(self, obs):
        """Predice la acción más probable."""
        with torch.no_grad():
            logits = self.forward(obs)
            return torch.argmax(logits, dim=-1)
    
    def predict_proba(self, obs):
        """Retorna probabilidades de cada acción."""
        with torch.no_grad():
            logits = self.forward(obs)
            return torch.softmax(logits, dim=-1)


class CarcosaTransformerPolicy(nn.Module):
    """
    Versión con Transformer (para secuencias de decisiones).
    Usar si se quiere capturar contexto temporal.
    """
    
    def __init__(self, obs_dim: int, num_actions: int, 
                 d_model: int = 64, nhead: int = 4, num_layers: int = 2):
        super().__init__()
        
        self.embedding = nn.Linear(obs_dim, d_model)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, 
            nhead=nhead,
            dim_feedforward=d_model * 4,
            dropout=0.1,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        self.output = nn.Linear(d_model, num_actions)
        
    def forward(self, obs):
        # obs: [batch, seq_len, obs_dim] o [batch, obs_dim]
        if obs.dim() == 2:
            obs = obs.unsqueeze(1)  # [batch, 1, obs_dim]
        
        x = self.embedding(obs)
        x = self.transformer(x)
        x = x.mean(dim=1)  # Pool sobre secuencia
        return self.output(x)
```

### 5. Entrenamiento

```python
# train/train_bc.py
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from dataset import create_dataloaders
from model import CarcosaPolicyNet

def train_behavioral_cloning(
    csv_path: str,
    epochs: int = 100,
    batch_size: int = 64,
    lr: float = 1e-3,
    device: str = "cuda"
):
    """
    Entrena policy network con Behavioral Cloning.
    """
    # Setup
    device = torch.device(device if torch.cuda.is_available() else "cpu")
    print(f"Usando dispositivo: {device}")
    
    # Data
    train_loader, val_loader, num_actions, obs_dim = create_dataloaders(
        csv_path, batch_size=batch_size
    )
    print(f"Obs dim: {obs_dim}, Num actions: {num_actions}")
    print(f"Train samples: {len(train_loader.dataset)}, Val samples: {len(val_loader.dataset)}")
    
    # Model
    model = CarcosaPolicyNet(obs_dim, num_actions).to(device)
    print(f"Parámetros: {sum(p.numel() for p in model.parameters()):,}")
    
    # Training
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    
    writer = SummaryWriter("runs/bc_training")
    best_val_acc = 0
    
    for epoch in range(epochs):
        # Train
        model.train()
        train_loss = 0
        train_correct = 0
        train_total = 0
        
        for obs, actions in train_loader:
            obs, actions = obs.to(device), actions.to(device)
            
            optimizer.zero_grad()
            logits = model(obs)
            loss = criterion(logits, actions)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            train_correct += (logits.argmax(dim=-1) == actions).sum().item()
            train_total += actions.size(0)
        
        # Validate
        model.eval()
        val_loss = 0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for obs, actions in val_loader:
                obs, actions = obs.to(device), actions.to(device)
                logits = model(obs)
                loss = criterion(logits, actions)
                
                val_loss += loss.item()
                val_correct += (logits.argmax(dim=-1) == actions).sum().item()
                val_total += actions.size(0)
        
        train_acc = train_correct / train_total
        val_acc = val_correct / val_total
        
        scheduler.step(val_loss)
        
        # Logging
        writer.add_scalar("Loss/train", train_loss / len(train_loader), epoch)
        writer.add_scalar("Loss/val", val_loss / len(val_loader), epoch)
        writer.add_scalar("Accuracy/train", train_acc, epoch)
        writer.add_scalar("Accuracy/val", val_acc, epoch)
        
        if epoch % 10 == 0:
            print(f"Epoch {epoch}: Train Acc={train_acc:.4f}, Val Acc={val_acc:.4f}")
        
        # Save best
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), "models/bc_policy_best.pt")
            print(f"  -> Nuevo mejor modelo guardado (val_acc={val_acc:.4f})")
    
    writer.close()
    print(f"\nEntrenamiento completado. Mejor val_acc: {best_val_acc:.4f}")
    return model


if __name__ == "__main__":
    import os
    os.makedirs("models", exist_ok=True)
    
    train_behavioral_cloning(
        csv_path="data/bc_training.csv",
        epochs=100,
        batch_size=64,
        lr=1e-3
    )
```

### 6. Ejecutar Entrenamiento

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
python train/train_bc.py

# Monitorear con TensorBoard
tensorboard --logdir=runs
# Abrir http://localhost:6006
```

---

## Integración con Gymnasium (Para RL)

### Crear Entorno Gymnasium

```python
# train/carcosa_env.py
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Tuple, Dict, Any

from engine.config import Config
from engine.rng import RNG
from engine.transition import step
from engine.legality import get_legal_actions
from sim.runner import make_smoke_state


class CarcosaEnv(gym.Env):
    """
    Entorno Gymnasium para CARCOSA.
    
    Observation: Vector de 10 features normalizados
    Action: ID de acción (0 a N-1)
    Reward: +100 WIN, -10 LOSE, pequeños rewards intermedios
    """
    
    metadata = {"render_modes": ["human"]}
    
    def __init__(self, seed: int = None, render_mode: str = None):
        super().__init__()
        
        self.cfg = Config()
        self.seed_value = seed or np.random.randint(0, 10000)
        self.render_mode = render_mode
        
        # Observation space: 10 features [0, 1]
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(10,), dtype=np.float32
        )
        
        # Action space: Definido dinámicamente por acciones legales
        # Usamos Discrete con el máximo posible
        self.action_space = spaces.Discrete(20)  # Max ~20 tipos de acción
        
        # Mapeo de acciones
        self.action_types = self._build_action_mapping()
        
        self.state = None
        self.rng = None
        
    def _build_action_mapping(self):
        """Construye mapeo ID → ActionType."""
        from engine.actions import ActionType
        return {i: at for i, at in enumerate(ActionType)}
    
    def _get_obs(self) -> np.ndarray:
        """Extrae observación del estado actual."""
        from engine.tension import compute_features, tension_T
        
        features = compute_features(self.state, self.cfg)
        obs = np.array([
            features.get("P_sanity", 0.0),
            features.get("P_keys", 0.0),
            features.get("P_mon", 0.0),
            features.get("P_umbral", 0.0),
            features.get("P_debuff", 0.0),
            features.get("P_king_risk", 0.0),
            features.get("P_crown", 0.0),
            features.get("P_round", 0.0),
            tension_T(self.state, self.cfg, features=features),
            self.state.king_floor / 3.0,
        ], dtype=np.float32)
        return obs
    
    def _get_legal_action_mask(self) -> np.ndarray:
        """Retorna máscara de acciones legales."""
        actor = str(self.state.turn_order[self.state.turn_pos])
        legal = get_legal_actions(self.state, actor)
        
        mask = np.zeros(self.action_space.n, dtype=np.float32)
        for action in legal:
            action_id = list(self.action_types.values()).index(action.type)
            mask[action_id] = 1.0
        return mask
    
    def reset(self, seed: int = None, options: Dict = None) -> Tuple[np.ndarray, Dict]:
        super().reset(seed=seed)
        
        if seed is not None:
            self.seed_value = seed
        
        self.rng = RNG(self.seed_value)
        self.state = make_smoke_state(seed=self.seed_value, cfg=self.cfg)
        
        obs = self._get_obs()
        info = {
            "legal_actions": self._get_legal_action_mask(),
            "round": self.state.round,
        }
        return obs, info
    
    def step(self, action_id: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Ejecuta una acción en el entorno.
        
        Returns:
            obs, reward, terminated, truncated, info
        """
        from engine.actions import Action
        
        # Obtener actor actual
        actor = str(self.state.turn_order[self.state.turn_pos])
        legal = get_legal_actions(self.state, actor)
        
        # Mapear action_id a Action
        target_type = self.action_types.get(action_id)
        action = None
        for a in legal:
            if a.type == target_type:
                action = a
                break
        
        # Si la acción no es legal, elegir una random legal
        if action is None:
            action = self.rng.choice(legal) if legal else None
        
        if action is None:
            # No hay acciones legales - terminar
            return self._get_obs(), -10.0, True, False, {"error": "no_legal_actions"}
        
        # Ejecutar transición
        next_state = step(self.state, action, self.rng, self.cfg)
        
        # Calcular reward
        reward = self._calculate_reward(self.state, next_state)
        
        self.state = next_state
        
        # Check terminación
        terminated = self.state.game_over
        truncated = self.state.round > 100  # Timeout
        
        obs = self._get_obs()
        info = {
            "legal_actions": self._get_legal_action_mask(),
            "round": self.state.round,
            "outcome": self.state.outcome,
        }
        
        return obs, reward, terminated, truncated, info
    
    def _calculate_reward(self, state, next_state) -> float:
        """Calcula reward para RL."""
        if next_state.game_over:
            if next_state.outcome == "WIN":
                return 100.0
            else:
                return -10.0
        
        reward = 0.0
        
        # Progreso de llaves
        keys_prev = sum(p.keys for p in state.players.values())
        keys_next = sum(p.keys for p in next_state.players.values())
        reward += (keys_next - keys_prev) * 1.0
        
        # Penalización por pérdida de sanity
        sanity_prev = sum(p.sanity for p in state.players.values())
        sanity_next = sum(p.sanity for p in next_state.players.values())
        reward += (sanity_next - sanity_prev) * 0.1
        
        return reward
    
    def render(self):
        if self.render_mode == "human":
            print(f"Round {self.state.round}, Phase: {self.state.phase}")
            for pid, p in self.state.players.items():
                print(f"  {pid}: Room={p.room}, Sanity={p.sanity}, Keys={p.keys}")


# Registrar entorno
gym.register(
    id="Carcosa-v0",
    entry_point="train.carcosa_env:CarcosaEnv",
)
```

### Entrenar con StableBaselines3

```python
# train/train_rl.py
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import EvalCallback
import gymnasium as gym

# Importar para registrar
import train.carcosa_env

def train_ppo():
    """Entrena agente con PPO (Proximal Policy Optimization)."""
    
    # Crear entorno vectorizado (paraleliza en CPU)
    env = make_vec_env("Carcosa-v0", n_envs=4)
    
    # Crear modelo con red MLP
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        verbose=1,
        tensorboard_log="./runs/ppo_carcosa/"
    )
    
    # Callback para evaluación
    eval_env = gym.make("Carcosa-v0")
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path="./models/",
        log_path="./logs/",
        eval_freq=10000,
        deterministic=True,
        render=False
    )
    
    # Entrenar
    model.learn(
        total_timesteps=500_000,
        callback=eval_callback,
        progress_bar=True
    )
    
    model.save("models/ppo_carcosa_final")
    print("Entrenamiento completado!")


if __name__ == "__main__":
    train_ppo()
```

---

## Workflow Completo Recomendado

```
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE DE ENTRENAMIENTO                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                               │
│  │ 1. GENERAR   │  python -m sim.runner --policy GOAL --seed N  │
│  │    DATOS     │  (50-200 partidas por policy)                 │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │ 2. EXPORTAR  │  python tools/ai_ready_export.py --mode bc    │
│  │    DATASET   │  --filter-outcome WIN                         │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │ 3. BC PRE-   │  python train/train_bc.py                     │
│  │    TRAINING  │  (100 epochs, ~5 min en 4060)                 │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │ 4. EVALUAR   │  python train/evaluate.py                     │
│  │    EN JUEGO  │  (win rate, comparar con bots)                │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼  (Opcional)                                           │
│  ┌──────────────┐                                               │
│  │ 5. RL FINE-  │  python train/train_rl.py                     │
│  │    TUNING    │  (PPO, 500K steps, ~2 horas en 4060)          │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │ 6. TESTING   │  Simular nuevas cartas/roles                  │
│  │    BALANCE   │  Comparar win rates                           │
│  └──────────────┘                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Estructura de Archivos Propuesta

```
CARCOSA/
├── train/                    # NUEVO: Código de entrenamiento
│   ├── __init__.py
│   ├── dataset.py            # CarcosaDataset para PyTorch
│   ├── model.py              # Redes neuronales (MLP, Transformer)
│   ├── train_bc.py           # Script de Behavioral Cloning
│   ├── train_rl.py           # Script de RL con StableBaselines3
│   ├── carcosa_env.py        # Entorno Gymnasium
│   └── evaluate.py           # Evaluación de modelos
│
├── models/                   # Modelos entrenados guardados
│   ├── bc_policy_best.pt
│   └── ppo_carcosa_final.zip
│
├── data/                     # Datasets exportados
│   ├── bc_training.csv
│   └── bc_training.action_mapping.json
│
└── runs/                     # TensorBoard logs + JSONL de partidas
```

---

## Recursos Adicionales

### Tutoriales Recomendados
1. [PyTorch Beginner Tutorial](https://pytorch.org/tutorials/beginner/basics/intro.html)
2. [StableBaselines3 Docs](https://stable-baselines3.readthedocs.io/)
3. [Gymnasium Docs](https://gymnasium.farama.org/)
4. [Behavioral Cloning Paper](https://arxiv.org/abs/1011.0686)

### Proyectos de Referencia
1. [PokerRL](https://github.com/EricSteinberger/PokerRL) - RL para juegos de cartas
2. [Hanabi Learning Environment](https://github.com/google-deepmind/hanabi-learning-environment) - Cooperativo
3. [PettingZoo](https://pettingzoo.farama.org/) - Multi-agent RL

---

## FAQ

### ¿Por qué empezar con BC en vez de RL directo?

BC es **mucho más rápido** de entrenar porque es supervisado. RL desde cero requiere millones de pasos para aprender comportamientos básicos. BC te da un "buen punto de partida" en minutos.

### ¿Qué tamaño de red necesito?

Para CARCOSA, un **MLP de 3 capas con 128 neuronas** es suficiente para empezar. Solo si el accuracy se estanca, considera Transformers.

### ¿Cuántos datos necesito?

- **Mínimo**: 50 partidas (~5,000 decisiones)
- **Recomendado**: 200+ partidas (~20,000 decisiones)
- **Óptimo**: 1000+ partidas (~100,000 decisiones)

### ¿Puedo usar el modelo entrenado en el simulador?

¡Sí! Crea una `NeuralNetworkPlayerPolicy` que cargue el modelo y lo use en `choose()`.

---

**Última actualización:** 29 de enero de 2026
**Autor:** Sistema CARCOSA

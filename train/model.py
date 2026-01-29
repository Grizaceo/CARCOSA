"""
Modelos de Redes Neuronales para CARCOSA
=========================================
Implementaciones de Policy Networks para Behavioral Cloning y RL.
"""

import torch
import torch.nn as nn
from typing import List, Optional


class CarcosaPolicyNet(nn.Module):
    """
    Policy Network MLP para CARCOSA.
    
    Arquitectura simple pero efectiva para behavioral cloning.
    Mapea observación (10 features) a logits de acciones.
    """
    
    def __init__(
        self, 
        obs_dim: int, 
        num_actions: int, 
        hidden_sizes: List[int] = None,
        dropout: float = 0.1
    ):
        """
        Args:
            obs_dim: Dimensión del vector de observación
            num_actions: Número de acciones posibles
            hidden_sizes: Lista de tamaños de capas ocultas
            dropout: Probabilidad de dropout
        """
        super().__init__()
        
        if hidden_sizes is None:
            hidden_sizes = [128, 128, 64]
        
        layers = []
        prev_size = obs_dim
        
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(dropout),
            ])
            prev_size = hidden_size
        
        # Capa final (logits para cada acción)
        layers.append(nn.Linear(prev_size, num_actions))
        
        self.network = nn.Sequential(*layers)
        
        # Inicialización
        self._init_weights()
        
    def _init_weights(self):
        """Inicialización de pesos Xavier."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
        
    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            obs: Tensor [batch, obs_dim]
        Returns:
            logits: Tensor [batch, num_actions]
        """
        return self.network(obs)
    
    def predict(self, obs: torch.Tensor) -> torch.Tensor:
        """
        Predice la acción más probable (greedy).
        
        Args:
            obs: Tensor [batch, obs_dim] o [obs_dim]
        Returns:
            actions: Tensor [batch] o escalar
        """
        was_single = obs.dim() == 1
        if was_single:
            obs = obs.unsqueeze(0)
            
        with torch.no_grad():
            logits = self.forward(obs)
            actions = torch.argmax(logits, dim=-1)
            
        if was_single:
            return actions.squeeze(0)
        return actions
    
    def predict_proba(self, obs: torch.Tensor) -> torch.Tensor:
        """
        Retorna probabilidades de cada acción.
        
        Args:
            obs: Tensor [batch, obs_dim] o [obs_dim]
        Returns:
            probs: Tensor [batch, num_actions] o [num_actions]
        """
        was_single = obs.dim() == 1
        if was_single:
            obs = obs.unsqueeze(0)
            
        with torch.no_grad():
            logits = self.forward(obs)
            probs = torch.softmax(logits, dim=-1)
            
        if was_single:
            return probs.squeeze(0)
        return probs
    
    def sample_action(self, obs: torch.Tensor, temperature: float = 1.0) -> torch.Tensor:
        """
        Samplea una acción según las probabilidades (con temperatura).
        
        Args:
            obs: Tensor de observación
            temperature: >1 = más exploración, <1 = más explotación
        Returns:
            action: Tensor con la acción sampleada
        """
        was_single = obs.dim() == 1
        if was_single:
            obs = obs.unsqueeze(0)
            
        with torch.no_grad():
            logits = self.forward(obs) / temperature
            probs = torch.softmax(logits, dim=-1)
            actions = torch.multinomial(probs, num_samples=1).squeeze(-1)
            
        if was_single:
            return actions.squeeze(0)
        return actions


class CarcosaTransformerPolicy(nn.Module):
    """
    Policy Network con Transformer para CARCOSA.
    
    Útil para capturar dependencias temporales si se usa
    una secuencia de observaciones como input.
    """
    
    def __init__(
        self, 
        obs_dim: int, 
        num_actions: int, 
        d_model: int = 64, 
        nhead: int = 4, 
        num_layers: int = 2,
        dropout: float = 0.1
    ):
        """
        Args:
            obs_dim: Dimensión de cada observación
            num_actions: Número de acciones posibles
            d_model: Dimensión del modelo transformer
            nhead: Número de cabezas de atención
            num_layers: Número de capas del encoder
            dropout: Probabilidad de dropout
        """
        super().__init__()
        
        self.obs_dim = obs_dim
        self.d_model = d_model
        
        # Embedding lineal de observación a d_model
        self.embedding = nn.Linear(obs_dim, d_model)
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, 
            nhead=nhead,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Output layer
        self.output = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.ReLU(),
            nn.Linear(d_model, num_actions)
        )
        
    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            obs: Tensor [batch, seq_len, obs_dim] o [batch, obs_dim]
        Returns:
            logits: Tensor [batch, num_actions]
        """
        # Si es una sola observación, agregarle dimensión de secuencia
        if obs.dim() == 2:
            obs = obs.unsqueeze(1)  # [batch, 1, obs_dim]
        
        # Embedding
        x = self.embedding(obs)  # [batch, seq, d_model]
        
        # Transformer
        x = self.transformer(x)  # [batch, seq, d_model]
        
        # Pooling sobre secuencia (mean)
        x = x.mean(dim=1)  # [batch, d_model]
        
        # Output
        return self.output(x)
    
    def predict(self, obs: torch.Tensor) -> torch.Tensor:
        """Predice acción greedy."""
        with torch.no_grad():
            logits = self.forward(obs)
            return torch.argmax(logits, dim=-1)


class CarcosaValueNet(nn.Module):
    """
    Value Network para actor-critic.
    Estima V(s) = expected return from state s.
    """
    
    def __init__(
        self, 
        obs_dim: int, 
        hidden_sizes: List[int] = None
    ):
        super().__init__()
        
        if hidden_sizes is None:
            hidden_sizes = [128, 128]
        
        layers = []
        prev_size = obs_dim
        
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.ReLU(),
            ])
            prev_size = hidden_size
        
        # Output: valor escalar
        layers.append(nn.Linear(prev_size, 1))
        
        self.network = nn.Sequential(*layers)
        
    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        """
        Args:
            obs: Tensor [batch, obs_dim]
        Returns:
            values: Tensor [batch, 1]
        """
        return self.network(obs)


class CarcosaActorCritic(nn.Module):
    """
    Actor-Critic combinado para PPO/A2C.
    Comparte las capas iniciales entre policy y value.
    """
    
    def __init__(
        self, 
        obs_dim: int, 
        num_actions: int, 
        shared_sizes: List[int] = None,
        policy_sizes: List[int] = None,
        value_sizes: List[int] = None
    ):
        super().__init__()
        
        if shared_sizes is None:
            shared_sizes = [128]
        if policy_sizes is None:
            policy_sizes = [64]
        if value_sizes is None:
            value_sizes = [64]
        
        # Shared layers
        shared_layers = []
        prev_size = obs_dim
        for size in shared_sizes:
            shared_layers.extend([
                nn.Linear(prev_size, size),
                nn.ReLU()
            ])
            prev_size = size
        self.shared = nn.Sequential(*shared_layers)
        
        # Policy head
        policy_layers = []
        for size in policy_sizes:
            policy_layers.extend([
                nn.Linear(prev_size, size),
                nn.ReLU()
            ])
            prev_size = size
        policy_layers.append(nn.Linear(prev_size, num_actions))
        self.policy_head = nn.Sequential(*policy_layers)
        
        # Value head
        value_layers = []
        prev_size = shared_sizes[-1] if shared_sizes else obs_dim
        for size in value_sizes:
            value_layers.extend([
                nn.Linear(prev_size, size),
                nn.ReLU()
            ])
            prev_size = size
        value_layers.append(nn.Linear(prev_size, 1))
        self.value_head = nn.Sequential(*value_layers)
        
    def forward(self, obs: torch.Tensor):
        """
        Returns:
            policy_logits: [batch, num_actions]
            value: [batch, 1]
        """
        shared = self.shared(obs)
        policy_logits = self.policy_head(shared)
        value = self.value_head(shared)
        return policy_logits, value
    
    def get_action_and_value(self, obs: torch.Tensor, action: Optional[torch.Tensor] = None):
        """
        Para PPO: obtiene action, log_prob, entropy, value.
        """
        policy_logits, value = self.forward(obs)
        probs = torch.softmax(policy_logits, dim=-1)
        dist = torch.distributions.Categorical(probs)
        
        if action is None:
            action = dist.sample()
        
        return action, dist.log_prob(action), dist.entropy(), value.squeeze(-1)


def count_parameters(model: nn.Module) -> int:
    """Cuenta parámetros entrenables."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def load_model(path: str, model_class: type, **kwargs) -> nn.Module:
    """Carga un modelo guardado."""
    model = model_class(**kwargs)
    model.load_state_dict(torch.load(path, map_location="cpu"))
    model.eval()
    return model


if __name__ == "__main__":
    # Test
    obs_dim = 10
    num_actions = 15
    batch_size = 32
    
    # Test MLP
    model = CarcosaPolicyNet(obs_dim, num_actions)
    print(f"MLP params: {count_parameters(model):,}")
    
    x = torch.randn(batch_size, obs_dim)
    logits = model(x)
    print(f"MLP output shape: {logits.shape}")
    
    action = model.predict(x[0])
    print(f"Single prediction: {action}")
    
    # Test Transformer
    trans = CarcosaTransformerPolicy(obs_dim, num_actions)
    print(f"\nTransformer params: {count_parameters(trans):,}")
    
    logits_t = trans(x)
    print(f"Transformer output shape: {logits_t.shape}")
    
    # Test Actor-Critic
    ac = CarcosaActorCritic(obs_dim, num_actions)
    print(f"\nActor-Critic params: {count_parameters(ac):,}")
    
    policy, value = ac(x)
    print(f"Policy shape: {policy.shape}, Value shape: {value.shape}")

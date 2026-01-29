"""
CarcosaDataset - PyTorch Dataset para Behavioral Cloning
=========================================================
Carga datos exportados por ai_ready_export.py y los prepara para entrenamiento.
"""

import json
from pathlib import Path
from typing import Optional, Tuple

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
    
    def __init__(self, csv_path: str, filter_policy: Optional[str] = None, 
                 filter_outcome: Optional[str] = None):
        """
        Args:
            csv_path: Ruta al CSV generado por ai_ready_export.py --mode bc
            filter_policy: Filtrar solo decisiones de esta policy (ej: "GOAL")
            filter_outcome: Filtrar solo decisiones de partidas con este outcome ("WIN", "LOSE")
        """
        self.df = pd.read_csv(csv_path)
        
        # Filtrar por policy si se especifica
        if filter_policy:
            self.df = self.df[self.df["policy"] == filter_policy]
            print(f"Filtrado por policy={filter_policy}: {len(self.df)} registros")
        
        # Filtrar por outcome si se especifica
        if filter_outcome:
            # Solo mantener registros donde outcome final sea el deseado
            # Como estamos en decisiones intermedias, outcome puede ser None
            # Filtramos los que tienen outcome o los que aún no terminaron
            mask = (self.df["outcome"] == filter_outcome) | (self.df["outcome"].isna())
            # Para BC, mejor filtrar solo las terminadas con el outcome deseado
            # Identificar partidas ganadoras por (seed, policy) and back-propagate
            # Por ahora, simple filter
            self.df = self.df[self.df["outcome"] == filter_outcome]
            print(f"Filtrado por outcome={filter_outcome}: {len(self.df)} registros")
        
        if len(self.df) == 0:
            raise ValueError("No hay datos después de filtrar. Verifica los filtros.")
        
        # Verificar columnas
        missing = set(self.OBS_COLS) - set(self.df.columns)
        if missing:
            raise ValueError(f"Columnas faltantes en CSV: {missing}")
        
        # Convertir a tensores
        self.observations = torch.tensor(
            self.df[self.OBS_COLS].values, 
            dtype=torch.float32
        )
        self.actions = torch.tensor(
            self.df["action_id"].values,
            dtype=torch.long
        )
        
        print(f"Dataset cargado: {len(self)} ejemplos, {self.obs_dim} features, {self.num_actions} acciones")
        
    def __len__(self) -> int:
        return len(self.df)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.observations[idx], self.actions[idx]
    
    @property
    def num_actions(self) -> int:
        """Número de acciones únicas."""
        return int(self.actions.max().item()) + 1
    
    @property
    def obs_dim(self) -> int:
        """Dimensión del vector de observación."""
        return len(self.OBS_COLS)
    
    def get_action_mapping(self, mapping_path: Optional[str] = None) -> dict:
        """Carga el mapeo de action_id a action_type."""
        if mapping_path is None:
            # Intentar encontrar el archivo de mapeo junto al CSV
            csv_path = Path(self.df.attrs.get("source_path", "data/bc_training.csv"))
            mapping_path = csv_path.with_suffix(".action_mapping.json")
        
        if Path(mapping_path).exists():
            with open(mapping_path) as f:
                return json.load(f)
        return {}


def create_dataloaders(
    csv_path: str, 
    batch_size: int = 64, 
    val_split: float = 0.2,
    filter_policy: Optional[str] = None,
    filter_outcome: Optional[str] = None,
    num_workers: int = 0,
) -> Tuple[DataLoader, DataLoader, int, int]:
    """
    Crea DataLoaders para train/val.
    
    Args:
        csv_path: Ruta al CSV
        batch_size: Tamaño del batch
        val_split: Fracción para validación
        filter_policy: Filtrar por policy
        filter_outcome: Filtrar por outcome
        num_workers: Workers para data loading (0 para Windows)
    
    Returns:
        train_loader, val_loader, num_actions, obs_dim
    """
    dataset = CarcosaDataset(
        csv_path, 
        filter_policy=filter_policy,
        filter_outcome=filter_outcome
    )
    
    # Split train/val
    train_size = int(len(dataset) * (1 - val_split))
    val_size = len(dataset) - train_size
    
    generator = torch.Generator().manual_seed(42)
    train_ds, val_ds = torch.utils.data.random_split(
        dataset, [train_size, val_size], generator=generator
    )
    
    train_loader = DataLoader(
        train_ds, 
        batch_size=batch_size, 
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True
    )
    val_loader = DataLoader(
        val_ds, 
        batch_size=batch_size, 
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True
    )
    
    print(f"Train: {len(train_ds)} samples, Val: {len(val_ds)} samples")
    
    return train_loader, val_loader, dataset.num_actions, dataset.obs_dim


if __name__ == "__main__":
    # Test
    import sys
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/bc_training.csv"
    
    train_loader, val_loader, num_actions, obs_dim = create_dataloaders(csv_path)
    
    # Inspeccionar un batch
    for obs, actions in train_loader:
        print(f"Batch obs shape: {obs.shape}")
        print(f"Batch actions shape: {actions.shape}")
        print(f"Sample obs: {obs[0]}")
        print(f"Sample action: {actions[0]}")
        break

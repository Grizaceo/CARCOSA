"""
Entrenamiento de Behavioral Cloning para CARCOSA
=================================================
Script principal para entrenar una policy network que imite
las decisiones de los bots heurísticos existentes.

Uso:
    python train/train_bc.py --data data/bc_training.csv --epochs 100
    python train/train_bc.py --data data/bc_training.csv --filter-policy GOAL --epochs 200
"""

import argparse
import os
from pathlib import Path
from datetime import datetime

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter

from dataset import create_dataloaders
from model import CarcosaPolicyNet, CarcosaTransformerPolicy, count_parameters


def train_behavioral_cloning(
    csv_path: str,
    epochs: int = 100,
    batch_size: int = 64,
    lr: float = 1e-3,
    hidden_sizes: list = None,
    use_transformer: bool = False,
    filter_policy: str = None,
    filter_outcome: str = None,
    device: str = "cuda",
    save_dir: str = "models",
    log_dir: str = "runs/bc_training",
):
    """
    Entrena policy network con Behavioral Cloning.
    
    Args:
        csv_path: Ruta al CSV de entrenamiento
        epochs: Número de epochs
        batch_size: Tamaño del batch
        lr: Learning rate
        hidden_sizes: Tamaños de capas ocultas
        use_transformer: Usar Transformer en vez de MLP
        filter_policy: Entrenar solo con datos de esta policy
        filter_outcome: Entrenar solo con partidas de este outcome
        device: "cuda" o "cpu"
        save_dir: Directorio para guardar modelos
        log_dir: Directorio para TensorBoard
    """
    # Setup
    device = torch.device(device if torch.cuda.is_available() else "cpu")
    print(f"="*60)
    print(f"CARCOSA Behavioral Cloning Training")
    print(f"="*60)
    print(f"Dispositivo: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    
    # Data
    train_loader, val_loader, num_actions, obs_dim = create_dataloaders(
        csv_path, 
        batch_size=batch_size,
        filter_policy=filter_policy,
        filter_outcome=filter_outcome,
    )
    print(f"Obs dim: {obs_dim}, Num actions: {num_actions}")
    print(f"Train samples: {len(train_loader.dataset)}, Val samples: {len(val_loader.dataset)}")
    
    # Model
    if use_transformer:
        model = CarcosaTransformerPolicy(obs_dim, num_actions).to(device)
        model_type = "transformer"
    else:
        if hidden_sizes is None:
            hidden_sizes = [128, 128, 64]
        model = CarcosaPolicyNet(obs_dim, num_actions, hidden_sizes=hidden_sizes).to(device)
        model_type = "mlp"
    
    print(f"Modelo: {model_type}")
    print(f"Parámetros: {count_parameters(model):,}")
    
    # Training setup
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='max', patience=10, factor=0.5, verbose=True
    )
    
    # Logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{model_type}_{filter_policy or 'all'}_{timestamp}"
    writer = SummaryWriter(f"{log_dir}/{run_name}")
    
    # Save directory
    Path(save_dir).mkdir(exist_ok=True, parents=True)
    
    best_val_acc = 0
    best_model_path = None
    
    print(f"\nIniciando entrenamiento...")
    print(f"TensorBoard: tensorboard --logdir={log_dir}")
    print(f"-"*60)
    
    for epoch in range(epochs):
        # === TRAIN ===
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
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            
            optimizer.step()
            
            train_loss += loss.item()
            train_correct += (logits.argmax(dim=-1) == actions).sum().item()
            train_total += actions.size(0)
        
        # === VALIDATE ===
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
        
        # Métricas
        train_loss_avg = train_loss / len(train_loader)
        val_loss_avg = val_loss / len(val_loader)
        train_acc = train_correct / train_total
        val_acc = val_correct / val_total
        
        # Learning rate scheduling
        scheduler.step(val_acc)
        current_lr = optimizer.param_groups[0]['lr']
        
        # Logging
        writer.add_scalar("Loss/train", train_loss_avg, epoch)
        writer.add_scalar("Loss/val", val_loss_avg, epoch)
        writer.add_scalar("Accuracy/train", train_acc, epoch)
        writer.add_scalar("Accuracy/val", val_acc, epoch)
        writer.add_scalar("LR", current_lr, epoch)
        
        # Print progress
        if epoch % 10 == 0 or epoch == epochs - 1:
            print(f"Epoch {epoch:3d}/{epochs}: "
                  f"Train Loss={train_loss_avg:.4f} Acc={train_acc:.4f} | "
                  f"Val Loss={val_loss_avg:.4f} Acc={val_acc:.4f} | "
                  f"LR={current_lr:.2e}")
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_model_path = f"{save_dir}/bc_{model_type}_{filter_policy or 'all'}_best.pt"
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_acc': val_acc,
                'obs_dim': obs_dim,
                'num_actions': num_actions,
                'hidden_sizes': hidden_sizes if not use_transformer else None,
                'model_type': model_type,
            }, best_model_path)
            print(f"  -> Nuevo mejor modelo guardado (val_acc={val_acc:.4f})")
        
        # Early stopping check
        if current_lr < 1e-6:
            print("Learning rate muy bajo, deteniendo...")
            break
    
    writer.close()
    
    print(f"\n{'='*60}")
    print(f"Entrenamiento completado!")
    print(f"Mejor val_acc: {best_val_acc:.4f}")
    print(f"Modelo guardado en: {best_model_path}")
    print(f"{'='*60}")
    
    return model, best_val_acc


def main():
    parser = argparse.ArgumentParser(description="Train Behavioral Cloning for CARCOSA")
    
    # Data
    parser.add_argument("--data", type=str, default="data/bc_training.csv",
                        help="Ruta al CSV de entrenamiento")
    parser.add_argument("--filter-policy", type=str, default=None,
                        help="Entrenar solo con datos de esta policy")
    parser.add_argument("--filter-outcome", type=str, default=None,
                        choices=["WIN", "LOSE", "TIMEOUT"],
                        help="Entrenar solo con partidas de este outcome")
    
    # Training
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    
    # Model
    parser.add_argument("--hidden", type=int, nargs="+", default=[128, 128, 64],
                        help="Tamaños de capas ocultas")
    parser.add_argument("--transformer", action="store_true",
                        help="Usar Transformer en vez de MLP")
    
    # Output
    parser.add_argument("--save-dir", type=str, default="models")
    parser.add_argument("--log-dir", type=str, default="runs/bc_training")
    
    # Device
    parser.add_argument("--device", type=str, default="cuda",
                        choices=["cuda", "cpu"])
    
    args = parser.parse_args()
    
    # Verificar que existe el CSV
    if not Path(args.data).exists():
        print(f"ERROR: No se encontró {args.data}")
        print("Primero genera los datos con:")
        print("  python tools/ai_ready_export.py --input runs/*.jsonl --mode bc --output data/bc_training.csv")
        return
    
    train_behavioral_cloning(
        csv_path=args.data,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        hidden_sizes=args.hidden,
        use_transformer=args.transformer,
        filter_policy=args.filter_policy,
        filter_outcome=args.filter_outcome,
        device=args.device,
        save_dir=args.save_dir,
        log_dir=args.log_dir,
    )


if __name__ == "__main__":
    main()

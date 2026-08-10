import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import pickle
import argparse
from pathlib import Path

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sb3_contrib import MaskablePPO


def train_bc(
    data_path="train/goldset_500_wins.pkl",
    model_save_path="models/bc_goldset_v1",
    epochs=200,
    lr=1e-3,
    batch_size=64,
    device="cpu",
):
    # Load data
    if str(data_path).endswith(".csv"):
        import csv
        from train.carcosa_env import CarcosaEnv

        action_types_list = [a.value for a in CarcosaEnv.ACTION_TYPES]
        observations = []
        actions = []

        obs_cols = [
            "obs_P_sanity",
            "obs_P_keys",
            "obs_P_mon",
            "obs_P_umbral",
            "obs_P_debuff",
            "obs_P_king_risk",
            "obs_P_crown",
            "obs_P_round",
            "obs_tension",
            "obs_king_floor_norm",
        ]

        with open(data_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                obs_row = []
                for col in obs_cols:
                    obs_row.append(float(row.get(col, 0.0)))
                # Pad with 14 zeros to match the 24-feature shape expected by CarcosaEnv
                obs_row.extend([0.0] * 14)
                observations.append(obs_row)

                act_str = row.get("action", "")
                if act_str in action_types_list:
                    act_idx = action_types_list.index(act_str)
                else:
                    act_idx = 0
                actions.append(act_idx)

        obs = torch.tensor(observations, dtype=torch.float32)
        actions = torch.tensor(actions, dtype=torch.long)
    else:
        with open(data_path, "rb") as f:
            data = pickle.load(f)

        obs = torch.tensor(data["observations"], dtype=torch.float32)
        actions = torch.tensor(data["actions"], dtype=torch.long)

    print(f"Loaded {len(obs)} samples.")

    # Split into train and validation (90/10)
    indices = np.arange(len(obs))
    np.random.shuffle(indices)
    split = int(0.9 * len(obs))
    train_indices, val_indices = indices[:split], indices[split:]

    train_dataset = TensorDataset(obs[train_indices], actions[train_indices])
    val_dataset = TensorDataset(obs[val_indices], actions[val_indices])

    # Smaller batch size for better noise/generalization
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    # Minimalist architecture from the training guide
    policy_kwargs = dict(net_arch=dict(pi=[128, 128, 64], vf=[128, 128, 64]))
    env = CarcosaEnv()
    model = MaskablePPO("MlpPolicy", env, policy_kwargs=policy_kwargs, verbose=1)

    policy = model.policy
    optimizer = optim.Adam(policy.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=15
    )
    criterion = nn.CrossEntropyLoss()

    device_obj = torch.device(
        device if (device == "cuda" and torch.cuda.is_available()) else "cpu"
    )
    policy.to(device_obj)

    print(f"Training on {device} for {epochs} epochs (Minimalist Guide Strategy)...")

    best_val_acc = 0
    patience_counter = 0
    early_stop_patience = 40

    for epoch in range(epochs):
        # Training phase
        policy.train()
        total_loss = 0
        correct = 0
        total = 0

        for batch_obs, batch_actions in train_loader:
            batch_obs, batch_actions = batch_obs.to(device), batch_actions.to(device)

            distribution = policy.get_distribution(batch_obs)
            logits = distribution.distribution.logits

            loss = criterion(logits, batch_actions)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            _, predicted = torch.max(logits, 1)
            total += batch_actions.size(0)
            correct += (predicted == batch_actions).sum().item()

        avg_train_loss = total_loss / len(train_loader)
        train_acc = correct / total

        # Validation phase
        policy.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for batch_obs, batch_actions in val_loader:
                batch_obs, batch_actions = (
                    batch_obs.to(device),
                    batch_actions.to(device),
                )
                distribution = policy.get_distribution(batch_obs)
                logits = distribution.distribution.logits
                _, predicted = torch.max(logits, 1)
                val_total += batch_actions.size(0)
                val_correct += (predicted == batch_actions).sum().item()

        val_acc = val_correct / val_total
        current_lr = optimizer.param_groups[0]["lr"]
        print(
            f"Epoch {epoch + 1}/{epochs} - Loss: {avg_train_loss:.4f} - Train Acc: {train_acc:.2%} - Val Acc: {val_acc:.2%} - LR: {current_lr}"
        )

        # Learning rate scheduling
        scheduler.step(val_acc)

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            patience_counter = 0
            os.makedirs(os.path.dirname(model_save_path), exist_ok=True)
            model.save(model_save_path + "_best")
            print(
                f"--> New best Val Acc: {val_acc:.2%}. Model saved to {model_save_path}_best.zip"
            )
        else:
            patience_counter += 1

        if val_acc >= 0.80:
            print(f"Target accuracy reached! (Val Acc: {val_acc:.2%})")
            break

        if patience_counter >= early_stop_patience:
            print(
                f"Early stopping triggered after {early_stop_patience} epochs without improvement."
            )
            break

    # Save final model
    os.makedirs(os.path.dirname(model_save_path), exist_ok=True)
    model.save(model_save_path)
    print(f"Final model saved to {model_save_path}.zip")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="train/goldset_500_wins.pkl")
    parser.add_argument("--output", type=str, default="models/bc_goldset_v1")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--save-dir", type=str, default=None)
    parser.add_argument("--log-dir", type=str, default=None)
    parser.add_argument("--device", type=str, default="cpu")
    args = parser.parse_args()

    # Si se define save-dir, se prioriza sobre el path default de output
    save_path = args.output
    if args.save_dir:
        from pathlib import Path

        save_path = str(Path(args.save_dir) / "bc_model")

    train_bc(
        data_path=args.data,
        model_save_path=save_path,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        device=args.device,
    )

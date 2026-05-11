import os
import argparse
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import json

# Minimalist architecture from the guide
class CarcosaPolicyNet(nn.Module):
    def __init__(self, obs_dim, num_actions, hidden_sizes=[128, 128, 64]):
        super().__init__()
        layers = []
        prev_size = obs_dim
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(0.1),
            ])
            prev_size = hidden_size
        layers.append(nn.Linear(prev_size, num_actions))
        self.network = nn.Sequential(*layers)
        
    def forward(self, obs):
        return self.network(obs)

class CarcosaDataset(Dataset):
    OBS_COLS = [
        "obs_P_sanity", "obs_P_keys", "obs_P_mon", "obs_P_umbral",
        "obs_P_debuff", "obs_P_king_risk", "obs_P_crown", "obs_P_round",
        "obs_tension", "obs_king_floor_norm"
    ]
    
    def __init__(self, csv_path):
        self.df = pd.read_csv(csv_path)
        # We only use the 10 columns specified in the guide
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

def train_replicated(csv_path, output_path, epochs=150, lr=1e-3, batch_size=64):
    dataset = CarcosaDataset(csv_path)
    obs_dim = len(dataset.OBS_COLS)
    num_actions = dataset.actions.max().item() + 1
    
    # Split train/val
    train_size = int(len(dataset) * 0.9)
    val_size = len(dataset) - train_size
    train_ds, val_ds = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = CarcosaPolicyNet(obs_dim, num_actions).to(device)
    
    optimizer = optim.AdamW(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=15)
    criterion = nn.CrossEntropyLoss()
    
    print(f"Replicating 70% process on {device}...")
    print(f"Samples: {len(dataset)}, Features: {obs_dim}, Actions: {num_actions}")
    
    best_val_acc = 0
    patience_counter = 0
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        correct = 0
        total = 0
        
        for obs, actions in train_loader:
            obs, actions = obs.to(device), actions.to(device)
            optimizer.zero_grad()
            logits = model(obs)
            loss = criterion(logits, actions)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            correct += (logits.argmax(dim=-1) == actions).sum().item()
            total += actions.size(0)
            
        train_acc = correct / total
        
        model.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for obs, actions in val_loader:
                obs, actions = obs.to(device), actions.to(device)
                logits = model(obs)
                val_correct += (logits.argmax(dim=-1) == actions).sum().item()
                val_total += actions.size(0)
        
        val_acc = val_correct / val_total
        print(f"Epoch {epoch+1}/{epochs} - Train Acc: {train_acc:.2%} - Val Acc: {val_acc:.2%}")
        
        scheduler.step(val_acc)
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            patience_counter = 0
            torch.save(model.state_dict(), output_path + "_best.pt")
            print(f"  -> Best model: {val_acc:.2%}")
        else:
            patience_counter += 1
            
        if patience_counter > 30:
            print("Early stopping.")
            break

    torch.save(model.state_dict(), output_path + "_final.pt")
    print(f"Training finished. Best Val Acc: {best_val_acc:.2%}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, default="data/goldset_replicated.csv")
    parser.add_argument("--output", type=str, default="models/bc_replicated")
    args = parser.parse_args()
    
    train_replicated(args.csv, args.output)

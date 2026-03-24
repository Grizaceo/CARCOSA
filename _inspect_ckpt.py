"""Inspect checkpoint and all action_mapping.json files."""
import torch
import json
import glob
from pathlib import Path

ckpt = torch.load("models_bc/bc_mlp_all_best.pt", map_location="cpu")
print("=== CHECKPOINT KEYS:", list(ckpt.keys()))
print("obs_dim:", ckpt.get("obs_dim"))
print("num_actions:", ckpt.get("num_actions"))
print("hidden_sizes:", ckpt.get("hidden_sizes"))
print("model_type:", ckpt.get("model_type"))
print("val_acc:", ckpt.get("val_acc"))
print()

# Print final layer shape directly
state_dict = ckpt["model_state_dict"]
for k, v in state_dict.items():
    if "weight" in k or "bias" in k:
        print(f"  {k}: {v.shape}")

print()
for path in glob.glob("reports/**/bc_smoke.action_mapping.json", recursive=True):
    print(f"=== {path}")
    with open(path) as f:
        data = json.load(f)
    print(json.dumps(data, indent=2))

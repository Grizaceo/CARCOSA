"""BC standalone para CARCOSA (línea [092]).

Entrena CarcosaPolicyNet por behavioral cloning desde datos de GOAL.
No depende de sb3_contrib (que no está instalado). Usa torch directo.

Uso:
    python train/train_bc_standalone.py --data train/expert_data_probe.pkl \
        --save models/bc_goal_probe.pt --epochs 30 --batch-size 256
"""
import sys, argparse
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).parent.parent))
from train.carcosa_env import CarcosaEnv
from train.model import CarcosaPolicyNet

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="train/expert_data_probe.pkl")
    ap.add_argument("--save", default="models/bc_goal_probe.pt")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden", default="256,256,128")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    import pickle
    with open(args.data, "rb") as f:
        data = pickle.load(f)

    obs = np.array(data["observations"], dtype=np.float32)
    acts = np.array(data["actions"], dtype=np.int64).reshape(-1)
    print(f"Dataset: {obs.shape[0]} muestras, obs_dim={obs.shape[1]}, num_actions={len(CarcosaEnv.ACTION_TYPES)}")

    hidden = [int(x) for x in args.hidden.split(",")]
    model = CarcosaPolicyNet(obs_dim=obs.shape[1], num_actions=len(CarcosaEnv.ACTION_TYPES), hidden_sizes=hidden).to(args.device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    crit = nn.CrossEntropyLoss()

    ds = TensorDataset(torch.tensor(obs), torch.tensor(acts))
    dl = DataLoader(ds, batch_size=args.batch_size, shuffle=True)

    model.train()
    for ep in range(args.epochs):
        tot = 0.0; n = 0; correct = 0
        for xb, yb in dl:
            xb, yb = xb.to(args.device), yb.to(args.device)
            opt.zero_grad()
            logits = model(xb)
            loss = crit(logits, yb)
            loss.backward()
            opt.step()
            tot += loss.item() * xb.size(0)
            correct += (logits.argmax(1) == yb).sum().item()
            n += xb.size(0)
        if (ep + 1) % 5 == 0 or ep == 0:
            print(f"  ep {ep+1}/{args.epochs}  loss={tot/n:.4f}  acc={correct/n:.3f}")

    Path(args.save).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model_state_dict": model.state_dict(), "obs_dim": obs.shape[1],
                "num_actions": len(CarcosaEnv.ACTION_TYPES), "hidden_sizes": hidden}, args.save)
    print(f"BC guardado en {args.save}")

if __name__ == "__main__":
    main()

"""Evalúa CarcosaPolicyNet (BC) en el env por N episodios y reporta win-rate."""
import sys
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0, str(Path(__file__).parent.parent))
from train.carcosa_env import CarcosaEnv
from train.model import CarcosaPolicyNet

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--episodes", type=int, default=20)
    args = ap.parse_args()

    ckpt = torch.load(args.model, map_location="cpu")
    model = CarcosaPolicyNet(obs_dim=ckpt["obs_dim"], num_actions=ckpt["num_actions"], hidden_sizes=ckpt["hidden_sizes"])
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    env = CarcosaEnv()
    wins = 0
    rewards = []
    for ep in range(args.episodes):
        obs, info = env.reset(seed=ep * 137)
        done = False
        total = 0.0
        while not done:
            with torch.no_grad():
                logits = model(torch.tensor(obs, dtype=torch.float32).unsqueeze(0))
                # respetar máscara legal
                mask = env.action_masks()
                mask_t = torch.tensor(mask, dtype=torch.bool).unsqueeze(0)
                logits = logits.masked_fill(~mask_t, float("-inf"))
                a = logits.argmax(1).item()
            obs, r, term, trunc, info = env.step(a)
            done = term or trunc
            total += r
        rewards.append(total)
        out = info.get("outcome", "TIMEOUT")
        if "WIN" in str(out):
            wins += 1
        print(f"Ep {ep+1}: {out}  reward={total:.1f}")
    print(f"\nBC Wins: {wins}/{args.episodes} ({wins/args.episodes:.1%})  avg_reward={np.mean(rewards):.1f}")

if __name__ == "__main__":
    main()

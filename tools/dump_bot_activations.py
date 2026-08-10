"""
dump_bot_activations.py — Extrae activaciones del bot PPO (techo 23%) mientras juega.

Carga el modelo de 23% (models/maskable_ppo_carcosa_final_20260805_154245.zip),
corre una partida headless con 4 bots PPO, y en cada decisión de bot captura:
  - obs: vector de observación (167 dims)
  - policy_hidden: activación capa intermedia policy_net (64 dims, post-Tanh)
  - logits: logits de acción (27 dims)
  - probs: softmax de logits
  - action: acción elegida (índice + nombre)
  - value: V(s) estimado por value_net

Uso:
  python tools/dump_bot_activations.py --seed 1 --steps 40 --out /tmp/acts.jsonl
"""
from __future__ import annotations
import argparse
import json
import sys
import torch
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sb3_contrib import MaskablePPO
from engine.config import Config
from engine.rng import RNG
from engine.state import GameState
from engine.transition import step
from engine.legality import get_legal_actions
from engine.actions import Action, ActionType
from sim.runner import make_smoke_state
from sim.policies import PPOCARCOPlayerPolicy  # para mapear action index -> Action

MODEL = "models/maskable_ppo_carcosa_final_20260805_154245.zip"


def action_name(action_type: str) -> str:
    try:
        return ActionType(action_type).name
    except Exception:
        return str(action_type)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--steps", type=int, default=40, help="número de decisiones de bot a volcar")
    ap.add_argument("--out", type=str, default="/tmp/bot_activations.jsonl")
    ap.add_argument("--model", type=str, default=MODEL)
    args = ap.parse_args()

    device = "cpu"
    model = MaskablePPO.load(args.model, device=device)
    policy = model.policy
    policy.eval()

    # Importamos el env para obtener la obs real (167 dims) desde el state.
    # El env construye su propio Config() por defecto; usamos ESE para el state
    # (así la obs que extrae el env es coherente con el estado que simulamos).
    from train.carcosa_env import CarcosaEnv
    env = CarcosaEnv()
    cfg = env.cfg
    rng = RNG(args.seed)
    state: GameState = make_smoke_state(seed=args.seed, cfg=cfg)

    # Hooks para capturar activaciones intermedias
    captures = {}

    def make_hook(key):
        def hook(module, inp, out):
            captures[key] = out.detach().cpu().numpy()
        return hook

    hooks = [
        policy.mlp_extractor.policy_net.register_forward_hook(make_hook("policy_hidden")),
        policy.mlp_extractor.value_net.register_forward_hook(make_hook("value_hidden")),
    ]

    def obs_for(actor: str) -> np.ndarray:
        env.state = state
        # _get_obs espera self._current_actor seteado en algunas versiones
        if hasattr(env, "_current_actor"):
            env._current_actor = actor
        try:
            return np.asarray(env._get_obs(), dtype=np.float32).reshape(-1)
        except Exception:
            return np.asarray(env._get_obs(), dtype=np.float32)

    def bot_decide(actor: str):
        acts = get_legal_actions(state, actor)
        if not acts:
            return None, None
        obs = obs_for(actor)
        obs_t = torch.as_tensor(obs, device=device).unsqueeze(0)
        with torch.no_grad():
            latent = policy.extract_features(obs_t, None)
            # MlpExtractor expone policy_net / value_net como Sequential
            policy_latent = policy.mlp_extractor.policy_net(latent)
            value_latent = policy.mlp_extractor.value_net(latent)
            logits = policy.action_net(policy_latent)
            value = policy.value_net(value_latent)
            # action masking
            try:
                mask = policy.action_masks(obs_t)
                if mask is not None:
                    logits = torch.where(mask, logits, torch.tensor(-1e10, device=device))
            except Exception:
                pass
            probs = torch.softmax(logits, dim=-1)
            action_idx = int(torch.argmax(logits, dim=-1).item())
            logit_arr = logits.squeeze(0).cpu().numpy()
            prob_arr = probs.squeeze(0).cpu().numpy()
            value_val = float(value.item())

        hidden = captures.get("policy_hidden")
        if hidden is not None and hasattr(hidden, "cpu"):
            hidden_arr = hidden.squeeze(0).cpu().numpy()
        elif hidden is not None:
            hidden_arr = np.asarray(hidden).squeeze(0)
        else:
            hidden_arr = None

        chosen = acts[action_idx] if 0 <= action_idx < len(acts) else acts[0]
        return chosen, {
            "obs": obs.tolist(),
            "policy_hidden": hidden_arr.tolist() if hidden_arr is not None else None,
            "logits": logit_arr.tolist(),
            "probs": prob_arr.tolist(),
            "action_idx": action_idx,
            "action_name": action_name(chosen.type) if chosen else None,
            "value": value_val,
        }

    records = []
    turn = 0
    while not state.game_over and len(records) < args.steps:
        turn += 1
        # El env usa su propio state; lo sincronizamos
        env.state = state
        env.rng = rng
        actor = str(state.turn_order[state.turn_pos])
        # fase KING la resuelve el env solo dentro de step
        chosen, info = bot_decide(actor)
        action_id = info.get("action_idx") if info else -1
        obs_n, reward, term, trunc, meta = env.step(action_id if action_id is not None else -1)
        if info:
            records.append({
                "turn": turn, "actor": actor, "round": state.round, **info,
                "reward": float(reward), "terminated": bool(term), "truncated": bool(trunc),
            })
        state = env.state
        if term or trunc:
            break

    for h in hooks:
        h.remove()

    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"=== BOT ACTIVATIONS DUMP (seed {args.seed}) ===")
    print(f"modelo: {args.model}")
    print(f"decisiones volcadas: {len(records)} -> {args.out}")
    print(f"obs_dim=167, policy_hidden=64 (post-Tanh), logits/acciones=27")
    print()
    for r in records[:10]:
        hid = r["policy_hidden"]
        top_hid = sorted(range(len(hid)), key=lambda i: -abs(hid[i]))[:5] if hid else []
        top_logits = sorted(range(len(r["logits"])), key=lambda i: -r["logits"][i])[:3]
        print(f"t{r['turn']} r{r['round']} {r['actor']}: {r['action_name']} "
              f"p={r['probs'][r['action_idx']]:.3f} V={r['value']:.2f}")
        print(f"   hidden top|act|: {[(i, round(hid[i], 2)) for i in top_hid]}")
        print(f"   logits top3: {[(i, round(r['logits'][i], 2)) for i in top_logits]}")


if __name__ == "__main__":
    main()
